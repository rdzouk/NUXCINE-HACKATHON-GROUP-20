"""Driver matching and the atomic claim.

**Waves, one query each.** Candidates come from a single `ST_DWithin` against
the GiST index on `driver_presence.geom`, joined to vehicles and filtered by
seats and capability in the same statement. Never a loop that fetches each
driver: at twelve drivers the difference is invisible, and at twelve hundred it
is the difference between a demo and a timeout. Widening rings rather than one
big radius because a driver 6 km away should only be asked once the nearby ones
have declined.

**The claim is the part that has to be right.** Two passengers must never get
the same driver, and two drivers must never get the same ride. Both are
enforced by partial unique indexes in migration 0004, so even a transaction
with a logic bug cannot violate them. This module's job is to lose gracefully:
the loser of a race gets `409 OFFER_TAKEN`, not a 500.

The claim uses `SELECT ... FOR UPDATE` on the ride row and keeps the
transaction short. Nothing slow happens inside it: no routing call, no
notification, no socket write. A lock held across a network call is how a
matching system deadlocks under load.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.logging import get_logger
from app.models.ride import Ride, RideOffer
from app.models.user import Driver, Vehicle
from app.schemas.ride import ActorType, RideStatus
from app.services.rides import record_event, transition_ride

logger = get_logger("vora.matching")

# Widening rings. Wave 1 fires immediately, then 2 and 3 on a timer.
WAVES: tuple[tuple[int, int, int], ...] = (
    # (wave number, radius in metres, seconds after request)
    (1, 2_000, 0),
    (2, 4_000, 15),
    (3, 6_000, 30),
)

# No driver by this point and the ride expires rather than hanging. A passenger
# staring at a spinner needs an answer, even a disappointing one.
MATCH_TIMEOUT_S = 60

# How long a driver has to answer before the offer lapses. Short, because an
# unanswered offer holds nothing but does clutter their screen.
OFFER_TTL_S = 25

# Vehicle capability columns, keyed by the requirement name the API uses.
# Written out rather than derived from the enum so that adding a capability to
# the contract cannot silently produce a matching query that ignores it.
CAPABILITY_COLUMNS: dict[str, str] = {
    "ramp": "v.has_ramp",
    "boot_space": "v.has_boot_space",
    "front_seat": "v.front_seat_available",
    "driver_assist": "v.driver_assists",
    "guide_animal": "v.accepts_guide_animal",
}


# One statement per wave.
#
# Every filter that can be expressed in SQL is expressed here rather than in
# Python, because each one that leaks into the application is a row fetched
# and discarded. The capability predicate is built from a fixed mapping, never
# from caller-supplied text, so it cannot be an injection point.
_CANDIDATES_SQL = """
SELECT
    d.id AS driver_id,
    ST_Distance(
        p.geom, ST_MakePoint(:pickup_lng, :pickup_lat)::geography
    ) AS distance_m
FROM driver_presence p
JOIN drivers d ON d.id = p.driver_id
JOIN vehicles v ON v.driver_id = d.id AND v.is_active
WHERE
    ST_DWithin(p.geom, ST_MakePoint(:pickup_lng, :pickup_lat)::geography, :radius_m)
    AND d.is_online
    -- Belt and braces with the CHECK constraint on drivers. An unverified
    -- driver going online is an unvetted stranger sent to somebody's address.
    AND d.kyc_status = 'verified'
    AND d.seats_free >= :seats
    AND v.seats >= :seats
    -- Location that has gone stale means the driver's app is not reporting.
    -- Offering them a ride would strand the passenger.
    AND p.recorded_at > now() - make_interval(secs => :max_age_s)
    -- Not already on a live ride.
    AND NOT EXISTS (
        SELECT 1 FROM rides r
        WHERE r.driver_id = d.id
          AND r.status IN ('requested', 'matching', 'accepted', 'arriving',
                           'arrived', 'in_progress')
    )
    -- Never re-offer a ride to a driver who has already seen it.
    AND NOT EXISTS (
        SELECT 1 FROM ride_offers o
        WHERE o.ride_id = :ride_id AND o.driver_id = d.id
    )
    {capability_predicate}
