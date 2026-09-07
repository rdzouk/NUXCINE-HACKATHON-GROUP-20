#!/usr/bin/env python3
"""Seed drivers, vehicles and presence around Yaounde.

    python scripts/seed_drivers.py            # 10 drivers
    python scripts/seed_drivers.py --count 12

Idempotent: reruns replace the seeded fleet and leave real accounts alone,
which is what the `+2376000009xx` reservation below is for.

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

# Reserved block for seeded drivers, so a rerun can clear exactly these and
# nothing else. Real test numbers live below +23760000009xx.
SEED_PREFIX = "+2376000009"

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
        removed = await session.execute(
            text(
                "DELETE FROM users WHERE phone_e164 LIKE :prefix || '%'"
            ),
            {"prefix": SEED_PREFIX},
        )
        print(f"removed {removed.rowcount} previously seeded drivers")

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
                    "VALUES (:phone, :name, 'driver', 'active', 'fr') RETURNING id"
                ),
                {"phone": phone, "name": name},
            )

            driver_id = await session.scalar(
                text(
                    "INSERT INTO drivers "
                    "(user_id, kyc_status, kyc_reviewed_at, is_online, seats_free, "
                    " rating_avg) "
                    "VALUES (:user_id, 'verified', now(), true, :seats, :rating) "
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
                    "VALUES (:driver_id, :plate, :make, :model, :color, :seats, "
                    " :ramp, :boot, :front, :assists, :animal)"
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
                    "        ST_MakePoint(:lng, :lat)::geography, :heading, now())"
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
