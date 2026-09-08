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
from app.schemas.common import NamedPlace, RideMode, RideNeed, VehicleCapability
from app.schemas.ride import (
    LOCATION_VISIBLE_STATUSES,
    RideDriverSummary,
    RidePassengerSummary,
    RideStatus,
    RideVehicleSummary,
)
from app.schemas.ride import Ride as RideSchema
from app.schemas.user import (
    AccessibilityProfile,
    DriverProfile,
    KycStatus,
)
from app.schemas.user import (
    User as UserSchema,
)
from app.services import accessibility


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


def _first_name(display_name: str | None, fallback: str) -> str:
    """First name only.

    The full legal name is not needed to identify somebody at the kerb, and
    handing it to a counterparty is a doxxing vector (I3).
    """
    if display_name and display_name.strip():
        return display_name.strip().split()[0]
    return fallback


def _ride_needs(values: list[str] | None) -> list[RideNeed]:
    """Drop anything the enum no longer knows about.

    A need retired from the vocabulary still sits on historical rides. Raising
    on it would make an old trip unreadable, which is a worse outcome than
    quietly showing one fewer line on a completed journey.
    """
    known = {n.value for n in RideNeed}
    return [RideNeed(v) for v in (values or []) if v in known]


def _capabilities(values) -> list[VehicleCapability]:
    known = {v.value for v in VehicleCapability}
    return [VehicleCapability(c) for c in (values or []) if c in known]


def serialize_ride(
    ride,
    *,
    actor: str,
    driver_user=None,
    vehicle=None,
    passenger_user=None,
    driver_location=None,
    eta_s: int | None = None,
    pickup: tuple[float, float] | None = None,
    dropoff: tuple[float, float] | None = None,
) -> RideSchema:
    """Build the wire `ride` for one caller.

    This function is where I3 and I4 actually live. Not in the model and not in
    the handlers: in one place, so "who may see this field" is a single
    readable decision rather than a property of whichever endpoint you happen
    to be reading.

      I3  no phone number is constructed here for anybody, in any state. There
          is no branch that could produce one, which is a stronger guarantee
          than a branch that currently does not.
      I4  `driver_location` is populated only for the assigned passenger and
          only while the ride sits between accepted and completed.

    `actor` comes from `require_ride_participant`, which has already proved the
    caller is entitled to see this ride at all.
    """
    is_passenger = actor == "passenger"
    status = RideStatus(ride.status)

    driver_summary = None
    if driver_user is not None and ride.driver_id is not None:
        driver_summary = RideDriverSummary(
            id=ride.driver_id,
            first_name=_first_name(driver_user.display_name, "Chauffeur"),
            rating_avg=None,
            photo_url=None,
        )

    vehicle_summary = None
    if vehicle is not None:
        caps: list[VehicleCapability] = []
        if vehicle.has_ramp:
            caps.append(VehicleCapability.RAMP)
        if vehicle.has_boot_space:
            caps.append(VehicleCapability.BOOT_SPACE)
        if vehicle.front_seat_available:
            caps.append(VehicleCapability.FRONT_SEAT)
        if vehicle.driver_assists:
            caps.append(VehicleCapability.DRIVER_ASSIST)
        if vehicle.accepts_guide_animal:
            caps.append(VehicleCapability.GUIDE_ANIMAL)
        vehicle_summary = RideVehicleSummary(
            make=vehicle.make,
            model=vehicle.model,
            color=vehicle.color,
            plate=vehicle.plate,
            seats=vehicle.seats,
            photo_url=vehicle.photo_url,
            capabilities=caps,
        )

    passenger_summary = None
    if passenger_user is not None and not is_passenger:
        # Shown to the assigned driver and to admins: a first name, and the
        # vehicle requirements they need to do the job. Nothing else.
        passenger_summary = RidePassengerSummary(
            first_name=_first_name(passenger_user.display_name, "Client"),
            seats=ride.seats,
            accessibility_required=_capabilities(ride.accessibility_required),
            prefers_text_contact=passenger_user.prefers_text_contact,
        )

    # I4. Both conditions, every time: the right person, and the right window.
    location = None
    if (
        is_passenger
        and driver_location is not None
        and status in LOCATION_VISIBLE_STATUSES
    ):
        location = driver_location

    return RideSchema(
        id=ride.id,
        status=status,
        mode=RideMode(ride.mode),
        seats=ride.seats,
        pickup=NamedPlace(
            lat=pickup[0] if pickup else 0.0,
            lng=pickup[1] if pickup else 0.0,
            label=ride.pickup_label,
        ),
        dropoff=NamedPlace(
            lat=dropoff[0] if dropoff else 0.0,
            lng=dropoff[1] if dropoff else 0.0,
            label=ride.dropoff_label,
        ),
        route_polyline=ride.route_polyline,
        quoted_fare_xaf=ride.quoted_fare_xaf,
        final_fare_xaf=ride.final_fare_xaf,
        quoted_distance_m=ride.quoted_distance_m,
        quoted_duration_s=ride.quoted_duration_s,
        actual_distance_m=ride.actual_distance_m,
        accessibility_required=_capabilities(ride.accessibility_required),
        # Sent to both parties, unlike the PIN. The passenger needs to see what
        # they asked for; the driver cannot carry it out without being told.
        # Neither side learns why it was asked for, because that was never
        # recorded (I9).
        ride_needs=_ride_needs(ride.ride_needs),
        ride_needs_note=ride.ride_needs_note,
        # The passenger reads this aloud at pickup. The driver must never see
        # it, or the PIN stops proving anything.
        pin=ride.pin if is_passenger else None,
        # The same line, spoken. Gated by actor exactly as the PIN is, because
        # the arrival announcement contains it: a driver who could hear this
        # would not need the passenger to read it out, and the whole
        # anti-impersonation check would stop proving anything.
        #
        # This is what makes the PIN usable by a passenger who cannot see it.
        # Without it the safety feature is sighted-only.
        announcement=(
            accessibility.announcement(
                status,
                locale=(getattr(passenger_user, "locale", None) or "fr"),
                vehicle=(
                    f"{vehicle_summary.make} {vehicle_summary.model}"
                    if vehicle_summary
                    else None
                ),
                color=vehicle_summary.color if vehicle_summary else None,
                plate=vehicle_summary.plate if vehicle_summary else None,
                pin=ride.pin,
                fare_xaf=ride.final_fare_xaf or ride.quoted_fare_xaf,
            )
            if is_passenger
            else None
        ),
        driver=driver_summary,
        vehicle=vehicle_summary,
        passenger=passenger_summary,
        driver_location=location,
        eta_s=eta_s,
        cancellation=None,
        share=None,
        created_at=ride.created_at,
        accepted_at=ride.accepted_at,
        arrived_at=ride.arrived_at,
        started_at=ride.started_at,
        ended_at=ride.ended_at,
    )
