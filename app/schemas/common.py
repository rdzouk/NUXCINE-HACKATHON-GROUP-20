"""Shared contract primitives."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

# Cameroon sits inside these bounds with room to spare. Tighter service-area
# enforcement is a runtime polygon check (Phase 2); this is only a sanity gate
# so that obviously-junk coordinates fail at the schema boundary (I6).
Latitude = Annotated[float, Field(ge=-90, le=90, examples=[3.848])]
Longitude = Annotated[float, Field(ge=-180, le=180, examples=[11.502])]

CURRENCY = "XAF"


class VoraModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class GeoPoint(VoraModel):
    lat: Latitude
    lng: Longitude


class NamedPlace(VoraModel):
    """A coordinate plus what the user actually called it.

    The label is carried end to end and stored on the ride. "Carrefour Warda"
    is the thing the passenger and driver will say to each other; a reverse
    geocode of the same point is not a substitute for it.
    """

    lat: Latitude
    lng: Longitude
    label: str = Field(min_length=1, max_length=160, examples=["Carrefour Warda"])


class RideMode(StrEnum):
    EXCLUSIVE = "exclusive"
    CORRIDOR = "corridor"


class UserRole(StrEnum):
    PASSENGER = "passenger"
    DRIVER = "driver"
    ADMIN = "admin"


class UserStatus(StrEnum):
    ACTIVE = "active"
    RESTRICTED = "restricted"
    SUSPENDED = "suspended"


class VehicleCapability(StrEnum):
    """Requirements a vehicle must satisfy. Never a fact about a person (I9).

    Law 2024/017 prohibits processing health data. A wheelchair user is not
    recorded as a wheelchair user; a trip is recorded as requiring a ramp.
    The matcher only ever compares this enum against vehicle columns.
    """

    RAMP = "ramp"
    BOOT_SPACE = "boot_space"
    FRONT_SEAT = "front_seat"
    DRIVER_ASSIST = "driver_assist"
    GUIDE_ANIMAL = "guide_animal"


class HealthComponent(VoraModel):
    status: str = Field(examples=["ok", "degraded", "down"])
    latency_ms: float | None = None
    detail: str | None = None


class HealthResponse(VoraModel):
    status: str = Field(examples=["ok", "degraded"])
    version: str
    app_env: str
    time: datetime
    components: dict[str, HealthComponent]


class ErrorDetailModel(VoraModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ErrorResponse(VoraModel):
    """The §6 envelope. Every non-2xx response in this API has this shape."""

    error: ErrorDetailModel
