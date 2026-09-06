"""Landmark geocoding routes. This is Bet 1's surface.

Rate limited despite being read-only. Each search is several index scans plus
trigram similarity across the gazetteer, and it is reachable without an account
because a passenger types a destination before they have any reason to sign in.
An unlimited endpoint with that cost profile is a denial-of-service primitive
that needs no credentials.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from redis.exceptions import RedisError

from app.api.v1._stub import PUBLIC_ERRORS
from app.deps import ClientIp, SessionDep
from app.logging import get_logger
from app.schemas.common import Latitude, Longitude
from app.schemas.places import PlaceSearchResponse, ReverseGeocodeResponse
from app.services import geocoding
from app.services.rate_limit import PLACES_SEARCH_PER_IP, limiter

router = APIRouter(prefix="/places", tags=["places"])
logger = get_logger("vora.places")


async def _limit(ip: str) -> None:
    """Throttle by IP, failing *open*.

    The opposite choice to the OTP path, and deliberately so. Failing closed
    there protects an SMS budget an attacker can spend. Here the only cost of a
    Redis outage is unthrottled reads of public data, and refusing to geocode
    would stop every passenger from booking. Availability wins.
    """
    try:
        decision = await limiter.consume(PLACES_SEARCH_PER_IP, ip)
    except RedisError:
        logger.warning("places_rate_limiter_unavailable_failing_open")
        return

    if not decision.allowed:
        from app.errors.codes import ErrorCode
        from app.errors.envelope import VoraError

        raise VoraError(
            ErrorCode.RATE_LIMITED,
            details={"retry_after_s": max(decision.retry_after_s, 1)},
        )


@router.get(
    "/search",
    response_model=PlaceSearchResponse,
    responses=PUBLIC_ERRORS,
    summary="Resolve a landmark by name",
    description=(
        "Layered cascade: exact alias, then fuzzy landmark match (trigram plus "
        "tsvector, accent-insensitive, tolerant of French, English and pidgin "
        "mixing), then quartier, then street fallback. The winning layer is "
        "returned as `match_type` so the client can show provenance instead of "
        "presenting a guess with the same confidence as a certainty.\n\n"
        "An empty `results` array means nothing in the gazetteer matched; the "
        "client should offer a map pin rather than an error."
    ),
)
async def search_places(
    session: SessionDep,
    ip: ClientIp,
    q: str = Query(min_length=1, max_length=120, examples=["carefour warda"]),
    near: str | None = Query(
        default=None,
        pattern=r"^-?\d{1,3}(\.\d+)?,-?\d{1,3}(\.\d+)?$",
        description="lat,lng to bias and measure results from.",
        examples=["3.848,11.502"],
    ),
    limit: int = Query(default=8, ge=1, le=20),
) -> PlaceSearchResponse:
    await _limit(ip)
    results = await geocoding.search_places(
        session,
        query=q,
        near=geocoding.parse_near(near),
        limit=limit,
    )
    return PlaceSearchResponse(query=q, results=results)


@router.get(
    "/reverse",
    response_model=ReverseGeocodeResponse,
    responses=PUBLIC_ERRORS,
    summary="Describe a coordinate the way a person would",
    description=(
        "Returns the nearest landmark and a label built from it, such as "
        "'200 m de Carrefour Warda'. That is how somebody actually gives this "
        "location to a driver, and it is more useful than a street name that "
        "may not exist or may not be known."
    ),
)
async def reverse_geocode(
    session: SessionDep,
    ip: ClientIp,
    lat: Latitude = Query(...),
    lng: Longitude = Query(...),
) -> ReverseGeocodeResponse:
    await _limit(ip)
    nearest, label = await geocoding.reverse_geocode(session, lat=lat, lng=lng)
    return ReverseGeocodeResponse(
        label=label,
        nearest_landmark=nearest,
        quartier=nearest.quartier if nearest else None,
        city=nearest.city if nearest else None,
    )
