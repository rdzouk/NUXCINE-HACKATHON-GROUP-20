"""ORM to contract conversion.

Every response body is built here rather than by handing an ORM object to
Pydantic with `from_attributes`. That is the point: automatic attribute mapping
means any column added to a model later is exposed by default, and the columns
this system adds later are GPS traces, KYC references and phone numbers.

Here, a field reaches a client only because somebody wrote a line to put it
there. Exposure is opt-in, and the diff that exposes something is visible.
"""

from __future__ import annotations

from app.models.user import Driver, User
from app.schemas.user import (
    AccessibilityProfile,
    DriverProfile,
    KycStatus,
)
from app.schemas.user import (
    User as UserSchema,
)


def serialize_accessibility(user: User) -> AccessibilityProfile:
    return AccessibilityProfile(
        requires_ramp=user.requires_ramp,
        requires_boot_space=user.requires_boot_space,
        requires_front_seat=user.requires_front_seat,
        requires_driver_assist=user.requires_driver_assist,
        allows_guide_animal=user.allows_guide_animal,
        prefers_text_contact=user.prefers_text_contact,
    )


def serialize_driver_profile(driver: Driver) -> DriverProfile:
    return DriverProfile(
        kyc_status=KycStatus(driver.kyc_status),
        kyc_reviewed_at=driver.kyc_reviewed_at,
        rating_avg=float(driver.rating_avg) if driver.rating_avg is not None else None,
        is_online=driver.is_online,
        seats_free=driver.seats_free,
    )


def serialize_user(user: User, *, outstanding_xaf: int = 0) -> UserSchema:
    """The caller's own user object.

    `phone_e164` is included because this is the caller's own number. It is
    never populated on a nested driver or passenger summary, which is what I3
    actually prohibits: exposing a *counterparty's* number.

    `outstanding_xaf` is a parameter rather than a lookup because the ledger
    does not exist until Phase 5. It defaults to zero, and Phase 5 passes the
    real balance in without changing this signature or the response shape.
    """
    return UserSchema(
        id=user.id,
        display_name=user.display_name,
        role=user.role,
        status=user.status,
        locale=user.locale,
        phone_e164=user.phone_e164,
        accessibility=serialize_accessibility(user),
        outstanding_xaf=outstanding_xaf,
        driver=serialize_driver_profile(user.driver) if user.driver else None,
        created_at=user.created_at,
    )
