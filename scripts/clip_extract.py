#!/usr/bin/env python3
"""Clip the country OSM extract to the served region.

    python scripts/clip_extract.py \
        --pbf osrm-data/cameroon-latest.osm.pbf \
        --out osrm-data/region.osm.pbf

Exists because `osrm-extract` on the whole 223 MB Cameroon file exhausted this
host and the Linux OOM killer took **Postgres** with it. The API stayed up on
the haversine fallback, which is the degradation path working as designed, but
losing the database to a preprocessing job is not acceptable.

The usual tool for this is `osmium extract --bbox`. No working osmium image was
reachable, so this does the same job with pyosmium, which is already a
dependency of the gazetteer build.

**Reference completeness is the whole difficulty.** A routing graph needs every
node referenced by a kept way, including nodes that fall outside the box. Drop
those and OSRM builds a graph full of broken geometry, which fails in the worst
way: it loads, answers, and routes wrongly. So this runs two passes.

  pass 1  read ways. Keep any highway whose name suggests it is routable and
          that has at least one node inside the box, and record every node id
          it references.
  pass 2  write out those nodes (wherever they are) plus the kept ways.

The box is padded so that a road crossing the boundary keeps enough of its
geometry to remain connected.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import osmium

# Padding in degrees, roughly 5 km. A road leaving the box needs some length
# beyond it, or the graph ends in dangling stubs at the boundary.
PAD = 0.05

# Way tags worth keeping for a car routing graph. Anything else is scenery.
ROUTABLE_HIGHWAYS = {
    "motorway", "motorway_link", "trunk", "trunk_link",
    "primary", "primary_link", "secondary", "secondary_link",
    "tertiary", "tertiary_link", "unclassified", "residential",
    "living_street", "service", "road", "track",
}


class WayCollector(osmium.SimpleHandler):
    """Pass 1: decide which ways to keep and collect their node ids."""

    def __init__(self, bbox: tuple[float, float, float, float]) -> None:
        super().__init__()
        self.min_lng, self.min_lat, self.max_lng, self.max_lat = bbox
        self.way_ids: set[int] = set()
        self.node_ids: set[int] = set()
        self.seen = 0

    def way(self, w) -> None:
        self.seen += 1
        if w.tags.get("highway") not in ROUTABLE_HIGHWAYS:
            return
        # Node locations are not available without a location index, so
        # membership is decided in pass 2 by which nodes actually land inside.
        # Here every routable way is a candidate and gets filtered by whether
        # any of its nodes survive.
        refs = [n.ref for n in w.nodes]
        if not refs:
            return
        self.way_ids.add(w.id)
        self.node_ids.update(refs)


class NodeSelector(osmium.SimpleHandler):
    """Pass 2a: of the referenced nodes, which lie inside the padded box."""

    def __init__(self, wanted: set[int], bbox: tuple[float, float, float, float]) -> None:
        super().__init__()
        self.wanted = wanted
        self.min_lng, self.min_lat, self.max_lng, self.max_lat = bbox
        self.inside: set[int] = set()

    def node(self, n) -> None:
        if n.id not in self.wanted or not n.location.valid():
            return
        if (
            self.min_lat <= n.location.lat <= self.max_lat
            and self.min_lng <= n.location.lon <= self.max_lng
        ):
            self.inside.add(n.id)


class Writer(osmium.SimpleHandler):
    """Pass 3: write the kept nodes and ways."""

    def __init__(self, writer, node_ids: set[int], way_ids: set[int]) -> None:
        super().__init__()
        self.writer = writer
        self.node_ids = node_ids
        self.way_ids = way_ids
        self.nodes_written = 0
        self.ways_written = 0

    def node(self, n) -> None:
        if n.id in self.node_ids and n.location.valid():
            self.writer.add_node(n)
            self.nodes_written += 1

    def way(self, w) -> None:
        if w.id in self.way_ids:
            self.writer.add_way(w)
            self.ways_written += 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pbf", default="osrm-data/cameroon-latest.osm.pbf")
    parser.add_argument("--out", default="osrm-data/region.osm.pbf")
    parser.add_argument(
        "--bbox",
        default="9.55,3.60,11.75,4.20",
        help="min_lng,min_lat,max_lng,max_lat",
    )
    args = parser.parse_args()

    source = Path(args.pbf)
    if not source.exists():
        print(f"extract not found: {source}", file=sys.stderr)
        return 1

    raw = [float(v) for v in args.bbox.split(",")]
    if len(raw) != 4:
        print("bbox must be min_lng,min_lat,max_lng,max_lat", file=sys.stderr)
        return 1
    bbox = (raw[0] - PAD, raw[1] - PAD, raw[2] + PAD, raw[3] + PAD)

    print(f"clipping {source} to {bbox} (padded by {PAD} deg)")

    print("pass 1: selecting routable ways")
    ways = WayCollector(bbox)
    ways.apply_file(str(source))
    print(f"  {len(ways.way_ids)} routable ways of {ways.seen} seen")
    print(f"  {len(ways.node_ids)} referenced nodes")

    print("pass 2: locating those nodes")
    nodes = NodeSelector(ways.node_ids, bbox)
    nodes.apply_file(str(source))
    print(f"  {len(nodes.inside)} lie inside the box")

    if not nodes.inside:
        print("nothing inside the box; check the bbox order", file=sys.stderr)
        return 1

    # Keep a way only if it has a node inside, then keep *every* node of that
    # way, including ones outside the box. That is what preserves connectivity
    # at the boundary rather than leaving broken geometry.
    print("pass 3: reselecting ways with a node inside")
    keep_ways: set[int] = set()
    keep_nodes: set[int] = set()

    class Reselect(osmium.SimpleHandler):
        def way(self, w) -> None:
            if w.id not in ways.way_ids:
                return
            refs = [n.ref for n in w.nodes]
            if any(r in nodes.inside for r in refs):
                keep_ways.add(w.id)
                keep_nodes.update(refs)

    Reselect().apply_file(str(source))
    print(f"  keeping {len(keep_ways)} ways and {len(keep_nodes)} nodes")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    print(f"pass 4: writing {out}")
    writer = osmium.SimpleWriter(str(out))
    try:
        handler = Writer(writer, keep_nodes, keep_ways)
        handler.apply_file(str(source))
    finally:
        writer.close()

    before = source.stat().st_size / 1e6
    after = out.stat().st_size / 1e6
    print(
        f"\nwrote {out}: {handler.nodes_written} nodes, "
        f"{handler.ways_written} ways"
    )
    print(f"{before:.0f} MB -> {after:.1f} MB ({before / max(after, 0.1):.0f}x smaller)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
