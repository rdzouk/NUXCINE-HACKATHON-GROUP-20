"""Landmark resolution. This is Bet 1.

People here navigate by carrefours, stations, markets and quartiers, not by
street addresses. So the cascade below is ordered by how confident each layer
is, and every result reports which layer produced it, so the client can show
provenance instead of guessing confidently and being wrong.

    exact_alias      the query is a name or alias, accent- and case-folded.
                     Highest confidence: somebody typed the name of a place.
    fuzzy_landmark   trigram similarity plus full-text match. Catches
                     misspelling ("carefour warda"), word order ("marche
                     mokolo"), and partial names.
    quartier         no landmark matched, but the query names a neighbourhood.
                     Lower confidence and a coarser point, flagged as such.
    street_fallback  nothing in the gazetteer matched.

All of it runs in Postgres against an index. Fuzzy matching in Python would
mean pulling the table into the process on every keystroke, which is why
neither rapidfuzz nor thefuzz appears anywhere in this build.

**On SQL injection.** The search term reaches `to_tsquery` only as a bind
parameter, never through string formatting, and `websearch_to_tsquery` is used
rather than `to_tsquery` because it accepts arbitrary human input without
raising on unbalanced quotes or stray operators. `to_tsquery('a & |')` is a
syntax error the user can trigger by typing punctuation; `websearch_to_tsquery`
just handles it.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.schemas.places import LandmarkKind, MatchType, PlaceResult

# Below this trigram similarity a "match" is noise. Tuned against the fixture
# set in scripts/geo_eval.py rather than guessed.
TRIGRAM_THRESHOLD = 0.28

MAX_QUERY_LEN = 120


@dataclass(frozen=True)
class NearPoint:
    lat: float
    lng: float


def parse_near(raw: str | None) -> NearPoint | None:
    """Parse a `lat,lng` bias parameter. Returns None rather than raising.

    A malformed bias should not fail the search: the user typed a place name
    and deserves results, biased or not.
    """
    if not raw:
        return None
    try:
        lat_s, lng_s = raw.split(",", 1)
        lat, lng = float(lat_s), float(lng_s)
    except (ValueError, AttributeError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return NearPoint(lat=lat, lng=lng)


def in_service_area(lat: float, lng: float) -> bool:
    """Whether a point is inside the served bounding region.

    A bounding box, not a polygon, and that is a deliberate simplification: the
    served area is two cities and the box that contains them admits some
    unserved countryside between. The cost of that is a ride request we cannot
    fill; the cost of a polygon is an hour of boundary data we do not have.
    Recorded as an accepted risk rather than presented as precise.
    """
    min_lng, min_lat, max_lng, max_lat = settings.service_area_bounds
    return min_lat <= lat <= max_lat and min_lng <= lng <= max_lng


def require_service_area(lat: float, lng: float, *, field: str) -> None:
    if not in_service_area(lat, lng):
        raise VoraError(
            ErrorCode.OUTSIDE_SERVICE_AREA,
            details={"field": field, "lat": lat, "lng": lng},
        )


def normalise_query(raw: str) -> str:
    return " ".join((raw or "").strip().split())[:MAX_QUERY_LEN]


# One statement for the whole cascade.
#
# Written as a single UNION rather than four sequential queries because the
# layers have to be ranked against each other: an exact alias hit must beat a
# fuzzy hit on a different row, and running them separately would mean either
# four round trips or losing that ordering. `layer_rank` encodes the cascade
# order and sorts first; everything after it is within-layer ranking.
#
# Every user-supplied value is a bind parameter. Nothing is formatted in.
_SEARCH_SQL = text(
    """
