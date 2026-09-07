"""SOS and incident reports.

**The snapshot is the feature.** Anyone can add a panic button; what makes it
worth something afterwards is that the state at the moment it was pressed is
sealed and cannot drift. By the time a report is reviewed the ride may have
completed, the driver may have gone offline, the trace may have grown. An
incident that reads the ride live would answer the wrong question.

So `snapshot` is written once, `NOT NULL`, and a database trigger refuses any
UPDATE that changes it.

**SOS gets its own path.** It must succeed under partial degradation, because
the one time it is pressed in earnest is the one time something else is
probably also wrong. It therefore takes no description, needs no counterparty
lookup to succeed, and degrades to a smaller snapshot rather than failing if
part of the gathering fails.

This is also the layer that encrypted incident audio would attach to, which is
described in ARCHITECTURE.md as designed and not built.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging import get_logger
from app.models.ride import Ride
from app.models.safety import IncidentReport
from app.schemas.ride import ActorType, IncidentCategory
from app.services.rides import record_event

logger = get_logger("vora.incidents")


async def _build_snapshot(session: AsyncSession, ride: Ride) -> dict[str, Any]:
    """Gather the evidence. Never raises.

    Each part is optional and failure-tolerant on purpose. An SOS that fails
    because one query timed out is worse than an SOS with a thinner snapshot,
    and this runs at exactly the moment the system is least likely to be
    healthy.
    """
    snapshot: dict[str, Any] = {
        "sealed_at": datetime.now(UTC).isoformat(),
        "ride": {
            "id": str(ride.id),
            "status": ride.status,
            "mode": ride.mode,
            "seats": ride.seats,
            "pickup_label": ride.pickup_label,
            "dropoff_label": ride.dropoff_label,
            "quoted_fare_xaf": ride.quoted_fare_xaf,
            "accepted_at": ride.accepted_at.isoformat() if ride.accepted_at else None,
            "started_at": ride.started_at.isoformat() if ride.started_at else None,
        },
        "passenger_id": str(ride.passenger_id),
        "driver_id": str(ride.driver_id) if ride.driver_id else None,
        "vehicle_id": str(ride.vehicle_id) if ride.vehicle_id else None,
    }

    try:
        vehicle = (
            await session.execute(
                text(
                    "SELECT plate, make, model, color FROM vehicles WHERE id = :id"
                ),
                {"id": ride.vehicle_id},
            )
        ).first()
        if vehicle is not None:
            # Identifying the car matters more than anything else here: it is
            # what a responder or a relative can act on.
            snapshot["vehicle"] = {
                "plate": vehicle.plate,
                "make": vehicle.make,
                "model": vehicle.model,
                "color": vehicle.color,
            }
    except Exception:
        logger.exception("snapshot_vehicle_failed", ride_id=str(ride.id))

    try:
        trace = (
            await session.execute(
                text(
                    """
                    SELECT
                        count(*) FILTER (WHERE NOT rejected) AS accepted_points,
                        count(*) FILTER (WHERE rejected)     AS rejected_points,
                        min(recorded_at)                     AS first_at,
                        max(recorded_at)                     AS last_at,
                        ST_Y(
                            (array_agg(geom::geometry ORDER BY seq DESC)
                             FILTER (WHERE NOT rejected))[1]
                        ) AS last_lat,
                        ST_X(
                            (array_agg(geom::geometry ORDER BY seq DESC)
                             FILTER (WHERE NOT rejected))[1]
                        ) AS last_lng
                    FROM ride_traces WHERE ride_id = :ride_id
                    """
                ),
                {"ride_id": ride.id},
            )
        ).first()
        if trace is not None:
            snapshot["trace"] = {
                "accepted_points": int(trace.accepted_points or 0),
                # A rejected count above zero in an incident is itself a signal.
                "rejected_points": int(trace.rejected_points or 0),
                "first_at": trace.first_at.isoformat() if trace.first_at else None,
                "last_at": trace.last_at.isoformat() if trace.last_at else None,
                "last_known_lat": trace.last_lat,
                "last_known_lng": trace.last_lng,
            }
    except Exception:
        logger.exception("snapshot_trace_failed", ride_id=str(ride.id))

    return snapshot


async def _counterparty(session: AsyncSession, ride: Ride, reporter_id: uuid.UUID):
    """Who the report is about. None rather than raising if it cannot be found."""
    if ride.passenger_id == reporter_id:
        if ride.driver_id is None:
            return None
        return await session.scalar(
            text("SELECT user_id FROM drivers WHERE id = :id"), {"id": ride.driver_id}
        )
    return ride.passenger_id


async def raise_sos(
    session: AsyncSession, *, ride: Ride, reporter_id: uuid.UUID
) -> IncidentReport:
    """Panic button. Seals evidence and alerts.

    Category is fixed to `safety` and no description is taken: somebody
    pressing this is not going to type, and asking them to would make the
    feature useless in the situation it exists for.
    """
    snapshot = await _build_snapshot(session, ride)
    reported_id = await _counterparty(session, ride, reporter_id)

    incident = IncidentReport(
        ride_id=ride.id,
        reporter_id=reporter_id,
        reported_id=reported_id,
        category=IncidentCategory.SAFETY.value,
        description=None,
        snapshot=snapshot,
        is_sos=True,
    )
    session.add(incident)
    await session.flush()

    await record_event(
        session,
        ride_id=ride.id,
        event_type="sos_raised",
        actor_type=ActorType.PASSENGER
        if ride.passenger_id == reporter_id
        else ActorType.DRIVER,
        actor_id=reporter_id,
        reason="sos",
        metadata={"incident_id": str(incident.id)},
    )

    # Logged at error level on purpose. This is the one line in the system that
    # should page a human, and it is what an alerting rule would key on.
    logger.error(
        "SOS_RAISED",
        incident_id=str(incident.id),
        ride_id=str(ride.id),
        reporter_id=str(reporter_id),
        ride_status=ride.status,
    )
    return incident


async def file_report(
    session: AsyncSession,
    *,
    ride: Ride,
    reporter_id: uuid.UUID,
    category: IncidentCategory,
    description: str,
) -> IncidentReport:
    """A considered report, filed after the fact.

    Same sealed snapshot as an SOS. A fare dispute raised a day later still
    needs the trace as it was, not as it is.
    """
    snapshot = await _build_snapshot(session, ride)
    reported_id = await _counterparty(session, ride, reporter_id)

    incident = IncidentReport(
        ride_id=ride.id,
        reporter_id=reporter_id,
        reported_id=reported_id,
        category=category.value,
        description=description,
        snapshot=snapshot,
        is_sos=False,
    )
    session.add(incident)
    await session.flush()

    await record_event(
        session,
        ride_id=ride.id,
        event_type="incident_reported",
        actor_type=ActorType.PASSENGER
        if ride.passenger_id == reporter_id
        else ActorType.DRIVER,
        actor_id=reporter_id,
        reason=category.value,
        metadata={"incident_id": str(incident.id)},
    )

    logger.warning(
        "incident_reported",
        incident_id=str(incident.id),
        ride_id=str(ride.id),
        category=category.value,
    )
    return incident
