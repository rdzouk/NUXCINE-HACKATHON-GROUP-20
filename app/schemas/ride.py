"""The `ride` object.

§6 returns `{ ride }` from eight endpoints without ever defining it. This is
that definition, and it is the single schema all of them use.

It is one model with role-dependent population, not three models. The
serializer decides what a given caller may see; the shape does not change, so
the client parses one thing. Which role sees which field is documented on the
field itself, so it survives into openapi.json.

Visibility rules encoded here:
  I1  a caller who is neither the passenger, the assigned driver, nor an admin
      does not get a filtered ride. They get 404 RIDE_NOT_FOUND.
  I3  no phone number appears anywhere in this file, for any role, in any state.
  I4  `driver_location` is populated only for the assigned passenger and only
      between `accepted` and `completed`.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    NamedPlace,
    RideMode,
    RideNeed,
    VehicleCapability,
    VoraModel,
)


class RideStatus(StrEnum):
    REQUESTED = "requested"
    MATCHING = "matching"
    ACCEPTED = "accepted"
    ARRIVING = "arriving"
    ARRIVED = "arrived"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED_PASSENGER = "cancelled_passenger"
    CANCELLED_DRIVER = "cancelled_driver"
    EXPIRED = "expired"


TERMINAL_STATUSES = frozenset(
    {
        RideStatus.COMPLETED,
        RideStatus.CANCELLED_PASSENGER,
        RideStatus.CANCELLED_DRIVER,
        RideStatus.EXPIRED,
    }
)

# The window in which a passenger may see precise driver location (I4).
LOCATION_VISIBLE_STATUSES = frozenset(
    {
        RideStatus.ACCEPTED,
        RideStatus.ARRIVING,
        RideStatus.ARRIVED,
        RideStatus.IN_PROGRESS,
    }
)


class ActorType(StrEnum):
    PASSENGER = "passenger"
    DRIVER = "driver"
    SYSTEM = "system"
    ADMIN = "admin"


class MessageTemplate(StrEnum):
    """The complete set of things one party may say to the other.

    A closed enum rather than free text: it replaces phone contact (I3), it
    translates without a translation pipeline, it costs almost nothing on a
    bad network, and it cannot carry harassment or an off-app phone number.
    """

    AT_GATE = "at_gate"
    TWO_MIN = "two_min"
    CANT_FIND_YOU = "cant_find_you"
    PLEASE_WAIT_5 = "please_wait_5"
    ON_MY_WAY = "on_my_way"
    ARRIVED_WAITING = "arrived_waiting"


class CancelReason(StrEnum):
    CHANGED_MIND = "changed_mind"
    TOO_LONG_WAIT = "too_long_wait"
    WRONG_PICKUP = "wrong_pickup"
    DRIVER_NO_SHOW = "driver_no_show"
    PASSENGER_NO_SHOW = "passenger_no_show"
    SAFETY_CONCERN = "safety_concern"
    VEHICLE_UNSUITABLE = "vehicle_unsuitable"
    OTHER = "other"


class RideDriverSummary(VoraModel):
    """What a passenger may see about their driver. No phone (I3)."""

    id: UUID
    first_name: str = Field(description="First name only. Never the full legal name.")
    rating_avg: float | None = Field(default=None, ge=0, le=5)
    photo_url: str | None = None


class RideVehicleSummary(VoraModel):
    """Shown to the passenger so they can identify the car at the kerb."""

    make: str
    model: str
    color: str
    plate: str
    seats: int = Field(ge=1, le=8)
    photo_url: str | None = None
    capabilities: list[VehicleCapability] = Field(default_factory=list)


class RidePassengerSummary(VoraModel):
    """What a driver may see about their passenger. No phone, no full name (I3).

    `accessibility_required` is here because the driver genuinely needs it to
    do the job, and it is expressed as vehicle capabilities, so nothing about
    the person's condition is disclosed (I9).
    """

    first_name: str
    seats: int = Field(ge=1, le=8)
    accessibility_required: list[VehicleCapability] = Field(default_factory=list)
    prefers_text_contact: bool = False


class DriverLocation(VoraModel):
    lat: float
    lng: float
    heading: int | None = Field(default=None, ge=0, le=359)
    updated_at: datetime


class FareBreakdown(VoraModel):
    base_xaf: int
    per_km_xaf: int
    per_min_xaf: int
    surge_multiplier: float = Field(default=1.0, ge=1.0)
    minimum_fare_xaf: int
    corridor_rate: float | None = Field(
        default=None,
        description="Multiplier applied to the exclusive rate for corridor legs.",
    )


class CancellationInfo(VoraModel):
    cancelled_by: ActorType
    reason: CancelReason
    fee_xaf: int = Field(ge=0)
    fee_reason: str
    cancelled_at: datetime


class ShareInfo(VoraModel):
    active: bool
    expires_at: datetime | None = None


class Ride(VoraModel):
    id: UUID
    status: RideStatus
    mode: RideMode
    seats: int = Field(ge=1, le=8)

    pickup: NamedPlace
    dropoff: NamedPlace
    route_polyline: str | None = Field(
        default=None, description="Encoded polyline, precision 5."
    )

    currency: str = "XAF"
    quoted_fare_xaf: int
    final_fare_xaf: int | None = Field(
        default=None,
        description="Set at completion. Derived from the server-held trace (I2).",
    )
    quoted_distance_m: int
    actual_distance_m: int | None = None
    quoted_duration_s: int
    breakdown: FareBreakdown | None = None

    accessibility_required: list[VehicleCapability] = Field(
        default_factory=list,
        description="Per-trip vehicle requirements. Defaults from the passenger profile.",
    )

    ride_needs: list[RideNeed] = Field(
        default_factory=list,
        description=(
            "What the passenger asked the driver to do on this trip. Returned "
            "to both parties: the passenger to confirm what they asked for, "
            "the driver because they cannot do it otherwise. Nothing here "
            "says why it was asked for (I9)."
        ),
    )
    ride_needs_note: str | None = Field(
        default=None,
        max_length=140,
        description="Free text accompanying 'other'. Capped hard; it reaches another person.",
    )

    pin: str | None = Field(
        default=None,
        description=(
            "Four-digit pickup PIN. Populated for the passenger on every read so it "
            "survives an app restart. Always null for the driver and for admins."
        ),
        examples=["4821"],
    )

    announcement: str | None = Field(
        default=None,
        description=(
            "The current status as one spoken sentence, for a passenger who "
            "cannot read the screen. Written to be heard rather than read and "
            "returned by the server so the wording can be corrected without an "
            "app release, and so the French is written once rather than in "
            "every client.\n\n"
            "Null for the driver: it is the passenger's own ride being "
            "narrated, and the arrival line contains the PIN."
        ),
        examples=["Votre chauffeur est arrive. Toyota Corolla de couleur blanc."],
    )

    driver: RideDriverSummary | None = Field(
        default=None, description="Populated from `accepted` onward."
    )
    vehicle: RideVehicleSummary | None = Field(
        default=None, description="Populated from `accepted` onward."
    )
    passenger: RidePassengerSummary | None = Field(
        default=None, description="Populated for the assigned driver and for admins."
    )

    driver_location: DriverLocation | None = Field(
        default=None,
        description=(
            "Assigned passenger only, and only while status is accepted, arriving, "
            "arrived or in_progress (I4). Null in every other case."
        ),
    )
    eta_s: int | None = None

    cancellation: CancellationInfo | None = None
    share: ShareInfo | None = None

    created_at: datetime
    accepted_at: datetime | None = None
    arrived_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None


class RideResponse(VoraModel):
    ride: Ride


class RideListResponse(VoraModel):
    items: list[Ride]
    next_cursor: str | None = None


class RideCreateRequest(VoraModel):
    """POST /rides.

    `mode` and `seats` are carried inside the signed quote and are authoritative
    from there (I2). `seats` is accepted here only so the client can confirm what
    it thinks it booked; a value that disagrees with the quote is rejected with
    422 rather than silently repriced.
    """

    quote_id: str = Field(min_length=16, max_length=4096)
    seats: int = Field(ge=1, le=8)
    accessibility_required: list[VehicleCapability] = Field(
        default_factory=list,
        max_length=5,
        description=(
            "Overrides the passenger's standing profile for this trip only. "
            "Vehicle capabilities, never a personal attribute (I9)."
        ),
    )
    ride_needs: list[RideNeed] = Field(
        default_factory=list,
        max_length=7,
        description=(
            "What the driver is asked to do on this trip. A closed vocabulary "
            "served by GET /ride-needs, so a phrasing correction is a server "
            "change rather than an app release."
        ),
    )
    ride_needs_note: str | None = Field(
        default=None,
        max_length=140,
        description=(
            "Accompanies 'other'. Capped at 140 characters because it reaches "
            "another person: long enough to be useful, too short to hold an "
            "address."
        ),
    )


class RideCancelRequest(VoraModel):
    reason: CancelReason


class RideCancelResponse(VoraModel):
    ride: Ride
    fee_xaf: int = Field(ge=0)
    fee_reason: str


class RideStartRequest(VoraModel):
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


class RideCompleteResponse(VoraModel):
    ride: Ride
    final_fare_xaf: int


class RideMessageRequest(VoraModel):
    template_key: MessageTemplate


class RideMessage(VoraModel):
    id: UUID
    ride_id: UUID
    sender_type: ActorType
    template_key: MessageTemplate
    text: str = Field(description="Server-rendered in the recipient's locale.")
    created_at: datetime


class RideMessageResponse(VoraModel):
    message: RideMessage


class ShareLinkResponse(VoraModel):
    url: str
    expires_at: datetime


class IncidentCategory(StrEnum):
    SAFETY = "safety"
    HARASSMENT = "harassment"
    FARE_DISPUTE = "fare_dispute"
    NO_SHOW = "no_show"
    VEHICLE_CONDITION = "vehicle_condition"
    OTHER = "other"


class IncidentReportRequest(VoraModel):
    category: IncidentCategory
    description: str = Field(min_length=1, max_length=2000)


class IncidentResponse(VoraModel):
    incident_id: UUID
