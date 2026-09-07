"""Public trip-share route.

The only unauthenticated view of a ride in the system, which is why it returns
its own model rather than a filtered `Ride`. If it reused `Ride` with fields
blanked out, every field added later would default to being visible to anybody
holding a link. Here a field is exposed only because somebody wrote it into
`app/schemas/share.py`.

Absent by construction: passenger identity, fare, PIN, phone, trace history,
and the driver's full name.
"""

from __future__ import annotations

from fastapi import APIRouter, Path
from redis.exceptions import RedisError

from app.api.v1._stub import PUBLIC_ERRORS
from app.deps import ClientIp, SessionDep
from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.logging import get_logger
from app.schemas.share import ShareView
from app.services import sharing
from app.services.rate_limit import SHARE_VIEW_PER_IP, limiter

router = APIRouter(prefix="/share", tags=["share"])
logger = get_logger("vora.share")


@router.get(
    "/{token}",
    response_model=ShareView,
    responses=PUBLIC_ERRORS,
    summary="Follow a shared trip",
    description=(
        "No authentication. The token is signed, expiring and revocable, and "
        "the row behind it can be killed before the signature lapses.\n\n"
        "Location is coarse until the ride is in_progress, so a link shared "
        "before pickup does not reveal exactly where the passenger is waiting. "
        "An invalid, expired or revoked token all return 404 alike: telling "
        "them apart would say which links were ever real."
    ),
)
async def view_shared_ride(
    session: SessionDep,
    ip: ClientIp,
    token: str = Path(min_length=16, max_length=512),
) -> ShareView:
    # Rate limited because it is unauthenticated and enumerable. A signed token
    # is not guessable, but the endpoint should not be a free lookup service
    # for somebody working through a list of forwarded links.
    try:
        decision = await limiter.consume(SHARE_VIEW_PER_IP, ip)
        if not decision.allowed:
            raise VoraError(
                ErrorCode.RATE_LIMITED,
                details={"retry_after_s": max(decision.retry_after_s, 1)},
            )
    except RedisError:
        # Fails open. The cost of an outage here is unthrottled reads of a
        # deliberately thin payload; the cost of failing closed is a worried
        # relative staring at an error while somebody is in a car.
        logger.warning("share_rate_limiter_unavailable_failing_open")

    ride = await sharing.resolve_token(session, token)

    # Assembled in one place, shared with the socket. See build_share_view.
    view = await sharing.build_share_view(session, ride)

    # resolve_token bumps the view counter, so this read has a write to commit.
    await session.commit()
    return view