ORDER BY distance_m ASC
LIMIT :limit
"""

PRESENCE_MAX_AGE_S = 120


def _capability_predicate(required: list[str]) -> str:
    """Build the capability filter from a fixed column mapping.

    Requirements arrive from the API as an enum, and only names present in
    CAPABILITY_COLUMNS produce a clause. An unknown value is ignored here and
    would have been rejected at the schema boundary already, so no caller text
    reaches the statement.
    """
    clauses = [
        f"AND {CAPABILITY_COLUMNS[name]}"
        for name in required
        if name in CAPABILITY_COLUMNS
    ]
    return "\n    ".join(clauses)


async def find_candidates(
    session: AsyncSession,
    *,
    ride: Ride,
    radius_m: int,
    limit: int = 10,
) -> list[tuple[uuid.UUID, float]]:
    """Candidate drivers for one wave, nearest first. One query."""
    pickup = await session.execute(
        text(
            "SELECT ST_Y(pickup_geom::geometry) AS lat, "
            "ST_X(pickup_geom::geometry) AS lng FROM rides WHERE id = :id"
        ),
        {"id": ride.id},
    )
    row = pickup.one()

    sql = _CANDIDATES_SQL.format(
        capability_predicate=_capability_predicate(
            list(ride.accessibility_required or [])
        )
    )

    result = await session.execute(
        text(sql),
        {
            "pickup_lat": row.lat,
            "pickup_lng": row.lng,
            "radius_m": radius_m,
            "seats": ride.seats,
            "ride_id": ride.id,
            "limit": limit,
            "max_age_s": PRESENCE_MAX_AGE_S,
        },
    )
    return [(r.driver_id, float(r.distance_m)) for r in result]


async def run_wave(
    session: AsyncSession, *, ride: Ride, wave: int, radius_m: int
) -> list[RideOffer]:
    """Create offers for one wave. Returns what was created."""
    candidates = await find_candidates(session, ride=ride, radius_m=radius_m)
    if not candidates:
        logger.info(
            "matching_wave_empty",
            ride_id=str(ride.id),
            wave=wave,
            radius_m=radius_m,
        )
        return []

    expires_at = datetime.now(UTC) + timedelta(seconds=OFFER_TTL_S)
    offers = [
        RideOffer(
            ride_id=ride.id,
            driver_id=driver_id,
            wave=wave,
            state="open",
            distance_to_pickup_m=int(distance),
            expires_at=expires_at,
        )
        for driver_id, distance in candidates
    ]
    session.add_all(offers)

    await record_event(
        session,
        ride_id=ride.id,
        event_type="matching_wave",
        actor_type=ActorType.SYSTEM,
        metadata={
            "wave": wave,
            "radius_m": radius_m,
            "offers": len(offers),
        },
    )
    await session.flush()

    logger.info(
        "matching_wave",
        ride_id=str(ride.id),
        wave=wave,
        radius_m=radius_m,
        offers=len(offers),
    )
    return offers


async def start_matching(session: AsyncSession, *, ride: Ride) -> list[RideOffer]:
    """Move the ride into matching and fire wave 1."""
    if RideStatus(ride.status) is RideStatus.REQUESTED:
        await transition_ride(
            session,
            ride=ride,
            target=RideStatus.MATCHING,
            actor_type=ActorType.SYSTEM,
        )
    wave, radius, _ = WAVES[0]
    return await run_wave(session, ride=ride, wave=wave, radius_m=radius)


async def claim_offer(
    session: AsyncSession, *, offer_id: uuid.UUID, driver: Driver
) -> Ride:
    """Accept an offer. Exactly one caller can win.

    The ordering matters:

      1. lock the offer row, so two accepts of the same offer serialise
      2. lock the ride row, so two accepts of *different* offers on the same
         ride also serialise
      3. re-check both states under those locks
      4. write, and let the unique indexes catch anything that slipped through

    Step 4 is not redundant. The locks make the common case correct; the
    indexes make it correct even if this function has a bug, which is the
    property worth having on the path where two passengers could otherwise be
    sent the same car.
    """
    now = datetime.now(UTC)

    offer = await session.get(RideOffer, offer_id, with_for_update=True)
    if offer is None or offer.driver_id != driver.id:
        # A foreign offer id and a nonexistent one answer the same way. Which
        # offers exist is not information a driver has earned.
        raise VoraError(ErrorCode.OFFER_NOT_FOUND)

    if offer.state != "open":
        raise VoraError(
            ErrorCode.OFFER_TAKEN, details={"offer_state": offer.state}
        )

    if offer.expires_at <= now:
        offer.state = "expired"
        await session.flush()
        raise VoraError(ErrorCode.OFFER_EXPIRED)

    ride = await session.get(Ride, offer.ride_id, with_for_update=True)
    if ride is None:
        raise VoraError(ErrorCode.RIDE_NOT_FOUND)

    # Somebody else already took it.
    if RideStatus(ride.status) not in (RideStatus.REQUESTED, RideStatus.MATCHING):
        offer.state = "superseded"
        offer.responded_at = now
        await session.flush()
        raise VoraError(
            ErrorCode.OFFER_TAKEN, details={"ride_status": ride.status}
        )

    if driver.kyc_status != "verified" or not driver.is_online:
        raise VoraError(ErrorCode.KYC_NOT_VERIFIED)

    vehicle = await session.execute(
        select(Vehicle)
        .where(Vehicle.driver_id == driver.id, Vehicle.is_active.is_(True))
        .limit(1)
    )
    chosen = vehicle.scalar_one_or_none()
    if chosen is None:
        raise VoraError(
            ErrorCode.KYC_NOT_VERIFIED, details={"reason": "no_active_vehicle"}
        )

    ride.driver_id = driver.id
    ride.vehicle_id = chosen.id
    offer.state = "accepted"
    offer.responded_at = now

    await transition_ride(
        session,
        ride=ride,
        target=RideStatus.ACCEPTED,
        actor_type=ActorType.SYSTEM,
        actor_id=driver.id,
        reason="offer_accepted",
        metadata={"offer_id": str(offer.id), "wave": offer.wave},
    )

    # Every other open offer on this ride is now dead.
    await session.execute(
        text(
            "UPDATE ride_offers SET state = 'superseded', responded_at = now() "
            "WHERE ride_id = :ride_id AND id <> :offer_id AND state = 'open'"
        ),
        {"ride_id": ride.id, "offer_id": offer.id},
    )

    try:
        await session.flush()
    except IntegrityError as exc:
        # The partial unique index on (driver_id) where live fired: this driver
        # is already on another ride. Losing here is correct behaviour, not an
        # error to surface as a 500.
        await session.rollback()
        logger.warning(
            "claim_lost_to_unique_index",
            driver_id=str(driver.id),
            offer_id=str(offer_id),
        )
        raise VoraError(ErrorCode.OFFER_TAKEN) from exc

    logger.info(
        "offer_claimed",
        ride_id=str(ride.id),
        driver_id=str(driver.id),
        offer_id=str(offer.id),
        wave=offer.wave,
    )
    return ride


async def decline_offer(
    session: AsyncSession, *, offer_id: uuid.UUID, driver: Driver
) -> None:
    """Decline. The driver is not offered this ride again in a later wave."""
    offer = await session.get(RideOffer, offer_id)
    if offer is None or offer.driver_id != driver.id:
        raise VoraError(ErrorCode.OFFER_NOT_FOUND)

    if offer.state == "open":
        offer.state = "declined"
        offer.responded_at = datetime.now(UTC)
        await record_event(
            session,
            ride_id=offer.ride_id,
            event_type="offer_declined",
            actor_type=ActorType.DRIVER,
            actor_id=driver.id,
            metadata={"offer_id": str(offer.id), "wave": offer.wave},
        )
        await session.flush()


async def expire_stale_rides(session: AsyncSession) -> int:
    """Expire rides nobody accepted within the timeout.

    Runs from a background task rather than a cron: at demo scale the set is
    tiny, and a ride stuck in `matching` forever is worse than one honestly
    marked expired.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=MATCH_TIMEOUT_S)
    result = await session.execute(
        select(Ride).where(
            Ride.status.in_([RideStatus.REQUESTED.value, RideStatus.MATCHING.value]),
            Ride.created_at < cutoff,
        )
    )
    rides = result.scalars().all()

    for ride in rides:
        await transition_ride(
            session,
            ride=ride,
            target=RideStatus.EXPIRED,
            actor_type=ActorType.SYSTEM,
            reason="no_driver_within_timeout",
        )

    if rides:
        await session.execute(
            text(
                "UPDATE ride_offers SET state = 'expired' "
                "WHERE ride_id = ANY(:ids) AND state = 'open'"
            ),
            {"ids": [r.id for r in rides]},
        )
    return len(rides)
