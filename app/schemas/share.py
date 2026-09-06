"""Public trip-share contract.

This is the only unauthenticated view of a ride in the system, so it is defined
as its own model rather than as a filtered `Ride`. That is deliberate: if the
share view reused `Ride` with fields blanked out, any field added to `Ride`
later would default to being exposed to anyone holding a link. Here, a new
field is exposed only if someone writes it into this file.

Absent by construction: passenger identity, fare, PIN, phone, trace history,
and the driver's full name.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.schemas.common import Latitude, Longitude, VoraModel
from app.schemas.ride import RideStatus


class SharePrecision(StrEnum):
    """Location precision served to a share viewer."""

    COARSE = "coarse"
    PRECISE = "precise"


class ShareVehicle(VoraModel):
    make: str
    model: str
    color: str
    plate: str


class ShareLocation(VoraModel):
    lat: Latitude
    lng: Longitude
    precision: SharePrecision = Field(
        description=(
            "Coarse until the ride is in_progress, so a link shared before pickup "
            "does not reveal exactly where the passenger is waiting."
        )
    )
    updated_at: datetime


class ShareView(VoraModel):
    ride_status: RideStatus
    driver_first_name: str
    vehicle: ShareVehicle
    current_location: ShareLocation | None = None
    eta_s: int | None = None
    dropoff_label: str
    expires_at: datetime
