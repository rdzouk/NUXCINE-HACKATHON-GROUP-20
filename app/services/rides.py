"""Ride lifecycle.

Creation, state transitions and the event log. Matching and the driver claim
live in `app/services/matching.py`.

Two things worth reading before changing anything here.

**Every transition goes through `transition_ride`.** Not because it is tidy,
but because that function is the only place `ride_events` is written, and I7
says every transition is recorded with actor, timestamp and reason. A handler
that sets `ride.status` directly produces a ride whose history has a hole in
it, and the hole is invisible until somebody needs it during a dispute.

**The fare is re-derived, never read from the request.** `create_ride` takes a
signed quote, verifies it, burns its jti so it cannot be replayed, and
recomputes the fare from the distance inside it. Nothing a client sends
influences the price (I2).
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from geoalchemy2 import WKTElement
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.logging import get_logger
from app.models.ride import Ride, RideEvent
from app.models.user import User
from app.schemas.ride import ActorType, RideStatus
from app.security import hashing
from app.services import quotes
from app.services.fare import DEFAULT_FARE_CONFIG, quote_both
from app.services.routing import get_routing_provider
from app.services.state_machine import LIVE, assert_transition

logger = get_logger("vora.rides")

PIN_LENGTH = 4
MAX_PIN_ATTEMPTS = 5
IDEMPOTENCY_TTL_S = 86_400


def generate_pin() -> str:
    """A four-digit pickup PIN.

    `secrets`, not `random`. The PIN is what stops a stranger at the kerb
    claiming to be the assigned driver, so a predictable sequence would defeat
    the whole mechanism. Four digits is a deliberate trade: it has to be read
    aloud across a car window, and the five-attempt cap is what makes the small
    keyspace acceptable.
    """
    return f"{secrets.randbelow(10**PIN_LENGTH):0{PIN_LENGTH}d}"


async def record_event(
    session: AsyncSession,
    *,
    ride_id: uuid.UUID,
    event_type: str,
    actor_type: ActorType,
    actor_id: uuid.UUID | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append to the ride's history. Never updates, never deletes (I7)."""
    session.add(
        RideEvent(
            ride_id=ride_id,
            event_type=event_type,
            actor_type=actor_type.value,
            actor_id=actor_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            event_metadata=metadata,
            occurred_at=datetime.now(UTC),
        )
    )


