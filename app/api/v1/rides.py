"""Ride routes.

**Every route carrying a `{ride_id}` declares `RideParticipant`.** That
dependency is the single implementation of I1: it resolves the ride, works out
whether the caller is its passenger, its assigned driver or an admin, and
raises `404 RIDE_NOT_FOUND` for anybody else. No handler in this file repeats
that check, and none should. `scripts/idor_sweep.py` reads openapi.json and
asserts a stranger's token gets 404 on every one of them, so a route added
later without the dependency fails the sweep rather than shipping.

The safety and money routes (cancel, share, SOS, messages) stay 501 until
Phase 5, but they already carry the dependency. The authorization surface is
complete now rather than arriving with the feature.
"""

from __future__ import annotations

import base64
from datetime import datetime

from fastapi import APIRouter, Header, Query, Response, status
from sqlalchemy import or_, select, text

from app.api.v1._stub import COMMON_ERRORS
from app.cache import get_redis
from app.deps import CurrentUser, RideParticipant, SessionDep
from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.logging import get_logger
from app.models.ride import Ride
from app.models.user import Driver, User, Vehicle
from app.schemas.ride import (
    ActorType,
    IncidentReportRequest,
    IncidentResponse,
    RideCancelRequest,
    RideCancelResponse,
    RideCompleteResponse,
    RideCreateRequest,
    RideListResponse,
    RideMessage,
    RideMessageRequest,
    RideMessageResponse,
    RideResponse,
    RideStartRequest,
    RideStatus,
    ShareLinkResponse,
)
from app.services import (
    accessibility,
    cancellation,
    corridor,
    incidents,
    matching,
    messaging,
    sharing,
)
from app.services import rides as ride_service
from app.services.fare import DEFAULT_FARE_CONFIG, quote_both
from app.services.serializers import serialize_ride

router = APIRouter(tags=["rides"])
logger = get_logger("vora.rides.api")


async def _endpoints(session, ride: Ride):
    """Read the geography columns back as plain coordinates."""
    row = (
        await session.execute(
            text(
                "SELECT ST_Y(pickup_geom::geometry) AS p_lat, "
                "ST_X(pickup_geom::geometry) AS p_lng, "
                "ST_Y(dropoff_geom::geometry) AS d_lat, "
                "ST_X(dropoff_geom::geometry) AS d_lng "
                "FROM rides WHERE id = :id"
            ),
            {"id": ride.id},
        )
    ).one()
    return (row.p_lat, row.p_lng), (row.d_lat, row.d_lng)


async def _render(session, ride: Ride, actor: str):
    """Load exactly the related rows this actor's view needs, then serialize.

    Loaded explicitly rather than through lazy relationships: under asyncio a
    lazy load at attribute-access time raises MissingGreenlet, and doing it
    here makes the query count per response obvious.
    """
    driver_user = vehicle = passenger_user = None

    if ride.driver_id is not None:
        driver = await session.get(Driver, ride.driver_id)
        if driver is not None:
            driver_user = await session.get(User, driver.user_id)
    if ride.vehicle_id is not None:
        vehicle = await session.get(Vehicle, ride.vehicle_id)
    if actor in ("driver", "admin"):
        passenger_user = await session.get(User, ride.passenger_id)

    pickup, dropoff = await _endpoints(session, ride)
    return serialize_ride(
        ride,
        actor=actor,
        driver_user=driver_user,
        vehicle=vehicle,
        passenger_user=passenger_user,
        pickup=pickup,
        dropoff=dropoff,
    )