WITH q AS (
    SELECT
        vora_unaccent(lower(:query)) AS folded,
        websearch_to_tsquery('simple', vora_unaccent(lower(:query))) AS tsq
),
exact_alias AS (
    SELECT l.*, 1 AS layer_rank, 1.0::float AS score,
           'exact_alias' AS match_type,
           l.name AS matched_alias
    FROM landmarks l, q
    WHERE vora_unaccent(lower(l.name)) = q.folded
       OR EXISTS (
            SELECT 1 FROM unnest(l.aliases) AS a
            WHERE vora_unaccent(lower(a)) = q.folded
       )
),
fuzzy AS (
    SELECT l.*, 2 AS layer_rank,
           GREATEST(
               similarity(vora_unaccent(lower(l.name)), q.folded),
               similarity(
                   vora_unaccent(lower(array_to_string(l.aliases, ' '))), q.folded
               ),
               CASE WHEN l.search_vec @@ q.tsq
                    THEN 0.5 + ts_rank(l.search_vec, q.tsq)
                    ELSE 0 END
           )::float AS score,
           'fuzzy_landmark' AS match_type,
           l.name AS matched_alias
    FROM landmarks l, q
    WHERE l.kind <> 'quartier'
      AND (
            l.search_vec @@ q.tsq
         OR vora_unaccent(lower(l.name)) % q.folded
         OR vora_unaccent(lower(array_to_string(l.aliases, ' '))) % q.folded
         OR vora_unaccent(lower(l.name)) LIKE '%' || q.folded || '%'
      )
),
quartier AS (
    SELECT l.*, 3 AS layer_rank,
           GREATEST(
               similarity(vora_unaccent(lower(l.name)), q.folded),
               CASE WHEN l.search_vec @@ q.tsq THEN 0.6 ELSE 0 END
           )::float AS score,
           'quartier' AS match_type,
           l.name AS matched_alias
    FROM landmarks l, q
    WHERE l.kind = 'quartier'
      AND (
            l.search_vec @@ q.tsq
         OR vora_unaccent(lower(l.name)) % q.folded
         OR vora_unaccent(lower(l.name)) LIKE '%' || q.folded || '%'
      )
),
merged AS (
    SELECT * FROM exact_alias
    UNION ALL SELECT * FROM fuzzy
    UNION ALL SELECT * FROM quartier
),
deduped AS (
    -- One row per landmark, keeping its best layer. Without this a place whose
    -- name is also an alias appears twice in the results.
    SELECT DISTINCT ON (id) *
    FROM merged
    ORDER BY id, layer_rank, score DESC
)
SELECT
    id, name, kind, city, quartier, popularity, match_type, matched_alias, score,
    ST_Y(geom::geometry) AS lat,
    ST_X(geom::geometry) AS lng,
    CASE WHEN :has_near
         THEN ST_Distance(geom, ST_MakePoint(:near_lng, :near_lat)::geography)
         ELSE NULL END AS distance_m
FROM deduped
WHERE score >= :threshold OR layer_rank = 1
ORDER BY
    layer_rank,
    -- Popularity breaks ties before proximity: a well-known carrefour is more
    -- likely meant than an unknown shop that happens to be nearer.
    score DESC,
    popularity DESC,
    CASE WHEN :has_near
         THEN ST_Distance(geom, ST_MakePoint(:near_lng, :near_lat)::geography)
         ELSE 0 END ASC
LIMIT :limit
"""
)


async def search_places(
    session: AsyncSession,
    *,
    query: str,
    near: NearPoint | None = None,
    limit: int = 8,
) -> list[PlaceResult]:
    """Resolve a query through the cascade. Empty list means street fallback."""
    cleaned = normalise_query(query)
    if not cleaned:
        return []

    result = await session.execute(
        _SEARCH_SQL,
        {
            "query": cleaned,
            "threshold": TRIGRAM_THRESHOLD,
            "limit": min(max(limit, 1), 20),
            "has_near": near is not None,
            "near_lat": near.lat if near else 0.0,
            "near_lng": near.lng if near else 0.0,
        },
    )

    return [
        PlaceResult(
            id=str(row.id),
            name=row.name,
            kind=LandmarkKind(row.kind),
            quartier=row.quartier,
            city=row.city,
            lat=row.lat,
            lng=row.lng,
            distance_m=int(row.distance_m) if row.distance_m is not None else None,
            match_type=MatchType(row.match_type),
            matched_alias=row.matched_alias,
        )
        for row in result
    ]


_REVERSE_SQL = text(
    """
    SELECT id, name, kind, city, quartier, popularity,
           ST_Y(geom::geometry) AS lat,
           ST_X(geom::geometry) AS lng,
           ST_Distance(geom, ST_MakePoint(:lng, :lat)::geography) AS distance_m
    FROM landmarks
    -- ST_DWithin against the GiST index, not an ORDER BY over the whole table.
    WHERE ST_DWithin(geom, ST_MakePoint(:lng, :lat)::geography, :radius_m)
    ORDER BY geom <-> ST_MakePoint(:lng, :lat)::geography
    LIMIT 1
    """
)

REVERSE_RADIUS_M = 1500


async def reverse_geocode(
    session: AsyncSession, *, lat: float, lng: float
) -> tuple[PlaceResult | None, str]:
    """Describe a coordinate the way a person would.

    Returns (nearest landmark or None, a human label). The label names the
    landmark and how far away it is, because "200 m from Carrefour Warda" is
    how somebody would actually give this location to a driver.
    """
    result = await session.execute(
        _REVERSE_SQL, {"lat": lat, "lng": lng, "radius_m": REVERSE_RADIUS_M}
    )
    row = result.first()

    if row is None:
        return None, "Position actuelle"

    place = PlaceResult(
        id=str(row.id),
        name=row.name,
        kind=LandmarkKind(row.kind),
        quartier=row.quartier,
        city=row.city,
        lat=row.lat,
        lng=row.lng,
        distance_m=int(row.distance_m),
        match_type=MatchType.EXACT_ALIAS,
        matched_alias=row.name,
    )

    distance = int(row.distance_m)
    if distance <= 120:
        label = row.name
    else:
        label = f"{distance} m de {row.name}"

    return place, label
