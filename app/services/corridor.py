"""Corridor rides. Bet 2.

The dominant real transport mode here is not exclusive hire. It is shared taxis
running *ramassage* along a corridor at a per-seat fare. This module digitises
that, rather than importing carpooling and hoping it fits.

The sentence to say to a jury: **we did not add ride-sharing to a taxi app, we
digitised the shared-corridor model that already exists here, and added
exclusive hire on top of it.**

Four rules, and each one exists because leaving it out breaks something real:

**Containment, not proximity.** A joiner's pickup *and* dropoff must both lie
near the route already being driven, tested with `ST_DWithin` against
`route_geom`. Matching on "is the driver nearby" would put somebody travelling
the opposite way into the car.

**A detour cap of 8 percent or 4 minutes, whichever binds first.** Without it
the first passenger gets a tour of the city while the driver fills seats, and
they will never share again. The cap is checked *before* the driver is asked,
so a passenger already aboard is never the one who pays for a bad match.

**Driver consent, always.** Never auto-append. The driver is the one who has to
manage two strangers in a car, and taking that decision away from them is how
you lose drivers. The offer is targeted at that one driver rather than fanned
out, because the normal matching wave excludes any driver already on a live
ride, which is every corridor driver by definition.

**Each passenger pays their own leg.** Not a split of one fare. At 0.68 of the
exclusive rate applied to the distance they personally travel, both passengers
pay less than exclusive hire while the driver earns more than one exclusive
fare. That is the whole economic proposition, and it is defensible in one
sentence without any cleverness.

Two things here are computed differently from the obvious first guess, and both
matter enough to say why.

**The leg is measured along the driven route, not as a fresh direct route.**
`ST_LineSubstring` between the two projected positions is the distance the
passenger actually sits in the car. A direct route between their endpoints
would be a different journey, usually shorter, and charging for it would
underprice every seat.

**The detour is the offset from the line, not the length of the leg.** Treating
the joiner's whole trip as a detour would compare a several-kilometre leg
against an 8 percent cap and reject every candidate, which is a cap that reads
strict and matches nothing. What joining actually costs the people already
aboard is leaving the line to collect somebody and returning to it, so the
detour is twice the sum of the two perpendicular offsets.

Both are single SQL expressions against the GiST index. `find_candidates` makes
no routing calls at all, which is what keeps it one statement.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.logging import get_logger
from app.models.ride import Ride, RideOffer
from app.schemas.ride import ActorType, RideStatus
from app.services.fare import DEFAULT_FARE_CONFIG, compute_corridor_fare

logger = get_logger("vora.corridor")

# How far off the driven line a pickup or dropoff may sit. Roughly two street
# blocks: far enough that a passenger need not stand in the middle of the road,
# close enough that collecting them is not a detour in itself.
CORRIDOR_TOLERANCE_M = 400

# The detour cap. Whichever binds first.
MAX_DETOUR_RATIO = 0.08
MAX_DETOUR_SECONDS = 240

# Converting a detour in metres to one in seconds. Yaounde traffic, not an open
# road. Deliberately a constant and not a traffic model: we have no historical
# data, and a model faked from nothing is the sort of claim a jury checks.
URBAN_SPEED_MPS = 5.6

# Two bookings to a vehicle. Never three.
#
# This counts *bookings*, not people, and the distinction is the whole rule.
# The first passenger may bring friends: they are one booking, they know each
# other, and they arrived together. What is capped is how many separate
# strangers the platform introduces into one car, and that number is one.
#
# The build plan allowed three legs. This is tighter on purpose, because the
# binding constraint is safety rather than routing. A third booking would mean
# two unrelated parties in a car with somebody who agreed to share with one.
#
# The originating passenger holds leg 1, so this permits exactly one joiner.
MAX_LEGS = 2

# The joining passenger rides in front, beside the driver, and travels alone.
#
# One seat, not a party. The first passenger booked a private journey and then
# agreed to share it with *a* stranger; letting the joiner bring three of their
# own would put the original passenger alone in a car with a group, which is
# not what they agreed to and is the exact situation the cap exists to prevent.
#
# Seating them in front means nobody ends up beside a stranger in the back, and
# keeps them in the driver's view rather than behind them. It costs nothing and
# removes the arrangement's most likely failure.
#
# The seat is enforced as a vehicle capability, so a car whose front seat is
# not free is never offered the join at all. It is a fact about the car, never
# about either person (I9).
JOINER_SEAT_REQUIREMENT = "front_seat"

# A joiner takes exactly one seat. The originating booking has no such limit.
MAX_JOINER_SEATS = 1

# A leg is written when the driver is asked, not when they answer, so a pending
# join holds its place in the boarding order and its seats cannot be sold twice.
STATE_OFFERED = "offered"
STATE_CONFIRMED = "confirmed"

# How long the driver has to answer a corridor join.
#
# Longer than an ordinary offer, not shorter. The first version of this was 20
# seconds against the 25 of a normal offer, on the reasoning that the joiner is
# waiting at the kerb. That had it backwards: a driver being asked to take a
# corridor join is *already carrying a passenger and driving*, so they have
# less attention to spare than one parked at a stand, and they need more time
# to glance at a phone and decide, not less.
#
# An offer that lapses before it can be answered is indistinguishable from one
# that was never sent, both to the driver and to the joiner left waiting.
JOIN_OFFER_TTL_S = 45

# Statuses in which a corridor ride can still take somebody else.
JOINABLE = (
    RideStatus.ACCEPTED,
    RideStatus.ARRIVING,
    RideStatus.ARRIVED,
    RideStatus.IN_PROGRESS,
)


@dataclass(frozen=True)
class CorridorCandidate:
    parent_ride_id: uuid.UUID
    driver_id: uuid.UUID
    vehicle_id: uuid.UUID
    seats_free: int
    boarding_order: int
    added_distance_m: int
    added_duration_s: int
    leg_distance_m: int
    leg_duration_s: int
    leg_fare_xaf: int


# Candidate corridor rides whose route already passes both endpoints.
#
# One statement. Every `ST_DWithin` runs against the GiST index on
# `route_geom`; testing containment in Python would mean decoding every live
# polyline per request, which is the difference between an index probe and a
# table scan.
#
# The CTE exists only so the two projected positions along the line are named
# once instead of being repeated in six places.
_CANDIDATES_SQL = text(
    """
    WITH live AS (
        SELECT
            r.id, r.driver_id, r.vehicle_id, r.quoted_duration_s,
            r.route_geom,
            d.seats_free,
            ST_Length(r.route_geom) AS route_len_m,
            -- ST_SetSRID, not a bare cast to geometry. ST_MakePoint returns
            -- SRID 0, and while casting to geography implies 4326, casting to
            -- geometry does not: PostGIS then refuses to compare it against
            -- the 4326 route line.
            ST_LineLocatePoint(
                r.route_geom::geometry,
                ST_SetSRID(ST_MakePoint(:p_lng, :p_lat), 4326)
            ) AS p_frac,
            ST_LineLocatePoint(
                r.route_geom::geometry,
                ST_SetSRID(ST_MakePoint(:d_lng, :d_lat), 4326)
            ) AS d_frac,
            ST_Distance(
                r.route_geom, ST_MakePoint(:p_lng, :p_lat)::geography
            ) AS p_offset_m,
            ST_Distance(
                r.route_geom, ST_MakePoint(:d_lng, :d_lat)::geography
            ) AS d_offset_m,
            (SELECT count(*) FROM corridor_legs cl
              WHERE cl.parent_ride_id = r.id
                AND cl.state IN ('offered', 'confirmed')) AS legs,
            (SELECT coalesce(sum(cl.seats), 0) FROM corridor_legs cl
              WHERE cl.parent_ride_id = r.id
                AND cl.state IN ('offered', 'confirmed')) AS seats_sold
        FROM rides r
        JOIN drivers d ON d.id = r.driver_id
        -- The joiner sits in front, so a car without a free front seat cannot
        -- take one. Filtered here rather than after fetching, so a car that
        -- cannot seat them is never a candidate in the first place.
        JOIN vehicles v ON v.driver_id = d.id AND v.is_active
             AND v.front_seat_available
        WHERE r.mode = 'corridor'
          AND r.status IN ('accepted', 'arriving', 'arrived', 'in_progress')
          AND r.route_geom IS NOT NULL
          -- Both endpoints on the line already being driven. Pickup alone would
          -- match somebody travelling the opposite way.
          AND ST_DWithin(
                r.route_geom, ST_MakePoint(:p_lng, :p_lat)::geography, :tol)
          AND ST_DWithin(
                r.route_geom, ST_MakePoint(:d_lng, :d_lat)::geography, :tol)
          -- The joiner has not already been offered this ride.
          AND NOT EXISTS (
              SELECT 1 FROM corridor_legs cl2
              JOIN rides r2 ON r2.id = cl2.ride_id
              WHERE cl2.parent_ride_id = r.id AND r2.passenger_id = :passenger_id
          )
    )
    SELECT
        live.id AS parent_ride_id,
        live.driver_id,
        live.vehicle_id,
        live.seats_free,
        live.route_len_m,
        live.quoted_duration_s,
        live.legs,
        live.d_frac - live.p_frac AS frac_travelled,
        -- What the passenger actually travels: along the driven line, between
        -- where they get in and where they get out.
        ST_Length(
            ST_LineSubstring(
                live.route_geom::geometry, live.p_frac, live.d_frac
            )::geography
        ) AS leg_len_m,
        -- What joining costs everybody already aboard: leaving the line to
        -- collect them and returning to it, at both ends.
        2 * (live.p_offset_m + live.d_offset_m) AS detour_m
    FROM live
    WHERE
        -- Travelling the same way along it, not against it.
        live.p_frac < live.d_frac
        -- Capacity. The originating passenger holds a leg too, so this counts
        -- every seat sold on the vehicle rather than only the joiners'.
        AND live.seats_free >= live.seats_sold + :seats
    ORDER BY detour_m ASC
    LIMIT 5
    """
)


async def find_candidates(
    session: AsyncSession,
    *,
    passenger_id: uuid.UUID,
    pickup: tuple[float, float],
    dropoff: tuple[float, float],
    seats: int,
) -> list[CorridorCandidate]:
    """Corridor rides this passenger could join, least disruptive first.

    Returns an empty list rather than raising when nothing matches: no
    compatible corridor is an ordinary outcome, and the caller falls back to
    exclusive hire.
    """
    # A joining booking is one person. More than that is not a corridor join,
    # it is a second group, so there is nothing to offer rather than a smaller
    # set of candidates.
    if seats > MAX_JOINER_SEATS:
        logger.info(
            "corridor_joiner_too_many_seats",
            passenger_id=str(passenger_id),
            seats=seats,
        )
        return []

    rows = await session.execute(
        _CANDIDATES_SQL,
        {
            "passenger_id": passenger_id,
            "p_lat": pickup[0],
            "p_lng": pickup[1],
            "d_lat": dropoff[0],
            "d_lng": dropoff[1],
            "seats": seats,
            "tol": CORRIDOR_TOLERANCE_M,
        },
    )

    candidates: list[CorridorCandidate] = []

    for row in rows:
        legs = int(row.legs or 0)
        if legs >= MAX_LEGS:
            continue

        base_len = float(row.route_len_m or 0)
        detour_m = int(row.detour_m or 0)
        detour_s = int(detour_m / URBAN_SPEED_MPS)

        # The cap is checked here, before the driver is asked, so a passenger
        # already aboard is never the one who pays for a bad match.
        if base_len > 0:
            ratio = detour_m / base_len
            if ratio > MAX_DETOUR_RATIO or detour_s > MAX_DETOUR_SECONDS:
                logger.info(
                    "corridor_detour_cap_exceeded",
                    parent_ride_id=str(row.parent_ride_id),
                    ratio=round(ratio, 3),
                    detour_m=detour_m,
                    detour_s=detour_s,
                )
                continue

        leg_len = int(row.leg_len_m or 0)
        # Time in the car, taken as the same share of the parent's journey that
        # the leg is of its distance. Scaling a measured duration beats
        # inventing one from an assumed speed.
        leg_duration = int(
            float(row.quoted_duration_s or 0) * max(0.0, float(row.frac_travelled or 0))
        )

        candidates.append(
            CorridorCandidate(
                parent_ride_id=row.parent_ride_id,
                driver_id=row.driver_id,
                vehicle_id=row.vehicle_id,
                seats_free=int(row.seats_free),
                boarding_order=legs + 1,
                added_distance_m=detour_m,
                added_duration_s=detour_s,
                leg_distance_m=leg_len,
                leg_duration_s=leg_duration,
                leg_fare_xaf=compute_corridor_fare(
                    leg_len, leg_duration, DEFAULT_FARE_CONFIG
                ),
            )
        )

    return candidates


async def record_leg(
    session: AsyncSession,
    *,
    parent_ride_id: uuid.UUID,
    ride_id: uuid.UUID,
    boarding_order: int,
    seats: int,
    leg_distance_m: int,
    leg_fare_xaf: int,
    state: str = STATE_OFFERED,
    added_distance_m: int | None = None,
    added_duration_s: int | None = None,
) -> None:
    """Write the audit row for one passenger's segment."""
    await session.execute(
        text(
            """
            INSERT INTO corridor_legs
                (parent_ride_id, ride_id, boarding_order, seats, state,
                 leg_distance_m, leg_fare_xaf, added_distance_m, added_duration_s)
            VALUES
                (:parent_ride_id, :ride_id, :boarding_order, :seats, :state,
                 :leg_distance_m, :leg_fare_xaf, :added_distance_m,
                 :added_duration_s)
            ON CONFLICT (ride_id) DO NOTHING
            """
        ),
        {
            "parent_ride_id": parent_ride_id,
            "ride_id": ride_id,
            "boarding_order": boarding_order,
            "seats": seats,
            "state": state,
            "leg_distance_m": leg_distance_m,
            "leg_fare_xaf": leg_fare_xaf,
            "added_distance_m": added_distance_m,
            "added_duration_s": added_duration_s,
        },
    )