async def _try_join_corridor(session, ride) -> bool:
    """Attempt to seat this passenger on a corridor already being driven.

    Returns True when a driver has been asked. Returns False when no corridor
    fits, which is an ordinary outcome and falls through to normal matching
    rather than failing the booking.

    The driver is *asked*, never auto-assigned. They are the one who has to
    manage two strangers in a car, and taking that decision away from them is
    how a platform loses drivers.
    """
    pickup, dropoff = await _endpoints(session, ride)

    candidates = await corridor.find_candidates(
        session,
        passenger_id=ride.passenger_id,
        pickup=pickup,
        dropoff=dropoff,
        seats=ride.seats,
    )
    if not candidates:
        return False

    # Least disruptive first, which is what the candidate query orders by.
    best = candidates[0]

    await ride_service.record_event(
        session,
        ride_id=ride.id,
        event_type="corridor_match_found",
        actor_type=ActorType.SYSTEM,
        metadata={
            "parent_ride_id": str(best.parent_ride_id),
            "boarding_order": best.boarding_order,
            "leg_distance_m": best.leg_distance_m,
            "leg_fare_xaf": best.leg_fare_xaf,
            "added_distance_m": best.added_distance_m,
            "added_duration_s": best.added_duration_s,
        },
    )

    # The ride moves to matching first, so that the offer the driver receives
    # belongs to a ride in a state that can be claimed. `start_matching` would
    # fan out to nearby drivers, which is exactly wrong here: its candidate
    # query excludes anybody already on a live ride, and this driver is on one.
    await ride_service.transition_ride(
        session,
        ride=ride,
        target=RideStatus.MATCHING,
        actor_type=ActorType.SYSTEM,
        reason="corridor_join_offered",
    )
    await corridor.offer_join(session, candidate=best, joiner_ride=ride)

    # Still needs the driver to say yes. Until then the ride sits in matching
    # holding its seats; declining releases them and falls back to an ordinary
    # matching wave, so a driver saying no costs the passenger only the wait.
    return True


@router.post(
    "/rides",
    response_model=RideResponse,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
    summary="Create a ride from a quote",
    description=(
        "Requires an Idempotency-Key header (I8). Mobile networks here drop and "
        "retry; without de-duplication one tap creates two rides. A repeated "
        "key returns the original ride with 200 rather than creating a second.\n\n"
        "The fare is re-derived from the signed quote, never read from the "
        "request. The quote is single-use: presenting it twice returns "
        "409 QUOTE_ALREADY_USED."
    ),
)
async def create_ride(
    payload: RideCreateRequest,
    user: CurrentUser,
    session: SessionDep,
    response: Response,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        description="Client-generated. Reuse it verbatim when retrying.",
    ),
) -> RideResponse:
    # The passenger's standing profile supplies the default requirements; the
    # body overrides them for this trip only. Booking for a relative, or
    # travelling with a wheelchair today and not tomorrow, are both ordinary,
    # and a requirement attached to the journey handles them while a flag
    # attached to the person does not (I9).
    required = [c.value for c in payload.accessibility_required]
    if not required:
        required = accessibility.required_from_profile(user)

    ride, created = await ride_service.create_ride(
        session,
        get_redis(),
        passenger=user,
        quote_id=payload.quote_id,
        seats=payload.seats,
        accessibility_required=required,
        idempotency_key=idempotency_key,
    )

    if created:
        joined = False
        if ride.mode == "corridor":
            # Try to join a corridor already being driven before falling back
            # to summoning a fresh vehicle. That ordering is the whole point of
            # the mode: a seat in a car already going that way costs the
            # passenger less and earns the driver more than a second car would.
            joined = await _try_join_corridor(session, ride)

        if not joined:
            # Wave 1 fires immediately, so offers are out before the passenger
            # has finished reading the confirmation screen.
            await matching.start_matching(session, ride=ride)
    else:
        response.status_code = status.HTTP_200_OK

    await session.commit()
    await session.refresh(ride)
    return RideResponse(ride=await _render(session, ride, "passenger"))


