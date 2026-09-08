#!/usr/bin/env python3
"""Seed demo passengers and their ride history.

    python scripts/seed_history.py                 # 5 passengers, 20 rides
    python scripts/seed_history.py --rides 30

Idempotent by converging, not by resetting. Passengers are upserted on their
phone number and rides are topped up to the target count, so a rerun leaves the
same system without deleting anything.

It cannot delete, and that is the database being right rather than a
limitation. `rides.passenger_id` is ON DELETE RESTRICT because a ride is a
financial and legal record, and `ride_events` is append-only, so clearing
seeded history would mean defeating I7 to make a fixture convenient.

The reserved `+237600000008xxx` block keeps these rows separate from the
drivers seeded into `+237600000009xxx`, so either can be reseeded without
touching the other or a real account.

Both sit inside the range the auth service accepts, which earlier blocks did
not. A seeded account that cannot request an OTP cannot be logged into, so the
whole fleet was unreachable and the driver side of the app could not be shown
at all.

**Why history exists at all.** A history screen with nothing in it demos
nothing, and a jury reads an empty list as a feature that was not built. These
rides are completed and dated across the past three weeks so the screen has
something to show and the fare column looks like money rather than like a
placeholder.

Every fare here is computed with the real fare engine rather than made up, so
a seeded ride and a live one price identically. A history full of round
numbers that the pricing code could never produce is worse than an empty one:
it is the kind of detail that makes somebody doubt the rest of it.

The PIN columns are populated because they are NOT NULL, and hashed with the
same function the live path uses. A completed ride's PIN is spent, but seeding
a plaintext-only value would leave a row the application could not have
written.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.db import dispose_engine, get_sessionmaker
from app.security import hashing
from app.services.fare import DEFAULT_FARE_CONFIG, quote_both

# Reserved block for seeded passengers, inside the range the auth service
# accepts so these accounts can actually be logged into. Drivers take 9xxx in
# the same range; keeping the two apart lets either be reseeded without
# disturbing the other.
SEED_PREFIX = "+237600000008"

PASSENGERS = [
    ("Amina", "fr"),
    ("Josephine", "fr"),
    ("Thierry", "fr"),
    ("Neville", "en"),
    ("Clarisse", "fr"),
]

# Real corridors people actually travel, with the gazetteer's own coordinates.
# A history of plausible journeys reads very differently from random points.
TRIPS: list[tuple[str, float, float, str, float, float]] = [
    ("Carrefour Warda", 3.87664, 11.51303, "Marche Central", 3.86600, 11.51700),
    ("Nlongkak", 3.88100, 11.51700, "Mvog-Mbi", 3.85700, 11.52400),
    ("Bastos", 3.88800, 11.51200, "Poste Centrale", 3.86700, 11.51600),
    ("Mokolo", 3.87900, 11.50600, "Ngoa-Ekelle", 3.85300, 11.50100),
    ("Emana", 3.91500, 11.51900, "Carrefour Warda", 3.87664, 11.51303),
    ("Essos", 3.87400, 11.53100, "Melen", 3.86300, 11.48800),
    ("Ngousso", 3.90100, 11.55400, "Nlongkak", 3.88100, 11.51700),
    ("Biyem-Assi", 3.83700, 11.48400, "Poste Centrale", 3.86700, 11.51600),
    ("Etoudi", 3.90600, 11.53000, "Mokolo", 3.87900, 11.50600),
    ("Mvan", 3.82700, 11.51600, "Marche Central", 3.86600, 11.51700),
]


def _point(lng: float, lat: float) -> str:
    """WKT is (longitude latitude), the reverse of how coordinates are said."""
    return f"SRID=4326;POINT({lng} {lat})"


async def seed(passenger_count: int, ride_count: int) -> tuple[int, int]:
    sessionmaker = get_sessionmaker()
    rng = random.Random(20260907)  # noqa: S311 - fixture data, not security
    now = datetime.now(UTC)

    async with sessionmaker() as session:
        # Upsert rather than delete-and-recreate.
        #
        # The first version cleared its own rows first, which is the ordinary
        # way to make a seeder idempotent and is wrong here. `rides.passenger_id`
        # is ON DELETE RESTRICT, deliberately: a ride is a financial and legal
        # record, so the database refuses to let the person on it be erased.
        # Deleting the rides instead is worse, because `ride_events` is
        # append-only and a cascade trips its trigger.
        #
        # So the seeder converges instead of resetting. The database was right
        # and the seeder was wrong; I7 is not something to work around.
        passenger_ids: list[uuid.UUID] = []
        for i in range(passenger_count):
            name, locale = PASSENGERS[i % len(PASSENGERS)]
            user_id = await session.scalar(
                text(
                    "INSERT INTO users "
                    "(phone_e164, display_name, role, status, locale) "
                    "VALUES (:phone, :name, 'passenger', 'active', :locale) "
                    "ON CONFLICT (phone_e164) DO UPDATE SET "
                    "  display_name = EXCLUDED.display_name, "
                    "  locale = EXCLUDED.locale "
                    "RETURNING id"
                ),
                {
                    "phone": f"{SEED_PREFIX}{i:03d}",
                    "name": name,
                    "locale": locale,
                },
            )
            passenger_ids.append(user_id)

        # Seeded drivers, so history points at a fleet that is actually there.
        # Left null rather than invented if the fleet has not been seeded yet:
        # a ride referencing a driver id that does not exist is worse than one
        # with no driver, and the foreign key would refuse it anyway.
        fleet = (
            await session.execute(
                text(
                    "SELECT d.id AS driver_id, v.id AS vehicle_id "
                    "FROM drivers d "
                    "JOIN users u ON u.id = d.user_id "
                    "JOIN vehicles v ON v.driver_id = d.id "
                    "WHERE u.phone_e164 LIKE :prefix || '%'"
                ),
                {"prefix": "+237600000009"},
            )
        ).all()

        if not fleet:
            print(
                "warning: no seeded drivers found, so history will have no "
                "driver attached. Run scripts/seed_drivers.py first."
            )

        # Reattach any seeded ride whose driver went missing.
        #
        # Earlier versions of the driver seeder deleted and recreated the
        # fleet. `rides.driver_id` is ON DELETE SET NULL, so that succeeded
        # quietly and left every historical ride pointing at nobody. The
        # seeder no longer does this, but a database that has already been
        # through it needs repairing, and a history screen listing twenty
        # trips that nobody drove is worse than an empty one.
        if fleet:
            orphaned = await session.execute(
                text(
                    "UPDATE rides SET "
                    "  driver_id = :driver_id, vehicle_id = :vehicle_id "
                    "WHERE driver_id IS NULL "
                    "  AND status = 'completed' "
                    "  AND passenger_id IN ("
                    "    SELECT id FROM users WHERE phone_e164 LIKE :prefix || '%')"
                ),
                {
                    "driver_id": fleet[0].driver_id,
                    "vehicle_id": fleet[0].vehicle_id,
                    "prefix": SEED_PREFIX,
                },
            )
            if orphaned.rowcount:
                print(
                    f"reattached {orphaned.rowcount} historical rides that had "
                    f"lost their driver"
                )

        # Only make up the difference. Running this twice must leave the same
        # system, and with no delete the only way to do that is to count first.
        already = await session.scalar(
            text(
                "SELECT count(*) FROM rides r "
                "JOIN users u ON u.id = r.passenger_id "
                "WHERE u.phone_e164 LIKE :prefix || '%'"
            ),
            {"prefix": SEED_PREFIX},
        )
        already = int(already or 0)
        if already >= ride_count:
            print(f"{already} seeded rides already present, nothing to add")
            await session.commit()
            return len(passenger_ids), 0

        print(f"{already} seeded rides present, adding {ride_count - already}")

        created = 0
        for i in range(already, ride_count):
            p_label, p_lat, p_lng, d_label, d_lat, d_lng = TRIPS[i % len(TRIPS)]
            passenger_id = passenger_ids[i % len(passenger_ids)]

            # Straight-line metres, inflated by the same 1.35 factor the
            # haversine routing fallback uses, so a seeded distance is one the
            # system itself could have produced. No OSRM call: seeding must
            # work on a cold machine where the routing container is still
            # warming up.
            straight = (
                ((p_lat - d_lat) ** 2 + (p_lng - d_lng) ** 2) ** 0.5
            ) * 111_320
            distance_m = int(straight * 1.35)
            duration_s = int(distance_m / 5.6)

            mode = "corridor" if i % 3 == 0 else "exclusive"
            fares = quote_both(distance_m, duration_s, DEFAULT_FARE_CONFIG)
            fare = fares.corridor_xaf if mode == "corridor" else fares.exclusive_xaf

            # Spread across three weeks, during daylight, so the history reads
            # like a person's rather than like a batch job at 03:00.
            ended = now - timedelta(
                days=rng.randint(1, 21),
                hours=rng.randint(6, 20),
                minutes=rng.randint(0, 59),
            )
            started = ended - timedelta(seconds=duration_s)
            accepted = started - timedelta(seconds=rng.randint(90, 300))

            driver_id, vehicle_id = (
                (fleet[i % len(fleet)].driver_id, fleet[i % len(fleet)].vehicle_id)
                if fleet
                else (None, None)
            )

            pin = f"{rng.randint(0, 9999):04d}"
            await session.execute(
                text(
                    "INSERT INTO rides ("
                    "  passenger_id, driver_id, vehicle_id, mode, status, seats,"
                    "  pickup_label, dropoff_label, pickup_geom, dropoff_geom,"
                    "  quoted_fare_xaf, final_fare_xaf, quoted_distance_m,"
                    "  quoted_duration_s, actual_distance_m, pin, pin_hash,"
                    "  accepted_at, arrived_at, started_at, ended_at, created_at"
                    ") VALUES ("
                    "  :passenger_id, :driver_id, :vehicle_id, :mode, 'completed',"
                    "  1, :p_label, :d_label, :p_geom, :d_geom,"
                    "  :fare, :fare, :distance, :duration, :distance, :pin,"
                    "  :pin_hash, :accepted, :accepted, :started, :ended, :accepted"
                    ")"
                ),
                {
                    "passenger_id": passenger_id,
                    "driver_id": driver_id,
                    "vehicle_id": vehicle_id,
                    "mode": mode,
                    "p_label": p_label,
                    "d_label": d_label,
                    "p_geom": _point(p_lng, p_lat),
                    "d_geom": _point(d_lng, d_lat),
                    "fare": fare,
                    "distance": distance_m,
                    "duration": duration_s,
                    "pin": pin,
                    "pin_hash": hashing.hash_otp(pin),
                    "accepted": accepted,
                    "started": started,
                    "ended": ended,
                },
            )
            created += 1

        await session.commit()
        return len(passenger_ids), created


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--passengers", type=int, default=5)
    parser.add_argument("--rides", type=int, default=20)
    args = parser.parse_args()

    try:
        passengers, rides = await seed(args.passengers, args.rides)
    finally:
        await dispose_engine()

    print(f"seeded {passengers} passengers and {rides} completed rides")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130) from None