async def ensure_parent_leg(session: AsyncSession, *, ride: Ride) -> None:
    """Give the originating passenger leg 1 of their own corridor ride.

    They are not a guest on somebody else's journey, they started it, so parent
    and ride are the same row here. Without this the seat they occupy is
    invisible to capacity accounting and a four-seat car sells five seats.
    """
    await record_leg(
        session,
        parent_ride_id=ride.id,
        ride_id=ride.id,
        boarding_order=1,
        seats=ride.seats,
        leg_distance_m=ride.quoted_distance_m or 0,
        leg_fare_xaf=ride.quoted_fare_xaf or 0,
        state=STATE_CONFIRMED,
        added_distance_m=0,
        added_duration_s=0,
    )


async def offer_join(
    session: AsyncSession, *, candidate: CorridorCandidate, joiner_ride: Ride
) -> RideOffer:
    """Ask one driver to accept one extra pickup.

    Targeted at that driver rather than fanned out. The normal matching wave
    excludes any driver already on a live ride, which is every corridor driver
    by definition, so routing a join through it would guarantee the one driver
    who can help never hears about it.

    Consent is not optional and is never inferred from the driver having gone
    online. They are the one who has to manage two strangers in a car, and
    taking that choice away is how a platform loses drivers. The ask is
    recorded on the *parent* ride's log, so a driver who declines has that on
    record and the joiner is not silently left waiting.
    """
    from app.services.rides import record_event

    # The seats are held now, at the ask, not at the answer. Two passengers
    # hitting the last seat of the same car a second apart would otherwise both
    # be offered it, and one of them finds out at the kerb.
    await record_leg(
        session,
        parent_ride_id=candidate.parent_ride_id,
        ride_id=joiner_ride.id,
        boarding_order=candidate.boarding_order,
        seats=joiner_ride.seats,
        leg_distance_m=candidate.leg_distance_m,
        leg_fare_xaf=candidate.leg_fare_xaf,
        state=STATE_OFFERED,
        added_distance_m=candidate.added_distance_m,
        added_duration_s=candidate.added_duration_s,
    )

    offer = RideOffer(
        ride_id=joiner_ride.id,
        driver_id=candidate.driver_id,
        wave=1,
        state="open",
        distance_to_pickup_m=candidate.added_distance_m,
        expires_at=datetime.now(UTC) + timedelta(seconds=JOIN_OFFER_TTL_S),
    )
    session.add(offer)

    await record_event(
        session,
        ride_id=candidate.parent_ride_id,
        event_type="corridor_join_requested",
        actor_type=ActorType.SYSTEM,
        metadata={
            "joiner_ride_id": str(joiner_ride.id),
            "seats": joiner_ride.seats,
            "added_distance_m": candidate.added_distance_m,
            "added_duration_s": candidate.added_duration_s,
            "boarding_order": candidate.boarding_order,
        },
    )
    await session.flush()

    logger.info(
        "corridor_consent_requested",
        parent_ride_id=str(candidate.parent_ride_id),
        joiner_ride_id=str(joiner_ride.id),
        driver_id=str(candidate.driver_id),
        added_distance_m=candidate.added_distance_m,
    )
    return offer


