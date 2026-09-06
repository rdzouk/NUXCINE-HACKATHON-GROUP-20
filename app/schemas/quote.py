"""Fare quoting contract.

`quote_id` is an HMAC-signed blob, not a database row. It carries pickup,
dropoff, distance, duration, mode, seats and fare, and the server re-derives
the fare from it at ride creation. A client-supplied price is never an input
to anything (I2).

Phase 2 will additionally burn the quote's jti in Redis on use, so one quote
cannot create two rides under two idempotency keys.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import NamedPlace, RideMode, VoraModel
from app.schemas.ride import FareBreakdown


class QuoteRequest(VoraModel):
    pickup: NamedPlace
    dropoff: NamedPlace
    seats: int = Field(default=1, ge=1, le=8)
    mode: RideMode = RideMode.EXCLUSIVE


class QuoteResponse(VoraModel):
    quote_id: str = Field(
        description="Signed and short-lived. Pass verbatim to POST /rides; do not parse."
    )
    distance_m: int
    duration_s: int
    currency: str = "XAF"
    fare_xaf: int = Field(description="Exclusive-hire fare for this trip.")
    corridor_fare_xaf: int | None = Field(
        default=None,
        description=(
            "Per-seat corridor fare for the same trip. Always lower than fare_xaf. "
            "Null when the route has no corridor eligibility."
        ),
    )
    route_polyline: str
    expires_at: datetime
    breakdown: FareBreakdown
    routing_source: str = Field(
        default="osrm",
        description=(
            "'osrm' when the route came from the routing engine, 'haversine_fallback' "
            "when OSRM was unreachable and a straight-line estimate was used instead. "
            "Surfaced so the client can say the estimate is approximate."
        ),
        examples=["osrm", "haversine_fallback"],
    )
