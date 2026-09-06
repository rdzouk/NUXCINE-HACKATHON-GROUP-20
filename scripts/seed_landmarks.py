#!/usr/bin/env python3
"""Load the gazetteer into Postgres.

    python scripts/seed_landmarks.py

Idempotent: rerunning replaces the OSM-sourced rows and leaves hand-added ones
alone. That distinction is why `landmarks.source` exists. Curated entries are
the ones OSM gets wrong or omits, and they are exactly what must survive a
refresh of the automated data.

Inserted in batches with a single multi-row INSERT per batch rather than one
statement per landmark. Four hundred round trips to build a lookup table is the
kind of thing that quietly costs a minute every time anyone seeds a database.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import text

from app.db import dispose_engine, get_sessionmaker

BATCH = 100

INSERT_SQL = text(
    """
    INSERT INTO landmarks
        (name, aliases, kind, city, quartier, geom, popularity, source, osm_id)
    VALUES (
        :name,
        CAST(:aliases AS text[]),
        CAST(:kind AS landmark_kind),
        :city,
        :quartier,
        ST_MakePoint(:lng, :lat)::geography,
        :popularity,
        :source,
        :osm_id
    )
    """
)


async def seed(records: list[dict], *, keep_manual: bool) -> int:
    if not records:
        print("seed file is empty", file=sys.stderr)
        return 1

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        if keep_manual:
            # Curated rows are the ones OSM does not have. Never clear them.
            result = await session.execute(
                text("DELETE FROM landmarks WHERE source <> 'manual'")
            )
            print(f"removed {result.rowcount} previously seeded rows")
        else:
            await session.execute(text("TRUNCATE landmarks"))
            print("truncated landmarks")

        inserted = 0
        for start in range(0, len(records), BATCH):
            chunk = records[start : start + BATCH]
            await session.execute(
                INSERT_SQL,
                [
                    {
                        "name": r["name"],
                        "aliases": r.get("aliases") or [],
                        "kind": r["kind"],
                        "city": r["city"],
                        "quartier": r.get("quartier"),
                        "lat": r["lat"],
                        "lng": r["lng"],
                        "popularity": r.get("popularity", 20),
                        "source": r.get("source", "osm"),
                        "osm_id": r.get("osm_id"),
                    }
                    for r in chunk
                ],
            )
            inserted += len(chunk)
            print(f"  inserted {inserted}/{len(records)}", end="\r")

        await session.commit()
        print(f"\ninserted {inserted} landmarks")

        counts = await session.execute(
            text(
                "SELECT kind::text, count(*) FROM landmarks "
                "GROUP BY kind ORDER BY count(*) DESC"
            )
        )
        for kind, count in counts:
            print(f"  {kind:<12} {count}")

        # The search vector is trigger-maintained, so a row with a null vector
        # means the trigger did not fire and every full-text match will miss.
        missing = await session.scalar(
            text("SELECT count(*) FROM landmarks WHERE search_vec IS NULL")
        )
        if missing:
            print(f"\n{missing} rows have no search vector", file=sys.stderr)
            return 1
        print("\nall rows have a search vector")

    return 0


async def _run(records: list[dict], *, keep_manual: bool) -> int:
    try:
        return await seed(records, keep_manual=keep_manual)
    finally:
        await dispose_engine()


def main() -> int:
    """Argument parsing and file reading stay synchronous.

    Reading the seed file inside the event loop would block it. It happens to
    be the only task on that loop here, but the habit is what matters: the same
    pattern inside a request handler stalls every other request on the worker.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="data/landmarks.seed.json")
    parser.add_argument(
        "--replace-all",
        action="store_true",
        help="Also delete hand-curated rows. Off by default.",
    )
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"seed file not found: {path}", file=sys.stderr)
        print("run scripts/build_gazetteer.py first", file=sys.stderr)
        return 1

    records = json.loads(path.read_text(encoding="utf-8"))
    return asyncio.run(_run(records, keep_manual=not args.replace_all))


if __name__ == "__main__":
    raise SystemExit(main())