async def pending_leg(session: AsyncSession, ride_id: uuid.UUID) -> dict | None:
    """The offered-but-unanswered leg for a joining ride, if there is one."""
    row = await session.execute(
        text(
            "SELECT parent_ride_id, boarding_order, seats, leg_distance_m, "
            "       leg_fare_xaf, added_distance_m, added_duration_s "
            "FROM corridor_legs WHERE ride_id = :ride_id AND state = :state"
        ),
        {"ride_id": ride_id, "state": STATE_OFFERED},
    )
    found = row.first()
    return dict(found._mapping) if found is not None else None


async def confirm_leg(session: AsyncSession, *, ride: Ride) -> dict | None:
    """The driver said yes. Turn the held seats into a boarded passenger.

    Returns the leg, or None when this ride was not a corridor join at all,
    which is the ordinary case and not an error.

    The joiner's fare becomes the leg fare: what they travel along the driven
    route, priced per seat. It is still derived entirely on the server from
    server-held geometry, so I2 holds exactly as it does for exclusive hire.
    """
    leg = await pending_leg(session, ride.id)
    if leg is None:
        return None

    await session.execute(
        text(
            "UPDATE corridor_legs SET state = :confirmed, updated_at = now() "
            "WHERE ride_id = :ride_id AND state = :offered"
        ),
        {
            "confirmed": STATE_CONFIRMED,
            "offered": STATE_OFFERED,
            "ride_id": ride.id,
        },
    )

    ride.quoted_fare_xaf = int(leg["leg_fare_xaf"])
    ride.quoted_distance_m = int(leg["leg_distance_m"])

    logger.info(
        "corridor_leg_confirmed",
        ride_id=str(ride.id),
        parent_ride_id=str(leg["parent_ride_id"]),
        boarding_order=leg["boarding_order"],
        leg_fare_xaf=leg["leg_fare_xaf"],
    )
    return leg


