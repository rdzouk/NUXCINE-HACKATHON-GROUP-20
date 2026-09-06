"""Landmark geocoding routes. Implemented in Phase 2. This is Bet 1."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.v1._stub import PUBLIC_ERRORS, not_implemented
from app.schemas.common import Latitude, Longitude
from app.schemas.places import PlaceSearchResponse, ReverseGeocodeResponse

router = APIRouter(prefix="/places", tags=["places"])


@router.get(
    "/search",
    response_model=PlaceSearchResponse,
    responses=PUBLIC_ERRORS,
    summary="Resolve a landmark by name",
    description=(
        "Layered cascade: exact alias, then fuzzy landmark match (trigram plus "
        "tsvector, accent-insensitive, tolerant of French, English and pidgin "
        "mixing), then quartier, then street fallback. The winning layer is "
        "returned as `match_type` so the client can show provenance."
    ),
)
async def search_places(
    q: str = Query(min_length=1, max_length=120, examples=["carefour warda"]),
    near: str | None = Query(
        default=None,
        pattern=r"^-?\d{1,3}(\.\d+)?,-?\d{1,3}(\.\d+)?$",
        description="lat,lng to bias and measure results from.",
        examples=["3.848,11.502"],
    ),
    limit: int = Query(default=8, ge=1, le=20),
) -> PlaceSearchResponse:
    not_implemented("Phase 2")


@router.get(
    "/reverse",
    response_model=ReverseGeocodeResponse,
    responses=PUBLIC_ERRORS,
    summary="Describe a coordinate the way a person would",
)
async def reverse_geocode(
    lat: Latitude = Query(...),
    lng: Longitude = Query(...),
) -> ReverseGeocodeResponse:
    not_implemented("Phase 2")
