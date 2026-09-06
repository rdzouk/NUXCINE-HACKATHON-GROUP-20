"""Public trip-share route. Implemented in Phase 5.

The only unauthenticated view of a ride in the system. It returns a strict
subset defined by its own model, so a field added to `Ride` later cannot leak
here by default.
"""

from __future__ import annotations

from fastapi import APIRouter, Path

from app.api.v1._stub import PUBLIC_ERRORS, not_implemented
from app.schemas.share import ShareView

router = APIRouter(prefix="/share", tags=["share"])


@router.get(
    "/{token}",
    response_model=ShareView,
    responses=PUBLIC_ERRORS,
    summary="Follow a shared trip",
    description=(
        "No authentication. The token is signed, expiring and revocable. "
        "Location is coarse until the ride is in_progress, so a link shared "
        "before pickup does not reveal where the passenger is waiting. "
        "An invalid or expired token returns 404, never 403."
    ),
)
async def view_shared_ride(
    token: str = Path(min_length=16, max_length=512),
) -> ShareView:
    not_implemented("Phase 5")
