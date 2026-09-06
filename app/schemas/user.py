"""The `user` object, returned by /auth/otp/verify, GET /me and PATCH /me.

§6 referenced `{ user }` without defining it. This is that definition.

Two rules govern what is in here:
  I3  a counterparty's phone never appears in any response. `phone_e164` is
      present only on the caller's own user object and never on a nested
      driver or passenger summary.
  I9  accessibility is a set of vehicle capability requirements, not a medical
      or personal attribute.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from app.schemas.common import UserRole, UserStatus, VehicleCapability, VoraModel


class KycStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class AccessibilityProfile(VoraModel):
    """Standing vehicle requirements for this user's trips.

    Read I9 before adding a field here. Anything that describes the person
    rather than the vehicle they need does not belong in this model, in this
    database, or in this country's legal envelope.
    """

    requires_ramp: bool = False
    requires_boot_space: bool = False
    requires_front_seat: bool = False
    requires_driver_assist: bool = False
    allows_guide_animal: bool = False
    # A communication preference, not a vehicle capability. It is never used as
    # a matching predicate; it selects canned messages over a voice call.
    prefers_text_contact: bool = False

    def to_capabilities(self) -> list[VehicleCapability]:
        mapping = {
            VehicleCapability.RAMP: self.requires_ramp,
            VehicleCapability.BOOT_SPACE: self.requires_boot_space,
            VehicleCapability.FRONT_SEAT: self.requires_front_seat,
            VehicleCapability.DRIVER_ASSIST: self.requires_driver_assist,
            VehicleCapability.GUIDE_ANIMAL: self.allows_guide_animal,
        }
        return [cap for cap, required in mapping.items() if required]


class DriverProfile(VoraModel):
    """Present on the user object only when role == driver."""

    kyc_status: KycStatus
    kyc_reviewed_at: datetime | None = None
    rating_avg: float | None = Field(default=None, ge=0, le=5)
    is_online: bool = False
    seats_free: int = Field(default=0, ge=0, le=8)


class User(VoraModel):
    id: UUID
    display_name: str
    role: UserRole
    status: UserStatus
    locale: str = Field(examples=["fr", "en"])
    phone_e164: str = Field(
        description="The caller's own number. Never populated for a counterparty (I3).",
        examples=["+237600000001"],
    )
    accessibility: AccessibilityProfile
    outstanding_xaf: int = Field(
        default=0,
        ge=0,
        description=(
            "Unsettled cancellation debt. Booking is refused with "
            "OUTSTANDING_BALANCE while this is above zero."
        ),
    )
    driver: DriverProfile | None = None
    created_at: datetime


class UserUpdateRequest(VoraModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    locale: str | None = Field(default=None, pattern="^(fr|en)$")
    accessibility: AccessibilityProfile | None = None


class UserResponse(VoraModel):
    user: User


class BalanceResponse(VoraModel):
    """GET /me/balance. Added at Phase 0 because Phase 5.3 blocks booking on
    an unsettled debt and §6 gave the client no way to see or clear it."""

    outstanding_xaf: int = Field(ge=0)
    currency: str = "XAF"
    entries: list[BalanceEntry] = Field(default_factory=list)


class BalanceEntry(VoraModel):
    id: UUID
    ride_id: UUID | None = None
    kind: str = Field(examples=["cancel_fee", "adjustment"])
    amount_xaf: int
    settled_at: datetime | None = None
    note: str | None = None
    created_at: datetime


BalanceResponse.model_rebuild()
