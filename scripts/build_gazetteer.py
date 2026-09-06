#!/usr/bin/env python3
"""Build the landmark gazetteer from the Cameroon OSM extract.

    python scripts/build_gazetteer.py \
        --pbf osrm-data/cameroon-latest.osm.pbf \
        --out data/landmarks.seed.json

This produces the dataset, not the database rows. `scripts/seed_landmarks.py`
loads the output. Keeping them separate means the expensive parse runs once and
its result is committed, so a teammate can seed a fresh database without a
213 MB download.

**Why generate aliases rather than take OSM names verbatim.** OSM records
"Carrefour Warda" once. People type "warda", "carefour warda", "rond point
warda". The alias list is what turns one OSM row into the several things a
person might actually say, and it is the reason the exact-alias layer of the
cascade hits at all. This generation is the curation step the build plan calls
a deliverable in its own right.

`pyosmium` streams the file rather than loading it, so peak memory stays low
even though the input is 213 MB.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import osmium

# Yaounde and Douala, generously bounded. Everything outside is dropped: the
# service area is two cities, and a gazetteer full of places we do not serve
# makes every search worse.
BBOX = {
    "min_lat": 3.60,
    "max_lat": 4.20,
    "min_lng": 9.55,
    "max_lng": 11.75,
}

# Rough city centres, used only to attribute a landmark to a city.
CITIES = {
    "Yaounde": (3.8480, 11.5021),
    "Douala": (4.0511, 9.7679),
}

# OSM tags to landmark kinds. Ordered: the first match wins, so a hospital
# tagged also as a building is a hospital.
KIND_RULES: list[tuple[str, str, str]] = [
    ("highway", "motorway_junction", "carrefour"),
    ("junction", "roundabout", "carrefour"),
    ("highway", "traffic_signals", "carrefour"),
    ("amenity", "hospital", "hospital"),
    ("amenity", "clinic", "hospital"),
    ("amenity", "doctors", "hospital"),
    ("amenity", "pharmacy", "business"),
    ("amenity", "school", "school"),
    ("amenity", "college", "school"),
    ("amenity", "university", "school"),
    ("amenity", "kindergarten", "school"),
    ("amenity", "fuel", "station"),
    ("amenity", "bus_station", "station"),
    ("amenity", "taxi", "station"),
    ("amenity", "marketplace", "market"),
    ("amenity", "townhall", "admin"),
    ("amenity", "police", "admin"),
    ("amenity", "post_office", "admin"),
    ("amenity", "courthouse", "admin"),
    ("amenity", "embassy", "admin"),
    ("amenity", "bank", "business"),
    ("amenity", "restaurant", "business"),
    ("amenity", "cafe", "business"),
    ("amenity", "bar", "business"),
    ("amenity", "place_of_worship", "admin"),
    ("shop", "supermarket", "business"),
    ("shop", "mall", "business"),
    ("shop", "convenience", "business"),
    ("public_transport", "station", "station"),
    ("railway", "station", "station"),
    ("office", "government", "admin"),
    ("tourism", "hotel", "business"),
    ("place", "suburb", "quartier"),
    ("place", "neighbourhood", "quartier"),
    ("place", "quarter", "quartier"),
    ("place", "village", "quartier"),
    ("place", "town", "quartier"),
]

# Ranking weight per kind. A carrefour or a quartier is far more likely to be
# what somebody means than a particular cafe.
KIND_POPULARITY = {
    "carrefour": 90,
    "quartier": 85,
    "market": 80,
    "station": 70,
    "hospital": 65,
    "admin": 55,
    "school": 50,
    "business": 25,
}

# Words that make a name a landmark people navigate by. A place called
# "Carrefour X" or "Total X" is a reference point even if OSM tags it as a
# generic business.
LANDMARK_PREFIXES = (
    "carrefour", "rond-point", "rond point", "marche", "market", "gare",
    "station", "total", "tradex", "neptune", "camerounaise", "poste",
    "hopital", "lycee", "college", "universite", "stade", "place",
)


def strip_accents(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn"
    )


def in_bbox(lat: float, lng: float) -> bool:
    return (
        BBOX["min_lat"] <= lat <= BBOX["max_lat"]
        and BBOX["min_lng"] <= lng <= BBOX["max_lng"]
    )


def nearest_city(lat: float, lng: float) -> str:
    return min(
        CITIES,
        key=lambda c: (lat - CITIES[c][0]) ** 2 + (lng - CITIES[c][1]) ** 2,
    )


def classify(tags: dict[str, str]) -> str | None:
    for key, value, kind in KIND_RULES:
        if tags.get(key) == value:
            return kind
    return None


def generate_aliases(name: str) -> list[str]:
    """The several things a person might type for one place.

    This is the curation that makes the gazetteer work. Each rule below exists
    because it is how people actually shorten or vary a name in speech:

      "Carrefour Warda"        -> "Warda"        (the qualifier is dropped)
      "Rond-point Nlongkak"    -> "Nlongkak"
      "Total Nsimeyong"        -> "Nsimeyong", "Total Nsimeyong"
      "Marche Central"         -> "Marche Central", "Central"
      "Ngoa-Ekelle"            -> "Ngoa Ekelle"  (hyphen typed as a space)
    """
    aliases: set[str] = {name}
    folded = strip_accents(name)
    if folded != name:
        aliases.add(folded)

    # Hyphen and space are interchangeable when typed.
    if "-" in name:
        aliases.add(name.replace("-", " "))
        aliases.add(strip_accents(name.replace("-", " ")))

    lower = folded.lower()
    for prefix in LANDMARK_PREFIXES:
        if lower.startswith(prefix + " "):
            bare = name[len(prefix) + 1 :].strip()
            if len(bare) >= 3:
                aliases.add(bare)
                aliases.add(strip_accents(bare))
                # "Carrefour Warda" is also said as "Warda carrefour".
                aliases.add(f"{bare} {name[: len(prefix)]}".strip())
            break

    # A parenthesised qualifier is rarely spoken: "Obili (Yaounde)" -> "Obili".
    stripped = re.sub(r"\s*\([^)]*\)", "", name).strip()
    if stripped and stripped != name and len(stripped) >= 3:
        aliases.add(stripped)

    return sorted({a for a in aliases if len(a) >= 2})


class LandmarkCollector(osmium.SimpleHandler):
    """Streams nodes, ways and areas, keeping anything named and classifiable."""

    def __init__(self) -> None:
        super().__init__()
        self.records: dict[str, dict] = {}
        self.seen_names: Counter[str] = Counter()
        self.skipped_unnamed = 0
        self.skipped_outside = 0

    def _consider(self, osm_obj, lat: float, lng: float, osm_type: str) -> None:
        tags = {t.k: t.v for t in osm_obj.tags}

        name = tags.get("name") or tags.get("name:fr") or tags.get("name:en")
        if not name or len(name.strip()) < 2:
            self.skipped_unnamed += 1
            return

        if not in_bbox(lat, lng):
            self.skipped_outside += 1
            return

        kind = classify(tags)
        if kind is None:
            return

        name = name.strip()
        # Deduplicate by name plus rounded position: OSM frequently holds the
        # same place as both a node and a building polygon.
        key = f"{strip_accents(name).lower()}|{round(lat, 3)}|{round(lng, 3)}"
        if key in self.records:
            return

        popularity = KIND_POPULARITY.get(kind, 20)
        lowered = strip_accents(name).lower()
        if any(lowered.startswith(p) for p in LANDMARK_PREFIXES):
            # Named like a reference point, so rank it like one regardless of
            # how OSM happened to tag it.
            popularity = max(popularity, 75)

        self.records[key] = {
            "name": name,
            "aliases": generate_aliases(name),
            "kind": kind,
            "city": nearest_city(lat, lng),
            "quartier": tags.get("addr:suburb") or tags.get("addr:neighbourhood"),
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "popularity": popularity,
            "source": "osm",
            "osm_id": f"{osm_type}/{osm_obj.id}",
        }
        self.seen_names[kind] += 1

    def node(self, n) -> None:
        # Nodes only, and deliberately so.
        #
        # Handling ways and areas as well would need a node-location index for
        # the whole country, which on this 5 GB box climbed past 3 GB and was
        # still running after several minutes. Nodes carry their own
        # coordinates, so this pass needs no index and finishes in seconds.
        #
        # What that costs: a place mapped only as a building polygon and not
        # as a point is missed. In practice OSM contributors tag Cameroonian
        # POIs overwhelmingly as nodes, and the categories that matter most
        # here (carrefours, fuel stations, markets, quartiers) are nodes by
        # convention. The gap is covered by the curated supplement.
        if n.location.valid():
            self._consider(n, n.location.lat, n.location.lon, "node")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pbf", default="osrm-data/cameroon-latest.osm.pbf")
    parser.add_argument("--out", default="data/landmarks.seed.json")
    parser.add_argument(
        "--min-records",
        type=int,
        default=300,
        help="Fail if fewer than this many landmarks survive. The build plan "
        "requires 300 to 500; a silent under-run would show up as a bad "
        "hit rate much later.",
    )
    args = parser.parse_args()

    pbf = Path(args.pbf)
    if not pbf.exists():
        print(f"extract not found: {pbf}", file=sys.stderr)
        return 1

    print(f"reading {pbf} ({pbf.stat().st_size / 1e6:.0f} MB)")
    collector = LandmarkCollector()
    # No `locations=True`: nodes carry their own coordinates, and building the
    # country-wide location index is what made the earlier attempt exhaust memory.
    collector.apply_file(str(pbf))

    records = sorted(
        collector.records.values(), key=lambda r: (-r["popularity"], r["name"])
    )

    print(f"\nkept {len(records)} landmarks")
    for kind, count in collector.seen_names.most_common():
        print(f"  {kind:<12} {count}")
    by_city = Counter(r["city"] for r in records)
    for city, count in by_city.most_common():
        print(f"  {city:<12} {count}")

    if len(records) < args.min_records:
        print(
            f"\nonly {len(records)} landmarks, expected at least {args.min_records}",
            file=sys.stderr,
        )
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
