"""Location ingest: validate, judge, persist, fan out.

The order is deliberate. A point is judged *before* it is stored and stored
*whatever the verdict*, because the record of a rejected point is worth more
than its absence. Fan-out happens only for accepted points: a passenger
watching a map should not see the driver teleport because somebody was
fiddling with a patched client.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from geoalchemy2 import WKTElement
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging import get_logger
from app.models.ride import Ride, RideTrace
from app.schemas.ride import ActorType, RideStatus
from app.services.plausibility import Point, check
from app.services.rides import record_event

logger = get_logger("vora.tracking")

# Statuses in which a driver's location is worth recording. Before acceptance
# there is no ride to attribute it to; after completion the trace is closed and
# late points would change a fare that has already been charged.
TRACKABLE = frozenset(
    {
        RideStatus.ACCEPTED,
        RideStatus.ARRIVING,
        RideStatus.ARRIVED,
        RideStatus.IN_PROGRESS,
    }
)


async def last_point(session: AsyncSession, ride_id: uuid.UUID) -> Point | None:
    """The most recent accepted point, which is what the next one is judged against.

    Accepted only. Judging against a rejected point would let one bad point
    poison the rest of the trace: a teleport becomes the new baseline, and
    everything after it looks plausible relative to a place the driver never was.
    """
    row = (
        await session.execute(
            text(
                "SELECT ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng, "
                "recorded_at, accuracy_m, speed_mps "
                "FROM ride_traces "
                "WHERE ride_id = :ride_id AND NOT rejected "
                "ORDER BY seq DESC LIMIT 1"
            ),
            {"ride_id": ride_id},
        )
    ).first()

    if row is None:
        return None
    return Point(
        lat=row.lat,
        lng=row.lng,
        recorded_at=row.recorded_at,
        accuracy_m=row.accuracy_m,
        speed_mps=row.speed_mps,
    )


async def record_location(
    session: AsyncSession,
    *,
    ride: Ride,
    lat: float,
    lng: float,
    recorded_at: datetime,
    accuracy_m: float | None = None,
    speed_mps: float | None = None,
) -> tuple[bool, str | None]:
    """Judge and store one point. Returns (accepted, reject_reason).

    Always writes a row. A rejected point carries `rejected = true` and the
    reason, which is what makes a forged trace provable after the fact rather
    than merely suspected.
    """
    point = Point(
        lat=lat,
        lng=lng,
        recorded_at=recorded_at,
        accuracy_m=accuracy_m,
        speed_mps=speed_mps,
    )
    previous = await last_point(session, ride.id)
    verdict = check(point, previous, now=datetime.now(UTC))

    next_seq = (
        await session.scalar(
            select(func.coalesce(func.max(RideTrace.seq), -1) + 1).where(
                RideTrace.ride_id == ride.id
            )
        )
    ) or 0

    session.add(
        RideTrace(
            ride_id=ride.id,
            seq=next_seq,
            geom=WKTElement(f"POINT({lng} {lat})", srid=4326),
            speed_mps=speed_mps,
            accuracy_m=accuracy_m,
            recorded_at=recorded_at,
            rejected=verdict.rejected,
            reject_reason=verdict.reason.value if verdict.reason else None,
        )
    )

    if verdict.rejected:
        # Into the ride's own history too, not just the trace table. A fare
        # dispute is read from ride_events, and "the driver's client submitted
        # eleven impossible points" belongs in that story.
        await record_event(
            session,
            ride_id=ride.id,
            event_type="trace_point_rejected",
            actor_type=ActorType.SYSTEM,
            reason=verdict.reason.value if verdict.reason else None,
            metadata={
                "seq": next_seq,
                "implied_speed_mps": round(verdict.implied_speed_mps, 2)
                if verdict.implied_speed_mps not in (None, float("inf"))
                else None,
                "distance_m": round(verdict.distance_m, 1)
                if verdict.distance_m is not None
                else None,
            },
        )
        logger.warning(
            "trace_point_rejected",
            ride_id=str(ride.id),
            reason=verdict.reason.value if verdict.reason else None,
            seq=next_seq,
        )

    await session.flush()
    return verdict.accepted, verdict.reason.value if verdict.reason else None


async def traced_distance_m(session: AsyncSession, ride_id: uuid.UUID) -> int:
    """Distance along the accepted trace. What the final fare is computed from.

    Rejected points are excluded by the WHERE clause rather than by ordering
    around them, so a forged point cannot contribute a single metre to a fare
    even if it sits in the middle of an otherwise honest journey.
    """
    length = await session.scalar(
        text(
            "SELECT ST_Length(ST_MakeLine(geom::geometry ORDER BY seq)::geography) "
            "FROM ride_traces WHERE ride_id = :ride_id AND NOT rejected"
        ),
        {"ride_id": ride_id},
    )
    return int(length or 0)
