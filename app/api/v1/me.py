"""Current-user routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1._stub import COMMON_ERRORS, not_implemented
from app.deps import CurrentUser, SessionDep
from app.schemas.user import BalanceResponse, UserResponse, UserUpdateRequest
from app.services.serializers import serialize_user

router = APIRouter(tags=["me"])


@router.get(
    "/me",
    response_model=UserResponse,
    responses=COMMON_ERRORS,
    summary="The caller's own profile",
)
async def get_me(user: CurrentUser) -> UserResponse:
    return UserResponse(user=serialize_user(user))


@router.patch(
    "/me",
    response_model=UserResponse,
    responses=COMMON_ERRORS,
    summary="Update display name, locale or accessibility requirements",
    description=(
        "Accessibility values are vehicle capability requirements and are "
        "writable only by the user themselves. They are never inferred, never "
        "derived from behaviour, and never shown to a driver as anything other "
        "than a vehicle requirement (I9, Law 2024/017)."
    ),
)
async def update_me(
    payload: UserUpdateRequest, user: CurrentUser, session: SessionDep
) -> UserResponse:
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.locale is not None:
        user.locale = payload.locale

    if payload.accessibility is not None:
        a = payload.accessibility
        # Written field by field rather than by looping over the model, so that
        # a field added to AccessibilityProfile later is not silently made
        # writable here without someone deciding that it should be.
        user.requires_ramp = a.requires_ramp
        user.requires_boot_space = a.requires_boot_space
        user.requires_front_seat = a.requires_front_seat
        user.requires_driver_assist = a.requires_driver_assist
        user.allows_guide_animal = a.allows_guide_animal
        user.prefers_text_contact = a.prefers_text_contact

    await session.commit()
    await session.refresh(user)
    return UserResponse(user=serialize_user(user))


@router.get(
    "/me/balance",
    response_model=BalanceResponse,
    responses=COMMON_ERRORS,
    summary="Outstanding cancellation debt",
    description=(
        "Booking is refused with OUTSTANDING_BALANCE while this is above zero. "
        "This route is not in the original §6 draft; it was added at Phase 0 "
        "because the cancellation ledger otherwise blocks booking with no way "
        "for the client to explain why or clear it."
    ),
)
async def get_balance(user: CurrentUser) -> BalanceResponse:
    # The ledger lands in Phase 5. Kept as a 501 rather than returning a
    # hardcoded zero: a client that sees a real zero will trust it and skip
    # the settle-before-booking flow entirely.
    not_implemented("Phase 5")
