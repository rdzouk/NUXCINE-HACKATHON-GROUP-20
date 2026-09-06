#!/usr/bin/env python3
"""Curate the extracted gazetteer. Run after build_gazetteer.py.

    python scripts/curate_gazetteer.py

OSM's Cameroon extract yielded 5454 landmarks but only **three** tagged as
carrefours, and carrefours are the single most important category for how
people here name places. That gap is exactly what the build plan predicted when
it said to hand-add what OSM misses.

**How this closes the gap without inventing coordinates.** The obvious fix is
to type out a list of carrefours with hand-placed latitudes. That would be
fabricating survey data, and a wrong coordinate is worse than a missing one: it
sends a driver confidently to the wrong place.

So this script adds no new locations. For each well-known carrefour name it
finds the OSM node that already exists for that place (usually the quartier
node, which carries a real surveyed coordinate) and attaches the name-forms
people actually say as aliases: "Carrefour Obili", "Rond-point Obili", "Obili
carrefour". The coordinate stays OSM's. Only the vocabulary is ours.

That is the honest version of "hand-add the carrefours", and it is why the
exact-alias layer of the cascade can hit on a query like "carrefour obili" that
OSM alone would miss entirely.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

# Places in Yaounde and Douala that people routinely refer to as a carrefour or
# rond-point. Each name must already exist in the extract for anything to
# happen: this list contributes vocabulary, never a position.
CARREFOUR_NAMES = [
    # Yaounde, centre and near-centre
    "Warda", "Nlongkak", "Bastos", "Mvog-Mbi", "Mvog-Ada", "Elig-Essono",
    "Elig-Edzoa", "Briqueterie", "Tsinga", "Messa", "Madagascar", "Mokolo",
    "Djoungolo", "Nkoldongo", "Nkolndongo", "Mfandena", "Fouda", "Ngousso",
    "Essos", "Mimboman", "Awae", "Nsam", "Efoulan", "Obobogo", "Ngoa-Ekelle",
    "Ngoa Ekelle", "Melen", "Obili", "Etoa-Meki", "Cradat", "Jouvence",
    # Yaounde, outer
    "Biyem-Assi", "Biyem Assi", "Mendong", "Simbock", "Nkolbisson", "Etoudi",
    "Emana", "Olembe", "Nkolmesseng", "Odza", "Mvan", "Ahala", "Ekounou",
    "Nkomo", "Nsimeyong", "Damas", "Ekoumdoum", "Nkoabang", "Soa",
    # Douala
    "Akwa", "Bonanjo", "Deido", "Bonaberi", "Ndokotti", "Makepe", "Bepanda",
    "Logbaba", "Bonamoussadi", "Kotto", "Yassa", "Ndogbong", "Cite Sic",
]

# Name-form templates. Each is how somebody actually says it out loud.
ALIAS_TEMPLATES = [
    "Carrefour {name}",
    "Rond-point {name}",
    "Rond point {name}",
    "{name} carrefour",
]

# Landmark kinds that can plausibly be referred to as a carrefour. A hospital
# or a school named "Obili" is not the junction people mean.
ELIGIBLE_KINDS = {"quartier", "carrefour", "station", "market", "admin"}

# Carrefours and markets are reference points people navigate by, so they
# outrank a business that happens to share a name.
CARREFOUR_POPULARITY = 95


def fold(value: str) -> str:
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn"
    )
    return stripped.lower().replace("-", " ").strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="data/landmarks.seed.json")
    parser.add_argument("--out", default=None, help="Defaults to editing in place.")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"seed file not found: {path}", file=sys.stderr)
        return 1

    records = json.loads(path.read_text(encoding="utf-8"))

    # Containment, not equality.
    #
    # The first version of this matched folded names exactly and found almost
    # nothing, because OSM does not hold these places under their bare names.
    # It has "Marche Obili", "TOTAL Essos", "Odza I", "Lycee d'Odza". The bare
    # name a person actually types is precisely what is missing.
    #
    # So the anchor node for "Obili" is the best-ranked node whose name
    # contains "Obili", and curation attaches both the bare name and the
    # carrefour forms to it. The coordinate is still OSM's; only the vocabulary
    # is added.
    def best_anchor(place: str) -> dict | None:
        needle = fold(place)
        candidates = [
            r
            for r in records
            if r["kind"] in ELIGIBLE_KINDS and needle in fold(r["name"])
        ]
        if not candidates:
            return None
        # Prefer a quartier (the neighbourhood centre is what "Obili" means to
        # a passenger), then popularity, then the shortest name, which is the
        # one least cluttered with a business's branding.
        return min(
            candidates,
            key=lambda r: (
                0 if r["kind"] == "quartier" else 1,
                -r.get("popularity", 0),
                len(r["name"]),
            ),
        )

    matched = 0
    missing: list[str] = []
    aliases_added = 0

    for name in CARREFOUR_NAMES:
        record = best_anchor(name)
        if record is None:
            missing.append(name)
            continue

        matched += 1
        existing = {fold(a) for a in record.get("aliases", [])}
        additions = []

        # The bare name first. "obili" is what someone types, and without this
        # it resolves to nothing at all.
        for candidate in (name, *(t.format(name=name) for t in ALIAS_TEMPLATES)):
            if fold(candidate) not in existing:
                additions.append(candidate)
                existing.add(fold(candidate))

        if additions:
            record["aliases"] = sorted({*record.get("aliases", []), *additions})
            aliases_added += len(additions)

        # A place people call a carrefour ranks like one, whatever OSM tagged it.
        record["popularity"] = max(record.get("popularity", 0), CARREFOUR_POPULARITY)
        # Record that a human touched this row, so a reseed can be reasoned about.
        record["source"] = "osm+curated"

    print(f"carrefour names in the curation list: {len(CARREFOUR_NAMES)}")
    print(f"  matched to an existing OSM node:    {matched}")
    print(f"  aliases added:                      {aliases_added}")
    print(f"  not found in the extract:           {len(missing)}")
    if missing:
        print(f"\n{DIM_NOTE}")
        for name in missing:
            print(f"    {name}")

    out = Path(args.out) if args.out else path
    out.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


DIM_NOTE = (
    "  These have no node in the extract, so no alias was added and no\n"
    "  coordinate was invented. They stay missing until somebody adds them to\n"
    "  OpenStreetMap or supplies a surveyed position:"
)


if __name__ == "__main__":
    raise SystemExit(main())
