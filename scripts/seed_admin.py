#!/usr/bin/env python3
"""Seed the demonstration administrator.

    python scripts/seed_admin.py

Every other role is seeded and the admin was not, which meant the admin
dashboard could be opened only by promoting an account by hand in psql. A
juror following the README cannot do that, so a screen that works looked
broken. The account is created here for the same reason the fleet is: a
documented demo account has to exist before it can be documented.

Reserved block `+237600000007xxx`, alongside drivers on 9xxx and passengers on
8xxx, so any one of the three can be reseeded without disturbing the others.
It sits inside TEST_NUMBER_PREFIX, which is what makes the OTP appear on screen
instead of being sent to a handset nobody has.

Upsert, never delete. `users` is referenced by rides, incidents and audit rows,
and an admin identity is exactly the kind of record that should be hard to
erase.

**This is a demonstration account, not a production one.** It exists because
`ALLOW_TEST_NUMBERS` is true in development. Production sets that to false, the
whole reserved block stops authenticating, and administrators are provisioned
deliberately rather than by a seeding script.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import text

from app.db import dispose_engine, get_sessionmaker

SEED_PREFIX = "+237600000007"

ADMINS = [
    ("Superviseur VORA", "fr"),
]


async def seed(count: int) -> int:
    sessionmaker = get_sessionmaker()

    async with sessionmaker() as session:
        created = 0
        for i in range(count):
            name, locale = ADMINS[i % len(ADMINS)]
            phone = f"{SEED_PREFIX}{i:03d}"

            # ON CONFLICT covers the case that matters most here: an account
            # that already exists as a passenger. Without the role in the
            # update clause, a teammate who logged in on this number first
            # would leave it stuck as a passenger and the dashboard would 403
            # with nothing on screen to explain why.
            user_id = await session.scalar(
                text(
                    "INSERT INTO users "
                    "  (phone_e164, display_name, role, status, locale) "
                    "VALUES (:phone, :name, 'admin', 'active', :locale) "
                    "ON CONFLICT (phone_e164) DO UPDATE SET "
                    "  display_name = EXCLUDED.display_name, "
                    "  role = 'admin', "
                    "  status = 'active', "
                    "  locale = EXCLUDED.locale "
                    "RETURNING id"
                ),
                {"phone": phone, "name": name, "locale": locale},
            )
            if user_id is not None:
                created += 1

        await session.commit()

        total = await session.scalar(
            text("SELECT count(*) FROM users WHERE role = 'admin'")
        )

    print(f"  {created} admin account(s) up to date, {total} in total")
    print(f"  sign in with {SEED_PREFIX}000")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args()

    if not 1 <= args.count <= len(ADMINS):
        print(f"count must be between 1 and {len(ADMINS)}", file=sys.stderr)
        return 1

    async def run() -> int:
        try:
            return await seed(args.count)
        finally:
            await dispose_engine()

    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
