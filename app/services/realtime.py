"""WebSocket connection registry and the LocationSink seam.

One process, one in-memory dictionary. That is the right answer at demo scale
and the wrong answer at ten thousand drivers, and the interface below is the
seam where the second answer drops in: `LocationSink` has one implementation
today that fans out in-process, and a Redis pub/sub implementation would
satisfy the same two methods without any caller changing.

Saying that out loud is worth more than building it. Redis pub/sub here would
add a dependency, a failure mode and an ordering question to a demo that has
twenty connections.

**I4 is enforced here, in the fan-out, not only in the serializer.** A
passenger receives driver location only for their own ride and only while that
ride is between `accepted` and `completed`. Enforcing it at the point of
transmission means a bug in a handler cannot broadcast a location to the wrong
socket: the registry simply has nowhere to send it.
"""

from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import WebSocket

from app.logging import get_logger

logger = get_logger("vora.realtime")

# The server pings on this interval and drops a connection that misses two.
# Twenty seconds is short enough to notice a dead socket before a passenger
# does, and long enough not to drain a phone battery on a metered connection.
HEARTBEAT_S = 20
MISSED_PINGS_BEFORE_DROP = 2

# Inbound location frames, per connection. One per two seconds is generous for
# real movement and cheap to enforce; a client exceeding it is malfunctioning
# or hostile, and either way its frames are not worth the write.
MIN_FRAME_INTERVAL_S = 2.0

# A location frame is a few hundred bytes. Anything approaching this is either
# a bug or an attempt to exhaust memory one frame at a time.
MAX_FRAME_BYTES = 4 * 1024


@dataclass
class Connection:
    """One live socket, and what it is allowed to receive."""

    websocket: WebSocket
    user_id: uuid.UUID
    role: str
    # The ride this socket is currently following. Set when the connection
    # authenticates and refreshed on ride updates; None means the socket gets
    # no location traffic at all.
    ride_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None
    connected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_frame_at: float = 0.0
    missed_pings: int = 0

    async def send(self, payload: dict) -> bool:
        """Send one frame. Returns False if the socket is gone.

        Never raises. A dead socket during fan-out is ordinary, and letting it
        propagate would abort delivery to everybody after it in the loop.
        """
        try:
            await self.websocket.send_json(payload)
            return True
        except Exception:
            return False


class LocationSink(ABC):
    """Where driver locations go.

    Two methods, deliberately. This is the interface a Redis pub/sub
    implementation would satisfy to make the service horizontally scalable, and
    naming it is the point: it is the one component we would swap first, and it
    is already isolated.
    """

    @abstractmethod
    async def publish_driver_location(
        self, *, ride_id: uuid.UUID, payload: dict
    ) -> int: ...

    @abstractmethod
    async def publish_ride_update(
        self, *, ride_id: uuid.UUID, payload: dict
    ) -> int: ...


class InProcessRegistry(LocationSink):
    """In-memory connection registry. Single process, no coordination."""

    def __init__(self) -> None:
        self._by_user: dict[uuid.UUID, Connection] = {}
        # Ride to the passenger socket following it. One entry per ride: a
        # ride has exactly one passenger, which is what makes I4 expressible
        # as a dictionary lookup rather than a filter over all connections.
        self._passenger_by_ride: dict[uuid.UUID, uuid.UUID] = {}
        self._lock = asyncio.Lock()

    async def register(self, connection: Connection) -> None:
        async with self._lock:
            # One socket per user. A reconnect replaces the old one rather than
            # accumulating; otherwise a phone on a flaky network leaves a
            # trail of dead sockets that still count as subscribers.
            existing = self._by_user.get(connection.user_id)
            if existing is not None:
                await self._unregister_locked(existing)

            self._by_user[connection.user_id] = connection
            if connection.role == "passenger" and connection.ride_id:
                self._passenger_by_ride[connection.ride_id] = connection.user_id

        logger.info(
            "ws_connected",
            user_id=str(connection.user_id),
            role=connection.role,
            ride_id=str(connection.ride_id) if connection.ride_id else None,
        )

    async def unregister(self, connection: Connection) -> None:
        async with self._lock:
            await self._unregister_locked(connection)

    async def _unregister_locked(self, connection: Connection) -> None:
        self._by_user.pop(connection.user_id, None)
        if connection.ride_id:
            holder = self._passenger_by_ride.get(connection.ride_id)
            if holder == connection.user_id:
                self._passenger_by_ride.pop(connection.ride_id, None)
        logger.info("ws_disconnected", user_id=str(connection.user_id))

    async def attach_ride(self, connection: Connection, ride_id: uuid.UUID) -> None:
        """Point a passenger socket at a ride, so it can receive its location."""
        async with self._lock:
            connection.ride_id = ride_id
            if connection.role == "passenger":
                self._passenger_by_ride[ride_id] = connection.user_id

    async def publish_driver_location(
        self, *, ride_id: uuid.UUID, payload: dict
    ) -> int:
        """Deliver a driver location to the one passenger entitled to it (I4).

        Returns the number of sockets written to, which is 0 or 1. That it
        cannot be more is the property worth having: there is no code path here
        that broadcasts, so a location cannot reach a second passenger even by
        mistake.
        """
        async with self._lock:
            user_id = self._passenger_by_ride.get(ride_id)
            connection = self._by_user.get(user_id) if user_id else None

        if connection is None:
            return 0

        delivered = await connection.send(payload)
        if not delivered:
            await self.unregister(connection)
            return 0
        return 1

    async def publish_ride_update(self, *, ride_id: uuid.UUID, payload: dict) -> int:
        """Ride status changes go to the passenger and, if connected, the driver.

        Status is not location: both parties are entitled to know the ride
        moved to `arrived`, and neither learns anything about the other's
        position from it.
        """
        async with self._lock:
            targets = [
                c
                for c in self._by_user.values()
                if c.ride_id == ride_id
            ]

        sent = 0
        for connection in targets:
            if await connection.send(payload):
                sent += 1
            else:
                await self.unregister(connection)
        return sent

    async def connection_for(self, user_id: uuid.UUID) -> Connection | None:
        async with self._lock:
            return self._by_user.get(user_id)

    async def stats(self) -> dict[str, int]:
        async with self._lock:
            return {
                "connections": len(self._by_user),
                "tracked_rides": len(self._passenger_by_ride),
            }


_registry: InProcessRegistry | None = None


def get_registry() -> InProcessRegistry:
    global _registry
    if _registry is None:
        _registry = InProcessRegistry()
    return _registry
