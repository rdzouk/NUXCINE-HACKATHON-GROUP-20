"""Development-only routes.

The simulator is the reason a solo live demo is possible at all. Without it,
showing live tracking needs two phones, two SIMs and a second person willing to
drive around Yaounde on cue. With it, one laptop shows a driver moving along a
real road at a believable speed.

**The whole router is gated on `DEBUG` and refuses to load in production.**
Not a flag checked inside each handler, which is the version somebody
eventually forgets: the router is not registered at all, so the paths do not
exist and do not appear in openapi.json. An endpoint that fabricates GPS
positions for arbitrary rides is exactly the thing that must not be reachable
on a real deployment.
"""

from __future__ import annotations

import asyncio
import itertools
import uuid
from datetime import UTC, datetime

import polyline as polyline_lib
from fastapi import APIRouter, status
from pydantic import Field
from sqlalchemy import select

from app.api.v1._stub import COMMON_ERRORS
from app.config import settings
from app.db import get_sessionmaker
from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.logging import get_logger
from app.models.ride import Ride
from app.schemas.common import VoraModel
from app.services import tracking
from app.services.realtime import get_registry
from app.services.routing import haversine_m

router = APIRouter(prefix="/dev", tags=["dev"])
logger = get_logger("vora.dev")

# How often the simulated driver emits a point. Matches what a real client
# sends, so the plausibility filter and the rate limiter see realistic traffic
# rather than a pattern that only works because it is synthetic.
TICK_S = 2.0

MAX_SIMULATION_S = 900


class SimulateDriverRequest(VoraModel):
    ride_id: uuid.UUID
    speed_kmh: float = Field(
        default=25.0,
        gt=0,
        le=120,
        description="Average speed along the route. Yaounde traffic averages 20 to 30.",
    )
    # Defaults to the ride's own route, which is what makes the marker follow
    # the road the passenger was quoted rather than a straight line across it.
    polyline: str | None = Field(
        default=None,
        max_length=100_000,
        description="Encoded polyline to walk. Defaults to the ride's route.",
    )


class SimulateDriverResponse(VoraModel):
    ride_id: uuid.UUID
    points: int
    estimated_duration_s: int
    speed_kmh: float