async def transition_ride(
    session: AsyncSession,
    *,
    ride: Ride,
    target: RideStatus,
    actor_type: ActorType,
    actor_id: uuid.UUID | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Ride:
    """Move a ride to a new status, validating and recording it.

    The single door. Validation and the audit write happen together so neither
    can be skipped by forgetting to call the other.
    """
    current = RideStatus(ride.status)
    transition = assert_transition(current, target, actor_type)

    ride.status = target.value
    now = datetime.now(UTC)

    # Timestamps that the contract exposes and the fare depends on.
    if target is RideStatus.ACCEPTED:
        ride.accepted_at = now
    elif target is RideStatus.ARRIVED:
        ride.arrived_at = now
    elif target is RideStatus.IN_PROGRESS:
        ride.started_at = now
    elif target in (
        RideStatus.COMPLETED,
        RideStatus.CANCELLED_PASSENGER,
        RideStatus.CANCELLED_DRIVER,
        RideStatus.EXPIRED,
    ):
        ride.ended_at = now

    await record_event(
        session,
        ride_id=ride.id,
        event_type=transition.event,
        actor_type=actor_type,
        actor_id=actor_id,
        from_status=current.value,
        to_status=target.value,
        reason=reason,
        metadata=metadata,
    )

    logger.info(
        "ride_transition",
        ride_id=str(ride.id),
        from_status=current.value,
        to_status=target.value,
        actor=actor_type.value,
    )
    return ride


async def find_live_ride_for_passenger(
    session: AsyncSession, *, passenger_id: uuid.UUID
) -> Ride | None:
    result = await session.execute(
        select(Ride).where(
            Ride.passenger_id == passenger_id,
            Ride.status.in_([s.value for s in LIVE]),
        )
    )
    return result.scalar_one_or_none()


async def create_ride(
    session: AsyncSession,
    redis,
    *,
    passenger: User,
    quote_id: str,
    seats: int,
    accessibility_required: list[str],
    idempotency_key: str,
) -> tuple[Ride, bool]:
    """Create a ride from a signed quote. Returns (ride, was_created).

    `was_created` is False when an existing ride is returned for a repeated
    idempotency key, which lets the handler answer 200 rather than 201 without
    the caller having to tell the difference.
    """
    # Idempotency first, before anything with a side effect. A retried request
    # must not burn the quote jti or generate a second PIN.
    existing = await session.execute(
        select(Ride).where(
            Ride.passenger_id == passenger.id,
            Ride.idempotency_key == idempotency_key,
        )
    )
    prior = existing.scalar_one_or_none()
    if prior is not None:
        logger.info(
            "ride_idempotent_replay",
            ride_id=str(prior.id),
            passenger_id=str(passenger.id),
        )
        return prior, False

    payload = quotes.verify_quote(quote_id)

    # The body's seat count is checked against the quote rather than trusted.
    # Repricing silently for a different seat count would let a client book
    # three seats at a one-seat price.
    if payload.seats != seats:
        # 422, not 400. The request is well-formed and the quote is genuine;
        # what is wrong is the meaning, which is what §6 reserves 422 for.
        # Contract decision 8: the signed quote is authoritative for seats and
        # mode, and a mismatch is refused rather than silently repriced.
        raise VoraError(
            ErrorCode.QUOTE_INVALID,
            status_code=422,
            details={"reason": "seats_mismatch", "quoted_seats": payload.seats},
            message="Le nombre de places ne correspond pas au tarif.",
        )

    live = await find_live_ride_for_passenger(session, passenger_id=passenger.id)
    if live is not None:
        raise VoraError(
            ErrorCode.ACTIVE_RIDE_EXISTS, details={"ride_id": str(live.id)}
        )

    # The cancellation ledger has teeth here, and only here.
    #
    # A debt that never blocks anything is a number in a table. Refusing the
    # next booking is what makes a cancellation fee real without any money
    # moving, which is the whole reason this is a debt ledger rather than a
    # wallet in a cash market.
    #
    # The error names the amount so the client can say what is owed rather
    # than only that something is.
    from app.services.cancellation import outstanding_balance

    owed = await outstanding_balance(session, passenger.id)
    if owed > 0:
        raise VoraError(
            ErrorCode.OUTSTANDING_BALANCE,
            details={"outstanding_xaf": owed, "currency": "XAF"},
        )

    # Single use. A signed blob proves the server minted it, not that it has
    # only been used once, so the jti is burned here. Done after the checks
    # above so a rejected request does not consume the quote.
    await quotes.burn_quote_jti(redis, payload.jti)

    # Re-derived from the distance inside the signed quote, never read from it
    # directly and never from the request body (I2).
    fares = quote_both(payload.distance_m, payload.duration_s, DEFAULT_FARE_CONFIG)
    fare = (
        fares.corridor_xaf if payload.mode == "corridor" else fares.exclusive_xaf
    )

    # Re-request the route rather than carrying it in the quote.
    #
    # A polyline runs to several kilobytes, and a quote id travels in a request
    # body on a mobile network, so putting it in the signed blob would make
    # every booking carry the whole geometry twice. Re-routing here also means
    # a ride is never created against a route the engine no longer agrees with.
    #
    # The fare is *not* recomputed from this. It comes from the distance inside
    # the signed quote, so a route that changed between quoting and booking
    # cannot silently reprice what the passenger already agreed to (I2).
    route = await get_routing_provider().route(
        (payload.pickup_lat, payload.pickup_lng),
        (payload.dropoff_lat, payload.dropoff_lng),
    )

    pin = generate_pin()
    ride = Ride(
        passenger_id=passenger.id,
        mode=payload.mode,
        status=RideStatus.REQUESTED.value,
        seats=payload.seats,
        pickup_label=payload.pickup_label,
        dropoff_label=payload.dropoff_label,
        # Set on the row, not by a follow-up UPDATE. Both geography columns are
        # NOT NULL, so anything that leaves them unset until after the flush
        # fails the insert outright. WKT order is (longitude latitude), which
        # is the reverse of how every other API here takes a coordinate and is
        # the reason this is written out rather than passed through a tuple.
        pickup_geom=WKTElement(
            f"POINT({payload.pickup_lng} {payload.pickup_lat})", srid=4326
        ),
        dropoff_geom=WKTElement(
            f"POINT({payload.dropoff_lng} {payload.dropoff_lat})", srid=4326
        ),
        route_polyline=route.polyline,
        quoted_fare_xaf=fare,
        quoted_distance_m=payload.distance_m,
        quoted_duration_s=payload.duration_s,
        accessibility_required=accessibility_required,
        pin=pin,
        pin_hash=hashing.hash_otp(pin),
        idempotency_key=idempotency_key,
    )
    session.add(ride)
    await session.flush()

    # Store the route as geometry, not only as an encoded string.
    #
    # `route_polyline` is what a client draws; `route_geom` is what Postgres
    # can answer questions about. Corridor matching asks "does this line pass
    # near both of these points, in this order", which is an ST_DWithin and an
    # ST_LineLocatePoint against the GiST index. Decoding polylines in Python
    # to answer that would mean loading every live route per request.
    #
    # Declared in Phase 3 and left null until now because nothing needed a line.
    if route.polyline:
        await session.execute(
            text(
                "UPDATE rides SET route_geom = ST_SetSRID("
                "  ST_LineFromEncodedPolyline(:polyline), 4326)::geography "
                "WHERE id = :id"
            ),
            {"polyline": route.polyline, "id": ride.id},
        )

    await record_event(
        session,
        ride_id=ride.id,
        event_type="ride_requested",
        actor_type=ActorType.PASSENGER,
        actor_id=passenger.id,
        to_status=RideStatus.REQUESTED.value,
        metadata={
            "mode": payload.mode,
            "seats": payload.seats,
            "quoted_fare_xaf": fare,
            "distance_m": payload.distance_m,
            "routing_source": payload.routing_source,
        },
    )

    logger.info(
        "ride_created",
        ride_id=str(ride.id),
        passenger_id=str(passenger.id),
        mode=payload.mode,
        fare_xaf=fare,
    )
    return ride, True


async def verify_pin(
    session: AsyncSession, *, ride: Ride, submitted: str, driver_id: uuid.UUID
) -> None:
    """Check the pickup PIN, or raise.

    Attempts are counted on the ride and capped. Four digits is a small
    keyspace; the cap is what makes it safe. Hitting it does not silently
    unlock anything, it escalates: the ride needs support intervention.
    """
    if ride.pin_attempts >= MAX_PIN_ATTEMPTS:
        raise VoraError(ErrorCode.PIN_ATTEMPTS_EXCEEDED)

    ride.pin_attempts += 1

    if not hashing.verify_otp(ride.pin_hash, submitted):
        remaining = MAX_PIN_ATTEMPTS - ride.pin_attempts
        await record_event(
            session,
            ride_id=ride.id,
            event_type="pin_rejected",
            actor_type=ActorType.DRIVER,
            actor_id=driver_id,
            reason="incorrect_pin",
            metadata={"attempts_remaining": max(remaining, 0)},
        )
        await session.flush()
        if remaining <= 0:
            raise VoraError(ErrorCode.PIN_ATTEMPTS_EXCEEDED)
        raise VoraError(
            ErrorCode.PIN_INVALID, details={"attempts_remaining": remaining}
        )
