#!/usr/bin/env python3
"""Gazetteer hit-rate evaluation. Phase 2 acceptance check.

    python scripts/geo_eval.py                    # against the local stack
    python scripts/geo_eval.py --base https://... # against the deployment

Prints a top-3 hit rate. The build plan wants at least 85 percent.

**On the honesty of this number.** The fixtures below are written from how
people in Yaounde actually name places, not by reading the seed file and
copying names out of it. Matching is by *expected substring* rather than by
landmark id, for two reasons: ids change on every reseed, and a fixture keyed
to an id can only ever confirm that the row it was written from still exists.
A substring expectation states the user's intent ("typing this should find
Warda") independently of what the gazetteer happens to contain.

That still leaves one bias worth naming out loud: the same person wrote the
extractor and these fixtures. The number is a real measurement of the cascade,
not an independent audit of coverage. Getting a teammate who has not seen the
seed data to write a second fixture file is the honest next step, and it costs
twenty minutes.

Categories, so a failure says something specific:
  exact        the name as written                 -> exact_alias expected
  shortened    how people actually shorten it      -> alias layer
  misspelled   realistic typos and phonetic spelling -> trigram layer
  accents      written with and without accents    -> unaccent handling
  reordered    words in a different order          -> tsvector layer
  quartier     a neighbourhood, not a landmark     -> quartier layer
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from dataclasses import dataclass

import httpx

GREEN, RED, YELLOW, DIM, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
)


@dataclass(frozen=True)
class Fixture:
    query: str
    expect: str  # case- and accent-insensitive substring of the expected name
    category: str


# Roughly forty queries covering how these places are actually typed.
FIXTURES: list[Fixture] = [
    # Exact names.
    Fixture("Carrefour Warda", "warda", "exact"),
    Fixture("Nlongkak", "nlongkak", "exact"),
    Fixture("Mokolo", "mokolo", "exact"),
    Fixture("Bastos", "bastos", "exact"),
    Fixture("Nsimeyong", "nsimeyong", "exact"),
    Fixture("Biyem-Assi", "biyem", "exact"),
    Fixture("Mvog-Mbi", "mvog", "exact"),
    Fixture("Obili", "obili", "exact"),
    Fixture("Melen", "melen", "exact"),
    Fixture("Essos", "essos", "exact"),
    # Shortened, the qualifier dropped.
    Fixture("warda", "warda", "shortened"),
    Fixture("mokolo market", "mokolo", "shortened"),
    Fixture("marche mokolo", "mokolo", "shortened"),
    Fixture("poste centrale", "poste", "shortened"),
    Fixture("total nsimeyong", "nsimeyong", "shortened"),
    Fixture("carrefour obili", "obili", "shortened"),
    Fixture("rond point nlongkak", "nlongkak", "shortened"),
    # Misspelled, phonetic, or missing letters.
    Fixture("carefour warda", "warda", "misspelled"),
    Fixture("carrefor warda", "warda", "misspelled"),
    Fixture("nsimeyon", "nsimeyong", "misspelled"),
    Fixture("bieym assi", "biyem", "misspelled"),
    Fixture("nlonkak", "nlongkak", "misspelled"),
    Fixture("mokol", "mokolo", "misspelled"),
    Fixture("bastoss", "bastos", "misspelled"),
    Fixture("melenn", "melen", "misspelled"),
    # Accents present or absent.
    Fixture("marche central", "central", "accents"),
    Fixture("marché central", "central", "accents"),
    Fixture("hopital central", "central", "accents"),
    Fixture("hôpital central", "central", "accents"),
    Fixture("universite yaounde", "universit", "accents"),
    Fixture("université yaoundé", "universit", "accents"),
    # Word order and mixed language.
    Fixture("warda carrefour", "warda", "reordered"),
    Fixture("central market", "central", "reordered"),
    Fixture("station total", "total", "reordered"),
    # Quartiers rather than landmarks.
    Fixture("ngoa ekelle", "ngoa", "quartier"),
    Fixture("ngoa-ekelle", "ngoa", "quartier"),
    Fixture("mvan", "mvan", "quartier"),
    Fixture("odza", "odza", "quartier"),
    Fixture("etoudi", "etoudi", "quartier"),
    Fixture("mendong", "mendong", "quartier"),
    Fixture("nkolbisson", "nkolbisson", "quartier"),
    Fixture("emana", "emana", "quartier"),
]


def fold(value: str) -> str:
    stripped = "".join(
        c
        for c in unicodedata.normalize("NFD", value)
        if unicodedata.category(c) != "Mn"
    )
    return stripped.lower()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8080/api/v1")
    parser.add_argument("--top", type=int, default=3, help="Top-N to count as a hit.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    client = httpx.Client(timeout=30.0)

    hits = 0
    misses: list[tuple[Fixture, list[str]]] = []
    by_category: dict[str, list[int]] = {}
    match_types: dict[str, int] = {}

    print(f"gazetteer evaluation against {base}")
    print(f"{DIM}{len(FIXTURES)} queries, top-{args.top} counts as a hit{RESET}\n")

    for fixture in FIXTURES:
        try:
            response = client.get(
                f"{base}/places/search",
                params={"q": fixture.query, "limit": args.top},
            )
            response.raise_for_status()
            results = response.json()["results"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            print(f"{RED}  request failed for {fixture.query!r}: {exc}{RESET}")
            results = []

        names = [r["name"] for r in results[: args.top]]
        hit = any(fixture.expect in fold(name) for name in names)

        by_category.setdefault(fixture.category, []).append(1 if hit else 0)
        if results:
            match_types[results[0]["match_type"]] = (
                match_types.get(results[0]["match_type"], 0) + 1
            )

        if hit:
            hits += 1
            if args.verbose:
                mt = results[0]["match_type"] if results else "-"
                print(f"{GREEN}  hit {RESET} {fixture.query!r} -> {names[0]} [{mt}]")
        else:
            misses.append((fixture, names))

    total = len(FIXTURES)
    rate = hits / total * 100

    if misses:
        print(f"{YELLOW}misses{RESET}")
        for fixture, names in misses:
            got = ", ".join(names[:3]) if names else "no results"
            print(f"  {fixture.query!r} ({fixture.category}) expected ~{fixture.expect}")
            print(f"{DIM}      got: {got}{RESET}")
        print()

    print("by category")
    for category, outcomes in sorted(by_category.items()):
        got = sum(outcomes)
        pct = got / len(outcomes) * 100
        colour = GREEN if pct >= 85 else (YELLOW if pct >= 60 else RED)
        print(f"  {category:<12} {colour}{got}/{len(outcomes)}  {pct:5.1f}%{RESET}")

    if match_types:
        print("\nwinning layer, top result")
        for name, count in sorted(match_types.items(), key=lambda kv: -kv[1]):
            print(f"  {name:<16} {count}")

    print("\n-----------------------------------------")
    colour = GREEN if rate >= 85 else RED
    print(f"top-{args.top} hit rate: {colour}{hits}/{total}  {rate:.1f}%{RESET}")

    if rate < 85:
        print(f"{RED}below the 85% acceptance threshold{RESET}")
        return 1
    print(f"{GREEN}meets the 85% acceptance threshold{RESET}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except httpx.HTTPError as exc:
        print(f"{RED}transport error: {exc}{RESET}", file=sys.stderr)
        raise SystemExit(2) from exc
