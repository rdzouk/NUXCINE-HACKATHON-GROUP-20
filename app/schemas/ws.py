"""WebSocket frame contract.

These models are not wired to a route in Phase 0. They are declared now because
the mobile client needs the frame vocabulary to build against, and because
Phase 4 must not be free to invent a different one.

Transport rules that are part of the contract, not implementation detail:
  - Authentication is by `Authorization` header on connect, or by a first frame
    of type `auth`. Never by query string, because query strings land in access
    logs, proxy logs and browser history.
  - The server sends `ping` every 20 s and drops a connection that misses two.
  - Inbound location frames are capped at one per 2 s per connection.
  - A driver frame arriving with no active ride is rejected, not stored.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import Latitude, Longitude, VoraModel
from app.schemas.ride import DriverLocation, MessageTemplate, RideStatus


class ClientFrameType(StrEnum):
    AUTH = "auth"
    LOCATION = "location"
    PONG = "pong"


class ServerFrameType(StrEnum):
    READY = "ready"
    OFFER = "offer"
    RIDE_UPDATE = "ride_update"
    DRIVER_LOCATION = "driver_location"
    MESSAGE = "message"
    SHARE_UPDATE = "share_update"
    PING = "ping"
    ERROR = "error"


class AuthFrame(VoraModel):
    type: Literal[ClientFrameType.AUTH] = ClientFrameType.AUTH
    token: str = Field(min_length=16, max_length=4096)


class LocationFrame(VoraModel):
    """Driver to server. The only inbound frame that carries data.

    Every field here is attacker-controlled. Phase 4's plausibility filter is
    what makes this safe to price a fare from (I2): implied speed, accuracy,
    timestamp monotonicity and teleport distance are all checked, and a point
    that fails is stored with rejected=true rather than discarded.
    """

    type: Literal[ClientFrameType.LOCATION] = ClientFrameType.LOCATION
    lat: Latitude
    lng: Longitude
    heading: int | None = Field(default=None, ge=0, le=359)
    speed_mps: float | None = Field(default=None, ge=0, le=100)
    accuracy_m: float | None = Field(default=None, ge=0, le=10000)
    ts: datetime


class PongFrame(VoraModel):
    type: Literal[ClientFrameType.PONG] = ClientFrameType.PONG


class ReadyFrame(VoraModel):
    type: Literal[ServerFrameType.READY] = ServerFrameType.READY
    user_id: UUID
    heartbeat_s: int = 20


class RideUpdateFrame(VoraModel):
    type: Literal[ServerFrameType.RIDE_UPDATE] = ServerFrameType.RIDE_UPDATE
    ride_id: UUID
    status: RideStatus
    eta_s: int | None = None
    occurred_at: datetime


class DriverLocationFrame(VoraModel):
    """Server to the one subscribed passenger of the active ride only (I4)."""

    type: Literal[ServerFrameType.DRIVER_LOCATION] = ServerFrameType.DRIVER_LOCATION
    ride_id: UUID
    location: DriverLocation
    eta_s: int | None = None


class MessageFrame(VoraModel):
    type: Literal[ServerFrameType.MESSAGE] = ServerFrameType.MESSAGE
    ride_id: UUID
    template_key: MessageTemplate
    text: str
    created_at: datetime


class PingFrame(VoraModel):
    type: Literal[ServerFrameType.PING] = ServerFrameType.PING
    ts: datetime


class ErrorFrame(VoraModel):
    """Socket-level failures reuse the REST error codes so the client keeps one map."""

    type: Literal[ServerFrameType.ERROR] = ServerFrameType.ERROR
    code: str
    message: str