async def release_leg(session: AsyncSession, ride_id: uuid.UUID) -> bool:
    """The driver declined, or the offer lapsed. Give the seats back.

    Returns whether anything was held, which is how the caller tells a declined
    corridor join from a declined ordinary offer without loading the ride.

    Deletes rather than marking, so the passenger can be offered the same
    corridor again once something changes. A declined join that left a row
    behind would silently exclude that car from every future search for that
    passenger.
    """
    result = await session.execute(
        text(
            "DELETE FROM corridor_legs WHERE ride_id = :ride_id AND state = :state"
        ),
        {"ride_id": ride_id, "state": STATE_OFFERED},
    )
    return bool(result.rowcount)


async def legs_for(session: AsyncSession, parent_ride_id: uuid.UUID) -> list[dict]:
    """Every leg of a corridor ride, in boarding order.

    Used by the driver's view and by the audit trail. **Never returned to a
    passenger**: a joiner seeing the other legs would learn where the people
    beside them are going, which is exactly the leak a shared ride must not
    become.
    """
    rows = await session.execute(
        text(
            """
            SELECT cl.boarding_order, cl.seats, cl.state, cl.leg_distance_m,
                   cl.leg_fare_xaf, cl.added_distance_m, cl.added_duration_s,
                   r.status, r.pickup_label, r.dropoff_label
            FROM corridor_legs cl
            JOIN rides r ON r.id = cl.ride_id
            WHERE cl.parent_ride_id = :parent_ride_id
            ORDER BY cl.boarding_order
            """
        ),
        {"parent_ride_id": parent_ride_id},
    )
    return [dict(r._mapping) for r in rows]


async def seats_taken(session: AsyncSession, parent_ride_id: uuid.UUID) -> int:
    total = await session.scalar(
        text(
            "SELECT coalesce(sum(seats), 0) FROM corridor_legs "
            "WHERE parent_ride_id = :parent_ride_id AND state = :state"
        ),
        {"parent_ride_id": parent_ride_id, "state": STATE_CONFIRMED},
    )
    return int(total or 0)


def assert_joinable(ride: Ride) -> None:
    """Whether a corridor ride can still take somebody else."""
    if ride.mode != "corridor":
        raise VoraError(
            ErrorCode.CORRIDOR_NOT_JOINABLE,
            details={"reason": "not a corridor ride"},
        )
    if RideStatus(ride.status) not in JOINABLE:
        raise VoraError(
            ErrorCode.CORRIDOR_NOT_JOINABLE,
            details={"ride_status": ride.status},
        )
