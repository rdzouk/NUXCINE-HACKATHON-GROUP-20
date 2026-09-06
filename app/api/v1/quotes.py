"""Fare quoting.

The order of operations here is the security design, not just control flow:

  1. validate both endpoints are inside the service area  (422 before any work)
  2. route the trip                                        (server-side distance)
  3. price it from that distance                           (server-side fare)
  4. sign the result                                       (tamper-evident)

At no point is a number from the request body used to compute a price. That is
invariant I2, and it is the difference between a patched client inflating a
fare and a patched client achieving nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from redis.exceptions import RedisError

from app.api.v1._stub import COMMON_ERRORS
from app.deps import CurrentUser
from app.logging import get_logger
from app.schemas.quote import QuoteRequest, QuoteResponse
from app.schemas.ride import FareBreakdown
from app.services import geocoding, quotes
from app.services.fare import DEFAULT_FARE_CONFIG, quote_both
from app.services.rate_limit import QUOTE_PER_USER, limiter
from app.services.routing import get_routing_provider

router = APIRouter(tags=["rides"])
logger = get_logger("vora.quotes")


@router.post(
    "/rides/quote",
    response_model=QuoteResponse,
    responses=COMMON_ERRORS,
    summary="Price a trip",
    description=(
        "Returns a signed, five-minute quote covering both exclusive and "
        "corridor pricing. The fare is derived server-side from a routed "
        "distance and re-derived again at ride creation; a price in a request "
        "body is never read (I2).\n\n"
        "`routing_source` reports whether the distance came from the routing "
        "engine or from a straight-line fallback, so the client can tell the "
        "user the estimate is approximate rather than presenting a guess as a "
        "surveyed figure."
    ),
)
async def quote_ride(payload: QuoteRequest, user: CurrentUser) -> QuoteResponse:
    # Both endpoints, not just the dropoff. A pickup outside the served area is
    # equally unfillable, and rejecting it here is cheaper than a ride nobody
    # can accept.
    geocoding.require_service_area(
        payload.pickup.lat, payload.pickup.lng, field="pickup"
    )
    geocoding.require_service_area(
        payload.dropoff.lat, payload.dropoff.lng, field="dropoff"
    )

    try:
        decision = await limiter.consume(QUOTE_PER_USER, str(user.id))
        if not decision.allowed:
            from app.errors.codes import ErrorCode
            from app.errors.envelope import VoraError

            raise VoraError(
                ErrorCode.RATE_LIMITED,
                details={"retry_after_s": max(decision.retry_after_s, 1)},
            )
    except RedisError:
        # Fails open: quoting is read-only and costs us a routing call, not
        # money. Refusing to quote would stop booking entirely.
        logger.warning("quote_rate_limiter_unavailable_failing_open")

    route = await get_routing_provider().route(
        (payload.pickup.lat, payload.pickup.lng),
        (payload.dropoff.lat, payload.dropoff.lng),
    )

    fares = quote_both(route.distance_m, route.duration_s, DEFAULT_FARE_CONFIG)

    quote_id, quote_payload = quotes.mint_quote(
        pickup_lat=payload.pickup.lat,
        pickup_lng=payload.pickup.lng,
        pickup_label=payload.pickup.label,
        dropoff_lat=payload.dropoff.lat,
        dropoff_lng=payload.dropoff.lng,
        dropoff_label=payload.dropoff.label,
        distance_m=route.distance_m,
        duration_s=route.duration_s,
        seats=payload.seats,
        mode=payload.mode,
        exclusive_fare_xaf=fares.exclusive_xaf,
        corridor_fare_xaf=fares.corridor_xaf,
        routing_source=route.source,
    )

    logger.info(
        "quote_issued",
        user_id=str(user.id),
        distance_m=route.distance_m,
        exclusive_xaf=fares.exclusive_xaf,
        corridor_xaf=fares.corridor_xaf,
        routing_source=route.source,
    )

    config = DEFAULT_FARE_CONFIG
    return QuoteResponse(
        quote_id=quote_id,
        distance_m=route.distance_m,
        duration_s=route.duration_s,
        fare_xaf=fares.exclusive_xaf,
        corridor_fare_xaf=fares.corridor_xaf,
        route_polyline=route.polyline,
        expires_at=datetime.fromtimestamp(quote_payload.expires_at, tz=UTC),
        routing_source=route.source,
        breakdown=FareBreakdown(
            base_xaf=config.base_xaf,
            per_km_xaf=config.per_km_xaf,
            per_min_xaf=config.per_min_xaf,
            surge_multiplier=config.surge_multiplier,
            minimum_fare_xaf=config.minimum_fare_xaf,
            corridor_rate=config.corridor_rate,
        ),
    )