async def _walk(
    ride_id: uuid.UUID, path: list[tuple[float, float]], speed_kmh: float
) -> None:
    """Emit points along a path at a believable speed.

    Interpolates *between* polyline vertices rather than jumping vertex to
    vertex. OSRM vertices are hundreds of metres apart on a straight road, and
    jumping between them would look like teleporting on the map and might trip
    the plausibility filter the demo is meant to showcase.
    """
    speed_mps = speed_kmh / 3.6
    started = datetime.now(UTC)
    emitted = 0

    # Cumulative distance along the path, so a position at time t is a lookup
    # rather than a step count that drifts.
    segments: list[tuple[float, tuple[float, float], tuple[float, float]]] = []
    total = 0.0
    for a, b in itertools.pairwise(path):
        d = haversine_m(a[0], a[1], b[0], b[1])
        if d > 0:
            segments.append((total, a, b))
            total += d

    if total <= 0:
        return

    duration_s = min(total / speed_mps, MAX_SIMULATION_S)
    sessionmaker = get_sessionmaker()

    while True:
        elapsed = (datetime.now(UTC) - started).total_seconds()
        if elapsed > duration_s:
            break

        travelled = min(elapsed * speed_mps, total)

        # Locate the segment containing this distance and interpolate within it.
        lat = lng = None
        for i, (start_at, a, b) in enumerate(segments):
            seg_len = (
                segments[i + 1][0] - start_at
                if i + 1 < len(segments)
                else total - start_at
            )
            if travelled <= start_at + seg_len or i == len(segments) - 1:
                frac = (travelled - start_at) / seg_len if seg_len > 0 else 0.0
                frac = max(0.0, min(1.0, frac))
                lat = a[0] + (b[0] - a[0]) * frac
                lng = a[1] + (b[1] - a[1]) * frac
                break

        if lat is None:
            break

        async with sessionmaker() as session:
            ride = await session.get(Ride, ride_id)
            if ride is None or ride.status not in {
                s.value for s in tracking.TRACKABLE
            }:
                # The ride ended, so the simulation ends with it rather than
                # continuing to write points to a closed trace.
                logger.info("simulation_stopped_ride_not_trackable", ride_id=str(ride_id))
                return

            accepted, reason = await tracking.record_location(
                session,
                ride=ride,
                lat=lat,
                lng=lng,
                recorded_at=datetime.now(UTC),
                accuracy_m=8.0,
                speed_mps=speed_mps,
            )
            await session.commit()

        if accepted:
            await get_registry().publish_driver_location(
                ride_id=ride_id,
                payload={
                    "type": "driver_location",
                    "ride_id": str(ride_id),
                    "location": {
                        "lat": lat,
                        "lng": lng,
                        "heading": None,
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                    "eta_s": int(max(duration_s - elapsed, 0)),
                },
            )
            emitted += 1
        else:
            logger.warning("simulated_point_rejected", reason=reason)

        await asyncio.sleep(TICK_S)

    logger.info("simulation_finished", ride_id=str(ride_id), points=emitted)


@router.post(
    "/simulate-driver",
    response_model=SimulateDriverResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=COMMON_ERRORS,
    summary="Walk a synthetic driver along a ride's route (development only)",
    description=(
        "Emits realistic location frames along the ride's own route at a "
        "configurable speed, so live tracking can be demonstrated without a "
        "second phone and a second person.\n\n"
        "Returns immediately; the walk runs in the background and stops on its "
        "own when the ride leaves a trackable state. Points go through the same "
        "plausibility filter and the same fan-out as a real driver's, so what "
        "is demonstrated is the real path and not a special case."
    ),
)
async def simulate_driver(payload: SimulateDriverRequest) -> SimulateDriverResponse:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        ride = (
            await session.execute(select(Ride).where(Ride.id == payload.ride_id))
        ).scalar_one_or_none()

        if ride is None:
            raise VoraError(ErrorCode.RIDE_NOT_FOUND)

        if ride.status not in {s.value for s in tracking.TRACKABLE}:
            raise VoraError(
                ErrorCode.RIDE_STATE_CONFLICT,
                details={
                    "ride_status": ride.status,
                    "trackable": sorted(s.value for s in tracking.TRACKABLE),
                },
            )

        encoded = payload.polyline or ride.route_polyline

    if not encoded:
        raise VoraError(
            ErrorCode.RIDE_STATE_CONFLICT,
            details={"reason": "ride has no route polyline to follow"},
        )

    try:
        path = polyline_lib.decode(encoded)
    except (ValueError, IndexError) as exc:
        raise VoraError(
            ErrorCode.VALIDATION_FAILED, details={"field": "polyline"}
        ) from exc

    if len(path) < 2:
        raise VoraError(
            ErrorCode.VALIDATION_FAILED,
            details={"field": "polyline", "reason": "needs at least two points"},
        )

    total = sum(
        haversine_m(a[0], a[1], b[0], b[1]) for a, b in itertools.pairwise(path)
    )
    duration = int(min(total / (payload.speed_kmh / 3.6), MAX_SIMULATION_S))

    # asyncio.create_task, not Celery. The build plan rules out a broker, and a
    # simulation that dies with the process is the correct lifetime for a demo
    # affordance anyway.
    asyncio.create_task(_walk(payload.ride_id, path, payload.speed_kmh))  # noqa: RUF006

    logger.info(
        "simulation_started",
        ride_id=str(payload.ride_id),
        points=len(path),
        speed_kmh=payload.speed_kmh,
        duration_s=duration,
    )

    return SimulateDriverResponse(
        ride_id=payload.ride_id,
        points=len(path),
        estimated_duration_s=duration,
        speed_kmh=payload.speed_kmh,
    )


@router.get(
    "/realtime-stats",
    responses=COMMON_ERRORS,
    summary="Live socket registry counts (development only)",
)
async def realtime_stats() -> dict:
    return await get_registry().stats()


class OtpPeekResponse(VoraModel):
    phone: str
    code: str | None = Field(
        default=None,
        description="The last code sent to this number by this process.",
    )


@router.get(
    "/otp/{phone}",
    response_model=OtpPeekResponse,
    responses=COMMON_ERRORS,
    summary="Read back the last OTP for a number (development only)",
    description=(
        "Returns the code the console sender last delivered to this number, so "
        "a demo does not have to pause while somebody reads it out of the "
        "container logs.\n\n"
        "This exists only because there is no SMS gateway wired. It lives on "
        "the dev router, which is not registered unless DEBUG is on and the "
        "environment is not production, so the path does not exist on a real "
        "deployment rather than being guarded inside the handler. Wire a real "
        "SmsSender and this returns nothing, because the console sender is no "
        "longer the one delivering."
    ),
)
async def peek_otp(phone: str) -> OtpPeekResponse:
    from app.services.sms import get_sms_sender

    sender = get_sms_sender()

    # Both the console sender and the routing sender expose peek(); a real
    # gateway on its own does not, because nothing there ever saw the code.
    peek = getattr(sender, "peek", None)
    if peek is None:
        return OtpPeekResponse(phone=phone, code=None)

    return OtpPeekResponse(phone=phone, code=peek(phone))


def is_enabled() -> bool:
    """Whether these routes may be registered at all.

    Two conditions, not one. `DEBUG` alone would be a single typo away from
    exposing a GPS-fabrication endpoint on a real deployment.
    """
    return settings.debug and not settings.is_production
