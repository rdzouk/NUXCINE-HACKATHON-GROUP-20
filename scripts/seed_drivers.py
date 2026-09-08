#!/usr/bin/env python3
"""Seed drivers, vehicles and presence around Yaounde.

    python scripts/seed_drivers.py            # 10 drivers
    python scripts/seed_drivers.py --count 12

Idempotent by upsert, not by replacement. Reruns update the seeded fleet in
place and leave real accounts alone, which is what the `+2376000009xx`
reservation below is for.

It deliberately does not delete. `rides.driver_id` is ON DELETE SET NULL, so
clearing the fleet succeeds quietly and detaches the driver from every
historical ride, leaving a history screen full of trips nobody drove. That is
the same mistake the passenger seeder makes loudly, and the quiet version is
the more dangerous one.

**The capability spread is the point, not decoration.** Phase 6 matches a
passenger's vehicle requirements against these flags, and a fleet where every
car is identical would make that matching look like it works when it has never
actually excluded anything. So the fleet below deliberately contains vehicles
that cannot serve some requests: two with a ramp, three with boot space, one
that refuses a guide animal.

Accessibility here is a property of the **vehicle**, never of a person (I9).
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys

from sqlalchemy import text

from app.db import dispose_engine, get_sessionmaker

# Reserved block for seeded drivers, so a rerun touches exactly these and
# nothing else.
#
# It has to sit inside the range the auth service accepts, or the whole fleet
# is unreachable: a seeded driver who cannot request an OTP cannot be logged
# into, and the driver half of the app cannot be demonstrated at all. Test
# numbers are TEST_NUMBER_PREFIX (+23760000000) plus one to four digits, so
# these end up as +237600000009000 upward, with 9xxx marking them as drivers.
SEED_PREFIX = "+237600000009"

# Real places, so a seeded fleet looks plausible on a map rather than a grid of
# points in a field. Coordinates are the gazetteer's own.
STANDS: list[tuple[str, float, float]] = [
    ("Carrefour Warda", 3.87664, 11.51303),
    ("Nlongkak", 3.88100, 11.51700),
    ("Bastos", 3.88800, 11.51200),
    ("Mvog-Mbi", 3.85800, 11.52300),
    ("Melen", 3.85600, 11.48900),
    ("Obili", 3.84900, 11.49400),
    ("Essos", 3.87600, 11.53700),
    ("Biyem-Assi", 3.83300, 11.47800),
    ("Nsam", 3.83300, 11.51200),
    ("Etoudi", 3.90600, 11.53100),
    ("Mendong", 3.82700, 11.46300),
    ("Emana", 3.93300, 11.51600),
]

# (make, model, colour, seats, ramp, boot, front seat, assists, guide animal)
FLEET: list[tuple[str, str, str, int, bool, bool, bool, bool, bool]] = [
    ("Toyota", "Corolla", "blanc", 4, False, False, True, False, True),
    ("Toyota", "Hiace", "bleu", 8, True, True, True, True, True),
    ("Nissan", "Almera", "gris", 4, False, True, True, False, True),
    ("Toyota", "Carina", "vert", 4, False, False, True, False, False),
    ("Hyundai", "Starex", "blanc", 7, True, True, False, True, True),
    ("Toyota", "Corolla", "rouge", 4, False, False, True, False, True),
    ("Kia", "Picanto", "jaune", 4, False, False, False, False, True),
    ("Toyota", "RAV4", "noir", 5, False, True, True, True, True),
    ("Nissan", "Sunny", "blanc", 4, False, False, True, False, True),
    ("Mercedes", "Sprinter", "blanc", 8, True, True, True, True, True),
    ("Suzuki", "Swift", "bleu", 4, False, False, True, False, True),
    ("Toyota", "Avensis", "gris", 4, False, True, True, False, True),
]

FIRST_NAMES = [
    "Emmanuel", "Aristide", "Bertrand", "Cyrille", "Didier", "Serge",
    "Landry", "Aime", "Blaise", "Franck", "Ghislain", "Herve",
]


async def seed(count: int) -> int:
    sessionmaker = get_sessionmaker()
    rng = random.Random(20260907)  # noqa: S311 - fixture data, not security

    async with sessionmaker() as session:
        # Upsert, never delete. `rides.driver_id` is ON DELETE SET NULL, so
        # clearing the fleet does not fail loudly the way clearing passengers
        # does. It quietly detaches the driver from every historical ride, and
        # the history screen then shows trips that nobody drove. A silent
        # version of the same mistake is worse than the one that crashes.

        created = 0
        for i in range(count):
            _stand, lat, lng = STANDS[i % len(STANDS)]
            make, model, colour, seats, ramp, boot, front, assists, animal = FLEET[
                i % len(FLEET)
            ]

            phone = f"{SEED_PREFIX}{i:03d}"
            name = f"{FIRST_NAMES[i % len(FIRST_NAMES)]} (chauffeur)"

            user_id = await session.scalar(
                text(
                    "INSERT INTO users (phone_e164, display_name, role, status, locale) "
                    "VALUES (:phone, :name, 'driver', 'active', 'fr') "
                    "ON CONFLICT (phone_e164) DO UPDATE SET "
                    "  display_name = EXCLUDED.display_name, role = 'driver', "
                    "  status = 'active' "
                    "RETURNING id"
                ),
                {"phone": phone, "name": name},
            )

            driver_id = await session.scalar(
                text(
                    "INSERT INTO drivers "
                    "(user_id, kyc_status, kyc_reviewed_at, is_online, seats_free, "
                    " rating_avg) "
                    "VALUES (:user_id, 'verified', now(), true, :seats, :rating) "
                    "ON CONFLICT (user_id) DO UPDATE SET "
                    "  kyc_status = 'verified', is_online = true, "
                    "  seats_free = EXCLUDED.seats_free "
                    "RETURNING id"
                ),
                {
                    "user_id": user_id,
                    "seats": seats,
                    "rating": round(rng.uniform(4.1, 5.0), 2),
                },
            )

            await session.execute(
                text(
                    "INSERT INTO vehicles "
                    "(driver_id, plate, make, model, color, seats, has_ramp, "
                    " has_boot_space, front_seat_available, driver_assists, "
                    " accepts_guide_animal) "
                    "SELECT :driver_id, :plate, :make, :model, :color, :seats, "
                    " :ramp, :boot, :front, :assists, :animal "
                    "WHERE NOT EXISTS ("
                    "  SELECT 1 FROM vehicles WHERE driver_id = :driver_id)"
                ),
                {
                    "driver_id": driver_id,
                    "plate": f"CE {rng.randint(100, 999)} {chr(65 + i % 26)}{chr(65 + (i * 7) % 26)}",
                    "make": make,
                    "model": model,
                    "color": colour,
                    "seats": seats,
                    "ramp": ramp,
                    "boot": boot,
                    "front": front,
                    "assists": assists,
                    "animal": animal,
                },
            )

            # Scattered a little around the stand, so markers do not stack on
            # one pixel and the matching radius has something to discriminate.
            await session.execute(
                text(
                    "INSERT INTO driver_presence (driver_id, geom, heading, recorded_at) "
                    "VALUES (:driver_id, "
                    "        ST_MakePoint(:lng, :lat)::geography, :heading, now()) "
                    "ON CONFLICT (driver_id) DO UPDATE SET "
                    "  geom = EXCLUDED.geom, heading = EXCLUDED.heading, "
                    "  recorded_at = EXCLUDED.recorded_at"
                ),
                {
                    "driver_id": driver_id,
                    "lat": lat + rng.uniform(-0.004, 0.004),
                    "lng": lng + rng.uniform(-0.004, 0.004),
                    "heading": rng.randint(0, 359),
                },
            )
            created += 1

        await session.commit()

    print(f"seeded {created} verified, online drivers")

    async with sessionmaker() as session:
        rows = await session.execute(
            text(
                "SELECT v.make || ' ' || v.model AS vehicle, v.seats, "
                "       v.has_ramp, v.has_boot_space, v.accepts_guide_animal "
                "FROM vehicles v JOIN drivers d ON d.id = v.driver_id "
                "JOIN users u ON u.id = d.user_id "
                "WHERE u.phone_e164 LIKE :prefix || '%' ORDER BY v.make"
            ),
            {"prefix": SEED_PREFIX},
        )
        print()
        print(f"  {'vehicle':<20} {'seats':>5}  ramp  boot  animal")
        for r in rows:
            print(
                f"  {r.vehicle:<20} {r.seats:>5}  "
                f"{'yes ' if r.has_ramp else '  . '}  "
                f"{'yes ' if r.has_boot_space else '  . '}  "
                f"{'yes' if r.accepts_guide_animal else '  .'}"
            )

        ramps = await session.scalar(
            text(
                "SELECT count(*) FROM vehicles v "
                "JOIN drivers d ON d.id = v.driver_id "
                "JOIN users u ON u.id = d.user_id "
                "WHERE u.phone_e164 LIKE :prefix || '%' AND v.has_ramp"
            ),
            {"prefix": SEED_PREFIX},
        )
        print()
        print(f"  {ramps} of {created} have a ramp")
        if ramps in (0, created):
            # A fleet that is uniformly capable or uniformly incapable cannot
            # demonstrate matching: the filter would never change the result.
            print(
                "  WARNING: no capability spread, so accessibility matching "
                "cannot be demonstrated",
                file=sys.stderr,
            )
            return 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10, help="8 to 12 is sensible.")
    args = parser.parse_args()

    if not 1 <= args.count <= len(FLEET):
        print(f"count must be between 1 and {len(FLEET)}", file=sys.stderr)
        return 1

    async def run() -> int:
        try:
            return await seed(args.count)
        finally:
            await dispose_engine()

    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
