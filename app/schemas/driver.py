"""Driver-side contract, including the offer shape.

§6 addresses `POST /driver/offers/{id}/accept` but §5 has no offers table, so
`{id}` had no referent. Resolved by making an offer a first-class object with
its own id, backed by a `ride_offers` table added in Phase 3.

Using the ride id as the offer id would have been simpler and wrong: decline
would be a no-op, and wave 2 would re-offer the same ride to a driver who
already refused it in wave 1.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    Latitude,
    Longitude,
    NamedPlace,
    RideMode,
    RideNeed,
    VehicleCapability,
    VoraModel,
)
from app.schemas.ride import Ride
from app.schemas.user import KycStatus


class OfferState(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class RideOffer(VoraModel):
    """What a driver is shown before accepting.

    Deliberately not a `Ride`. Before acceptance the driver has no relationship
    to this passenger, so they get the operational facts needed to decide and
    nothing that identifies anyone (I3).
    """

    id: UUID
    ride_id: UUID
    mode: RideMode
    seats: int = Field(ge=1, le=8)
    pickup: NamedPlace
    dropoff: NamedPlace
    distance_to_pickup_m: int
    trip_distance_m: int
    trip_duration_s: int
    fare_xaf: int = Field(description="What the driver would earn on this trip.")
    currency: str = "XAF"
    accessibility_required: list[VehicleCapability] = Field(default_factory=list)
    ride_needs: list[RideNeed] = Field(
        default_factory=list,
        description=(
            "What the driver is being asked to do, shown before they accept. "
            "Actions only: nothing here says anything about the passenger, "
            "because nothing about them was recorded (I9)."
        ),
    )
    ride_needs_note: str | None = Field(default=None, max_length=140)
    wave: int = Field(ge=1, le=3, description="Matching wave that produced this offer.")
    expires_at: datetime
    created_at: datetime


class DriverOffersResponse(VoraModel):
    offers: list[RideOffer]


class DriverOnlineRequest(VoraModel):
    lat: Latitude
    lng: Longitude
    seats_free: int = Field(ge=0, le=8)
    heading: int | None = Field(default=None, ge=0, le=359)


class DriverPresence(VoraModel):
    is_online: bool
    seats_free: int = Field(ge=0, le=8)
    kyc_status: KycStatus
    updated_at: datetime


class DriverPresenceResponse(VoraModel):
    presence: DriverPresence


class OfferAcceptResponse(VoraModel):
    ride: Ride


class VehicleCapabilityInfo(VoraModel):
    """GET /vehicles/capabilities. Drives the client's filter UI.

    `label_fr` and `label_en` are served rather than hardcoded in the app so the
    wording can be corrected without shipping a release.
    """

    key: VehicleCapability
    label_fr: str
    label_en: str
    description_fr: str
    description_en: str


class VehicleCapabilitiesResponse(VoraModel):
    capabilities: list[VehicleCapabilityInfo]


class KycDocumentKind(StrEnum):
    CNI = "cni"
    DRIVING_LICENCE = "driving_licence"
    VEHICLE_REGISTRATION = "vehicle_registration"
    VEHICLE_PHOTO = "vehicle_photo"
    DRIVER_PHOTO = "driver_photo"


class KycStatusResponse(VoraModel):
    kyc_status: KycStatus
    submitted: list[KycDocumentKind]
    missing: list[KycDocumentKind]
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None


class KycDocumentRequest(VoraModel):
    """Submit one KYC document reference.

    A reference, not a file. Object storage is a Phase 7 concern; what matters
    for the KYC state machine is that the identifier exists, is encrypted at
    rest, and is bound to this driver.
    """

    kind: KycDocumentKind
    reference: str = Field(
        min_length=4,
        max_length=128,
        description=(
            "The document identifier, for example a CNI number. Encrypted with "
            "AES-GCM before storage and never returned by any endpoint. For a "
            "CNI, only a keyed hash is retained for deduplication and banning."
        ),
    )


class KycDocumentResponse(VoraModel):
    kind: KycDocumentKind
    submitted_at: datetime
    kyc_status: KycStatus
    missing: list[KycDocumentKind]


class KycDecisionRequest(VoraModel):
    """Admin decision on a driver's KYC."""

    status: KycStatus
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Required when rejecting, so the driver can correct and resubmit.",
    )


class DriverAdminView(VoraModel):
    """What an admin sees about a driver under review.

    No phone number and no decrypted document reference. An admin approving
    KYC needs to know which documents exist and what state the account is in;
    they do not need the identity numbers themselves, and not returning them
    means an admin session compromise does not leak them either.
    """

    driver_id: UUID
    user_id: UUID
    display_name: str
    kyc_status: KycStatus
    submitted: list[KycDocumentKind]
    missing: list[KycDocumentKind]
    is_online: bool
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None


class RideNeedInfo(VoraModel):
    """One thing a passenger can ask for, and what the driver does about it.

    A need, never a diagnosis. Every entry describes an action the driver
    takes; none records anything about the person asking. Somebody tall,
    somebody who gets carsick and somebody with a mobility impairment select
    the same option and the system cannot tell them apart, which is what
    keeps this the right side of Law 2024/017 (I9).
    """

    key: str
    label_fr: str
    label_en: str
    driver_action_fr: str
    driver_action_en: str
    requires_undertaking: bool = Field(
        description=(
            "Whether a driver must have signed the undertakings before being "
            "offered a ride carrying this need. True for anything the driver "
            "does rather than anything the car has."
        )
    )
    vehicle_capability: str | None = Field(
        default=None,
        description=(
            "The vehicle capability this implies, if any. Most needs imply "
            "none: keeping the windows closed is behaviour, not a property of "
            "the car, so it must not shrink the pool of vehicles."
        ),
    )


class RideNeedsResponse(VoraModel):
    needs: list[RideNeedInfo]
    undertakings_fr: list[str]
    undertakings_en: list[str]
    undertakings_version: str