@router.get(
    "/rides",
    response_model=RideListResponse,
    responses=COMMON_ERRORS,
    summary="List the caller's rides",
    description=(
        "Rides where the caller is the passenger or the assigned driver. The "
        "restriction is a WHERE clause, not a filter applied after fetching."
    ),
)
async def list_rides(
    user: CurrentUser,
    session: SessionDep,
    status_filter: RideStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None, max_length=512),
) -> RideListResponse:
    driver = (
        await session.execute(select(Driver).where(Driver.user_id == user.id))
    ).scalar_one_or_none()

    visibility = (
        Ride.passenger_id == user.id
        if driver is None
        else or_(Ride.passenger_id == user.id, Ride.driver_id == driver.id)
    )
    query = select(Ride).where(visibility)

    if status_filter is not None:
        query = query.where(Ride.status == status_filter.value)

    # Keyset pagination on created_at. An opaque cursor, because a client that
    # can construct one is a client that can page through somebody else's data
    # if the visibility clause ever regresses.
    if cursor:
        try:
            after = datetime.fromisoformat(base64.urlsafe_b64decode(cursor).decode())
        except (ValueError, TypeError) as exc:
            raise VoraError(
                ErrorCode.VALIDATION_FAILED, details={"field": "cursor"}
            ) from exc
        query = query.where(Ride.created_at < after)

    # One extra row tells us whether a next page exists without a count query.
    query = query.order_by(Ride.created_at.desc()).limit(limit + 1)
    found = list((await session.execute(query)).scalars().all())

    next_cursor = None
    if len(found) > limit:
        found = found[:limit]
        next_cursor = base64.urlsafe_b64encode(
            found[-1].created_at.isoformat().encode()
        ).decode()

    items = []
    for ride in found:
        actor = "passenger" if ride.passenger_id == user.id else "driver"
        items.append(await _render(session, ride, actor))

    return RideListResponse(items=items, next_cursor=next_cursor)


@router.get(
    "/rides/{ride_id}",
    response_model=RideResponse,
    responses=COMMON_ERRORS,
    summary="Read one ride",
    description=(
        "A caller who is not the passenger, the assigned driver or an admin "
        "receives 404 RIDE_NOT_FOUND, never 403. The existence of a ride is "
        "itself information."
    ),
)
async def get_ride(ctx: RideParticipant, session: SessionDep) -> RideResponse:
    return RideResponse(ride=await _render(session, ctx.ride, ctx.actor))


@router.post(
    "/rides/{ride_id}/arrived",
    response_model=RideResponse,
    responses=COMMON_ERRORS,
    summary="Driver reports arrival at pickup",
)
async def driver_arrived(ctx: RideParticipant, session: SessionDep) -> RideResponse:
    if not ctx.is_driver:
        raise VoraError(ErrorCode.RIDE_STATE_CONFLICT)

    await ride_service.transition_ride(
        session,
        ride=ctx.ride,
        target=RideStatus.ARRIVED,
        actor_type=ActorType.DRIVER,
        actor_id=ctx.user.id,
    )
    await session.commit()
    await session.refresh(ctx.ride)
    return RideResponse(ride=await _render(session, ctx.ride, ctx.actor))


@router.post(
    "/rides/{ride_id}/start",
    response_model=RideResponse,
    responses=COMMON_ERRORS,
    summary="Start the trip with the passenger's PIN",
    description=(
        "The passenger reads the four-digit PIN aloud and the driver enters "
        "it. This is what makes impersonation at pickup fail: somebody who "
        "read the plate off the app still does not have the PIN. A wrong PIN "
        "returns 403; five failures escalate to support rather than silently "
        "unlocking."
    ),
)
async def start_ride(
    payload: RideStartRequest, ctx: RideParticipant, session: SessionDep
) -> RideResponse:
    if not ctx.is_driver:
        raise VoraError(ErrorCode.RIDE_STATE_CONFLICT)

    await ride_service.verify_pin(
        session, ride=ctx.ride, submitted=payload.pin, driver_id=ctx.user.id
    )
    await ride_service.transition_ride(
        session,
        ride=ctx.ride,
        target=RideStatus.IN_PROGRESS,
        actor_type=ActorType.DRIVER,
        actor_id=ctx.user.id,
        reason="pin_verified",
    )
    await session.commit()
    await session.refresh(ctx.ride)
    return RideResponse(ride=await _render(session, ctx.ride, ctx.actor))


