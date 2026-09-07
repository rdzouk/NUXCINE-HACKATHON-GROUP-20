#!/usr/bin/env python3
"""Seed demo passengers and their ride history.

    python scripts/seed_history.py                 # 5 passengers, 20 rides
    python scripts/seed_history.py --rides 30

Idempotent: reruns clear exactly the seeded passengers and rebuild them. The
reserved `+2376000008xx` block is what makes "exactly" true, so a rerun cannot
touch a real account or a driver seeded from the +2376000009xx block.

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

# Reserved block for seeded passengers. Drivers use +2376000009xx; keeping the
# two apart is what lets either be reseeded without disturbing the other.
SEED_PREFIX = "+2376000008"

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
        removed = await session.execute(
            text("DELETE FROM users WHERE phone_e164 LIKE :prefix || '%'"),
            {"prefix": SEED_PREFIX},
        )
        print(f"removed {removed.rowcount} previously seeded passengers")

        passenger_ids: list[uuid.UUID] = []
        for i in range(passenger_count):
            name, locale = PASSENGERS[i % len(PASSENGERS)]
            user_id = await session.scalar(
                text(
                    "INSERT INTO users "
                    "(phone_e164, display_name, role, status, locale) "
                    "VALUES (:phone, :name, 'passenger', 'active', :locale) "
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
                {"prefix": "+2376000009"},
            )
        ).all()

        if not fleet:
            print(
                "warning: no seeded drivers found, so history will have no "
                "driver attached. Run scripts/seed_drivers.py first."
            )

        created = 0
        for i in range(ride_count):
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
