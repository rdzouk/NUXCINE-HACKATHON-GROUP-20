"""Landmark geocoding contract. This is Bet 1's surface.

`match_type` is returned so the client can show provenance. A result that came
from an exact alias is worth displaying differently from a street fallback, and
being honest about which is which is the difference between a geocoder people
trust and one they stop using after two wrong guesses.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from app.schemas.common import Latitude, Longitude, VoraModel


class LandmarkKind(StrEnum):
    CARREFOUR = "carrefour"
    STATION = "station"
    MARKET = "market"
    SCHOOL = "school"
    HOSPITAL = "hospital"
    ADMIN = "admin"
    BUSINESS = "business"
    QUARTIER = "quartier"


class MatchType(StrEnum):
    """The resolution cascade, in the order it is attempted."""

    EXACT_ALIAS = "exact_alias"
    FUZZY_LANDMARK = "fuzzy_landmark"
    QUARTIER = "quartier"
    STREET_FALLBACK = "street_fallback"


class PlaceResult(VoraModel):
    id: str
    name: str
    kind: LandmarkKind
    quartier: str | None = None
    city: str
    lat: Latitude
    lng: Longitude
    distance_m: int | None = Field(
        default=None,
        description="Distance from the `near` parameter. Null when `near` is omitted.",
    )
    match_type: MatchType
    matched_alias: str | None = Field(
        default=None,
        description="The alias that produced the hit, when the match was alias-based.",
    )


class PlaceSearchResponse(VoraModel):
    query: str
    results: list[PlaceResult]


class ReverseGeocodeResponse(VoraModel):
    label: str = Field(description="Best human label for the point, in the caller's locale.")
    nearest_landmark: PlaceResult | None = None
    quartier: str | None = None
    city: str | None = None