@router.post(
    "/rides/{ride_id}/complete",
    response_model=RideCompleteResponse,
    responses=COMMON_ERRORS,
    summary="Complete the trip",
    description=(
        "The final fare is computed from the server-held GPS trace where one "
        "exists and from the quoted distance otherwise. Which basis was used "
        "is written to the ride's event log, so the reason for a charge is "
        "never ambiguous. A client-reported distance is never an input (I2)."
    ),
)
async def complete_ride(
    ctx: RideParticipant, session: SessionDep
) -> RideCompleteResponse:
    if not ctx.is_driver:
        raise VoraError(ErrorCode.RIDE_STATE_CONFLICT)

    ride = ctx.ride

    # Distance from the trace, excluding rejected points: those failed the
    # plausibility filter and are retained as evidence, not as measurement.
    traced = await session.scalar(
        text(
            "SELECT ST_Length(ST_MakeLine(geom::geometry ORDER BY seq)::geography) "
            "FROM ride_traces WHERE ride_id = :id AND NOT rejected"
        ),
        {"id": ride.id},
    )

    if traced and traced > 0:
        distance_m, basis = int(traced), "trace"
    else:
        # Phase 4 supplies the trace. Until then, completing on the quoted
        # distance keeps the lifecycle working, and the basis is recorded.
        distance_m, basis = ride.quoted_distance_m, "quoted_distance"

    fares = quote_both(distance_m, ride.quoted_duration_s, DEFAULT_FARE_CONFIG)
    final = fares.corridor_xaf if ride.mode == "corridor" else fares.exclusive_xaf

    ride.actual_distance_m = distance_m
    ride.final_fare_xaf = final

    await ride_service.transition_ride(
        session,
        ride=ride,
        target=RideStatus.COMPLETED,
        actor_type=ActorType.DRIVER,
        actor_id=ctx.user.id,
        metadata={
            "final_fare_xaf": final,
            "actual_distance_m": distance_m,
            "fare_basis": basis,
        },
    )
    await session.commit()
    await session.refresh(ride)

    return RideCompleteResponse(
        ride=await _render(session, ride, ctx.actor), final_fare_xaf=final
    )


@router.post(
    "/rides/{ride_id}/cancel",
    response_model=RideCancelResponse,
    responses=COMMON_ERRORS,
    summary="Cancel a ride",
)
async def cancel_ride(
    payload: RideCancelRequest, ctx: RideParticipant, session: SessionDep
) -> RideCancelResponse:
    if ctx.is_admin:
        # An admin voiding a ride is a different act with different money
        # attached. Out of scope here rather than quietly treated as one of
        # the two parties cancelling.
        raise VoraError(
            ErrorCode.RIDE_STATE_CONFLICT,
            details={"reason": "admin cancellation is not part of this endpoint"},
        )

    actor = ActorType.PASSENGER if ctx.is_passenger else ActorType.DRIVER
    outcome = await cancellation.cancel_ride(
        session,
        ride=ctx.ride,
        actor=actor,
        actor_user_id=ctx.user.id,
        reason=payload.reason,
    )
    await session.commit()
    await session.refresh(ctx.ride)

    return RideCancelResponse(
        ride=await _render(session, ctx.ride, ctx.actor),
        fee_xaf=outcome.fee_xaf,
        fee_reason=outcome.fee_reason,
    )


@router.post(
    "/rides/{ride_id}/share",
    response_model=ShareLinkResponse,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
    summary="Mint a trip-share link",
    description=(
        "Creates a signed, expiring, revocable link that shows a strict subset "
        "of the ride to somebody with no account: driver first name, vehicle, "
        "position and ETA. No passenger identity, no fare, no PIN, no phone.\n\n"
        "Position is coarse until the trip is in progress, so a link shared "
        "while waiting does not reveal exactly where the passenger is standing. "
        "Minting a new link revokes any previous one for the same ride."
    ),
)
async def create_share_link(
    ctx: RideParticipant, session: SessionDep
) -> ShareLinkResponse:
    if not ctx.is_passenger:
        # The passenger's journey is the passenger's to share. A driver
        # publishing a live link to where they are taking somebody is the
        # opposite of a safety feature.
        raise VoraError(
            ErrorCode.RIDE_STATE_CONFLICT,
            details={"reason": "only the passenger may share their trip"},
        )

    link = await sharing.mint_share_link(
        session, ride=ctx.ride, created_by=ctx.user.id
    )
    await ride_service.record_event(
        session,
        ride_id=ctx.ride.id,
        event_type="share_link_created",
        actor_type=ActorType.PASSENGER,
        actor_id=ctx.user.id,
        metadata={"expires_at": link.expires_at.isoformat()},
    )
    await session.commit()
    return ShareLinkResponse(url=link.url, expires_at=link.expires_at)


@router.delete(
    "/rides/{ride_id}/share",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=COMMON_ERRORS,
    summary="Revoke every share link for this ride",
    description=(
        "Immediate. A link already forwarded onward stops working, which is "
        "the property that makes sharing safe to offer at all."
    ),
)
async def revoke_share_link(ctx: RideParticipant, session: SessionDep) -> None:
    if not ctx.is_passenger:
        raise VoraError(ErrorCode.RIDE_STATE_CONFLICT)

    revoked = await sharing.revoke_all(session, ride_id=ctx.ride.id)
    if revoked:
        await ride_service.record_event(
            session,
            ride_id=ctx.ride.id,
            event_type="share_links_revoked",
            actor_type=ActorType.PASSENGER,
            actor_id=ctx.user.id,
            metadata={"count": revoked},
        )
    await session.commit()


@router.post(
    "/rides/{ride_id}/messages",
    response_model=RideMessageResponse,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
    summary="Send a canned message",
    description=(
        "Template keys only; free text is never accepted. This replaces phone "
        "contact between the parties entirely (I3): it cannot carry harassment "
        "or an off-app number, it translates without a pipeline, it costs a few "
        "bytes on a bad network, and it works for users who cannot take a call."
    ),
)
async def send_message(
    payload: RideMessageRequest, ctx: RideParticipant, session: SessionDep
) -> RideMessageResponse:
    if ctx.is_admin:
        raise VoraError(ErrorCode.RIDE_STATE_CONFLICT)

    message = await messaging.send(
        session,
        ride=ctx.ride,
        sender_id=ctx.user.id,
        template=payload.template_key,
    )
    await session.commit()

    # Rendered in the sender's own locale for the echo they get back; the
    # recipient's copy is rendered for them when it is delivered.
    text_out = messaging.render(payload.template_key, ctx.user.locale)

    return RideMessageResponse(
        message=RideMessage(
            id=message.id,
            ride_id=ctx.ride.id,
            sender_type=ActorType.PASSENGER if ctx.is_passenger else ActorType.DRIVER,
            template_key=payload.template_key,
            text=text_out,
            created_at=message.created_at,
        )
    )


@router.post(
    "/rides/{ride_id}/sos",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
    summary="Raise an SOS",
    description=(
        "Seals an immutable snapshot: trace summary, driver and vehicle "
        "identifiers, timestamps, both parties. A database trigger refuses any "
        "later change to it.\n\n"
        "Takes no body. Somebody pressing this is not going to type, and the "
        "snapshot degrades to a smaller one rather than failing if part of the "
        "gathering does: this runs at exactly the moment the system is least "
        "likely to be healthy."
    ),
)
async def raise_sos(ctx: RideParticipant, session: SessionDep) -> IncidentResponse:
    incident = await incidents.raise_sos(
        session, ride=ctx.ride, reporter_id=ctx.user.id
    )
    await session.commit()
    return IncidentResponse(incident_id=incident.id)


@router.post(
    "/rides/{ride_id}/report",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
    summary="File an incident report",
    description=(
        "Same sealed snapshot as an SOS. A fare dispute raised a day later "
        "still needs the trace as it was, not as it is."
    ),
)
async def report_incident(
    payload: IncidentReportRequest, ctx: RideParticipant, session: SessionDep
) -> IncidentResponse:
    incident = await incidents.file_report(
        session,
        ride=ctx.ride,
        reporter_id=ctx.user.id,
        category=payload.category,
        description=payload.description,
    )
    await session.commit()
    return IncidentResponse(incident_id=incident.id)
