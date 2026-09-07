"""WebSocket routes.

**Authentication never uses a query string.** Query strings are recorded in
access logs, proxy logs and browser history, so a token in one is a credential
written to disk in three places. Two paths are accepted instead:

  Authorization header    native clients, which can set headers
  first frame `auth`      browsers, which cannot

The browser path is not a workaround, it is the contract. `features/map/hooks/
useDriverLocation.js` asked which one to use; the answer is the first frame,
and `docs/INTEGRATION.md` carries the snippet.

The socket is accepted before authentication so the client can be told *why* it
was refused. Rejecting the handshake gives a browser nothing to distinguish an
expired token from a network failure, and a client that cannot tell those apart
either retries forever or gives up on a recoverable error.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.db import get_sessionmaker
from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.i18n import message_for
from app.logging import get_logger
from app.models.ride import Ride
from app.models.user import Driver, User
from app.schemas.ride import RideStatus
from app.security.tokens import decode_access_token
from app.services import sharing, tracking
from app.services.realtime import (
    HEARTBEAT_S,
    MAX_FRAME_BYTES,
    MIN_FRAME_INTERVAL_S,
    MISSED_PINGS_BEFORE_DROP,
    Connection,
    get_registry,
)
from app.services.state_machine import LIVE

router = APIRouter(prefix="/ws", tags=["websocket"])
logger = get_logger("vora.ws")

# Close codes. 1008 is a policy violation, which is what an auth failure is.
CLOSE_POLICY = 1008
CLOSE_TOO_BIG = 1009
CLOSE_INTERNAL = 1011

# How long a client has to send its auth frame before the socket is dropped.
AUTH_TIMEOUT_S = 10


async def _send_error(websocket: WebSocket, code: ErrorCode, detail: str = "") -> None:
    """Socket errors reuse the REST error codes, so the client keeps one map."""
    with contextlib.suppress(Exception):
        await websocket.send_json(
            {
                "type": "error",
                "code": code.value,
                "message": message_for(code),
                **({"detail": detail} if detail else {}),
            }
        )


async def _authenticate(websocket: WebSocket) -> dict | None:
    """Resolve the caller from a header or a first `auth` frame.

    Returns the decoded token payload, or None after closing the socket.
    """
    header = websocket.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        try:
            return decode_access_token(token.strip())
        except VoraError as exc:
            await _send_error(websocket, exc.code)
            await websocket.close(code=CLOSE_POLICY, reason="invalid token")
            return None

    # Browser path. A bounded wait, because an unauthenticated socket holding a
    # slot indefinitely is a trivial resource exhaustion.
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=AUTH_TIMEOUT_S)
    except (TimeoutError, WebSocketDisconnect):
        await websocket.close(code=CLOSE_POLICY, reason="auth timeout")
        return None

    if len(raw) > MAX_FRAME_BYTES:
        await websocket.close(code=CLOSE_TOO_BIG, reason="frame too large")
        return None

    try:
        import json

        frame = json.loads(raw)
    except ValueError:
        await _send_error(websocket, ErrorCode.MALFORMED_REQUEST)
        await websocket.close(code=CLOSE_POLICY, reason="malformed auth frame")
        return None

    if frame.get("type") != "auth" or not frame.get("token"):
        await _send_error(
            websocket, ErrorCode.UNAUTHENTICATED, "first frame must be {type:'auth'}"
        )
        await websocket.close(code=CLOSE_POLICY, reason="auth frame required")
        return None

    try:
        return decode_access_token(str(frame["token"]))
    except VoraError as exc:
        await _send_error(websocket, exc.code)
        await websocket.close(code=CLOSE_POLICY, reason="invalid token")
        return None


async def _load_user(user_id: uuid.UUID) -> User | None:
    """Load the user from the database, not from the token body.

    Same reasoning as the HTTP dependency: a token is a snapshot, and a user
    suspended thirty seconds ago still holds one that says otherwise.
    """
    async with get_sessionmaker()() as session:
        user = await session.get(User, user_id)
        if user is None or user.status == "suspended":
            return None
        return user


async def _active_ride_for_passenger(user_id: uuid.UUID) -> Ride | None:
    async with get_sessionmaker()() as session:
        result = await session.execute(
            select(Ride).where(
                Ride.passenger_id == user_id,
                Ride.status.in_([s.value for s in LIVE]),
            )
        )
        return result.scalar_one_or_none()


async def _active_ride_for_driver(user_id: uuid.UUID) -> tuple[Ride | None, Driver | None]:
    async with get_sessionmaker()() as session:
        driver = (
            await session.execute(select(Driver).where(Driver.user_id == user_id))
        ).scalar_one_or_none()
        if driver is None:
            return None, None
        result = await session.execute(
            select(Ride).where(
                Ride.driver_id == driver.id,
                Ride.status.in_([s.value for s in LIVE]),
            )
        )
        return result.scalar_one_or_none(), driver


async def _heartbeat(connection: Connection) -> None:
    """Ping on an interval; drop a socket that stops answering.

    Without this a half-open connection, which is what a phone leaving coverage
    produces, looks identical to an idle one. The passenger's map then freezes
    on a stale position with no indication anything is wrong.
    """
    while True:
        await asyncio.sleep(HEARTBEAT_S)
        connection.missed_pings += 1
        if connection.missed_pings > MISSED_PINGS_BEFORE_DROP:
            logger.info("ws_heartbeat_timeout", user_id=str(connection.user_id))
            with contextlib.suppress(Exception):
                await connection.websocket.close(
                    code=CLOSE_POLICY, reason="heartbeat timeout"
                )
            return
        if not await connection.send(
            {"type": "ping", "ts": datetime.now(UTC).isoformat()}
        ):
            return


@router.websocket("/passenger")
async def passenger_socket(websocket: WebSocket) -> None:
    """Passenger socket. Outbound only.

    Receives ride_update, driver_location, message and ping. It sends nothing
    but pong: a passenger has no location to contribute, and accepting data
    here would be an ingest path with no purpose and a real attack surface.
    """
    await websocket.accept()

    payload = await _authenticate(websocket)
    if payload is None:
        return

    user_id = uuid.UUID(payload["sub"])
    user = await _load_user(user_id)
    if user is None:
        await _send_error(websocket, ErrorCode.ACCOUNT_SUSPENDED)
        await websocket.close(code=CLOSE_POLICY)
        return

    ride = await _active_ride_for_passenger(user_id)

    connection = Connection(
        websocket=websocket,
        user_id=user_id,
        role="passenger",
        ride_id=ride.id if ride else None,
    )
    registry = get_registry()
    await registry.register(connection)

    await connection.send(
        {
            "type": "ready",
            "user_id": str(user_id),
            "heartbeat_s": HEARTBEAT_S,
            # Reconnect resumes from known state rather than from nothing, so a
            # dropped connection does not blank the passenger's screen.
            "ride_id": str(ride.id) if ride else None,
            "ride_status": ride.status if ride else None,
        }
    )

    heartbeat = asyncio.create_task(_heartbeat(connection))
    try:
        while True:
            raw = await websocket.receive_text()
            if len(raw) > MAX_FRAME_BYTES:
                await websocket.close(code=CLOSE_TOO_BIG, reason="frame too large")
                return
            # Anything from a passenger is treated as liveness and nothing more.
            connection.missed_pings = 0
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("passenger_socket_error", user_id=str(user_id))
    finally:
        heartbeat.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat
        await registry.unregister(connection)


@router.websocket("/driver")
async def driver_socket(websocket: WebSocket) -> None:
    """Driver socket. Inbound location, outbound offers and ride updates.

    Every inbound frame is attacker-controlled. A location is rejected outright
    unless the driver has an active ride, rate limited to one per two seconds,
    size capped, and run through the plausibility filter before it can affect a
    fare.
    """
    await websocket.accept()

    payload = await _authenticate(websocket)
    if payload is None:
        return

    user_id = uuid.UUID(payload["sub"])
    user = await _load_user(user_id)
    if user is None or user.role != "driver":
        await _send_error(websocket, ErrorCode.FORBIDDEN_ROLE)
        await websocket.close(code=CLOSE_POLICY, reason="driver role required")
        return

    ride, driver = await _active_ride_for_driver(user_id)
    if driver is None:
        await _send_error(websocket, ErrorCode.FORBIDDEN_ROLE)
        await websocket.close(code=CLOSE_POLICY, reason="no driver record")
        return

    connection = Connection(
        websocket=websocket,
        user_id=user_id,
        role="driver",
        ride_id=ride.id if ride else None,
        driver_id=driver.id,
    )
    registry = get_registry()
    await registry.register(connection)

    await connection.send(
        {
            "type": "ready",
            "user_id": str(user_id),
            "heartbeat_s": HEARTBEAT_S,
            "ride_id": str(ride.id) if ride else None,
            "min_frame_interval_s": MIN_FRAME_INTERVAL_S,
        }
    )

    heartbeat = asyncio.create_task(_heartbeat(connection))
    try:
        while True:
            raw = await websocket.receive_text()

            if len(raw) > MAX_FRAME_BYTES:
                await websocket.close(code=CLOSE_TOO_BIG, reason="frame too large")
                return

            connection.missed_pings = 0

            import json

            try:
                frame = json.loads(raw)
            except ValueError:
                await _send_error(websocket, ErrorCode.MALFORMED_REQUEST)
                continue

            if frame.get("type") == "pong":
                continue

            if frame.get("type") != "location":
                await _send_error(websocket, ErrorCode.MALFORMED_REQUEST)
                continue

            # Rate limit before any parsing or database work, so a flood costs
            # one comparison rather than a transaction.
            now = time.monotonic()
            if now - connection.last_frame_at < MIN_FRAME_INTERVAL_S:
                continue
            connection.last_frame_at = now

            await _ingest_location(connection, frame)

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("driver_socket_error", user_id=str(user_id))
    finally:
        heartbeat.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat
        await registry.unregister(connection)


async def _ingest_location(connection: Connection, frame: dict) -> None:
    """Validate, persist and fan out one driver location."""
    try:
        lat = float(frame["lat"])
        lng = float(frame["lng"])
    except (KeyError, TypeError, ValueError):
        await _send_error(connection.websocket, ErrorCode.VALIDATION_FAILED)
        return

    heading = frame.get("heading")
    recorded_at = datetime.now(UTC)
    if frame.get("ts"):
        with contextlib.suppress(ValueError, TypeError):
            recorded_at = datetime.fromisoformat(str(frame["ts"]).replace("Z", "+00:00"))

    async with get_sessionmaker()() as session:
        # Re-read the ride every frame rather than trusting the one captured at
        # connect. A ride completed thirty seconds ago must stop accepting
        # points immediately, or a driver can keep adding distance to a fare
        # that has already been charged.
        ride = None
        if connection.driver_id is not None:
            result = await session.execute(
                select(Ride).where(
                    Ride.driver_id == connection.driver_id,
                    Ride.status.in_([s.value for s in tracking.TRACKABLE]),
                )
            )
            ride = result.scalar_one_or_none()

        if ride is None:
            # No active ride: nothing to attribute this to, and storing it
            # would be location history unattached to any journey.
            await _send_error(
                connection.websocket,
                ErrorCode.RIDE_STATE_CONFLICT,
                "no active ride for this driver",
            )
            return

        accepted, reason = await tracking.record_location(
            session,
            ride=ride,
            lat=lat,
            lng=lng,
            recorded_at=recorded_at,
            accuracy_m=frame.get("accuracy_m"),
            speed_mps=frame.get("speed_mps"),
        )
        await session.commit()

    if not accepted:
        # Told, not silently dropped. A driver whose phone is reporting badly
        # deserves to know; an attacker learns only that we noticed.
        await connection.websocket.send_json(
            {"type": "location_rejected", "reason": reason}
        )
        return

    # Fan out only accepted points. The passenger's map should never show a
    # position the system itself does not believe.
    await get_registry().publish_driver_location(
        ride_id=ride.id,
        payload={
            "type": "driver_location",
            "ride_id": str(ride.id),
            "location": {
                "lat": lat,
                "lng": lng,
                "heading": heading,
                "updated_at": recorded_at.isoformat(),
            },
            "eta_s": None,
        },
    )


# How often the share socket re-reads the ride. Slower than the driver's own
# reporting rate on purpose: a relative watching from home needs to see the car
# move, not every fix, and the payload is re-derived from the database each time.
SHARE_POLL_S = 3.0

# A share link outlives the trip by design, so the socket needs its own ceiling.
# Without one, a tab left open on a completed ride holds a connection all night.
SHARE_MAX_DURATION_S = 30 * 60


@router.websocket("/share/{token}")
async def share_socket(websocket: WebSocket, token: str) -> None:
    """Follow a shared trip live, without an account.

    **The token is in the path, and that is the design rather than an
    exception to the no-credentials-in-URLs rule at the top of this module.**
    The share link *is* the URL: it gets forwarded in WhatsApp, and there is
    nowhere else for it to live. What makes that acceptable is everything
    around it, all built in Phase 5: the token is signed, expires in four
    hours, can be revoked before the signature lapses, and reveals a
    deliberately thin view that never contains passenger identity, fare, PIN or
    phone number. An invalid, expired and revoked token are answered alike, so
    the socket does not confirm which links were ever real.

    **This pushes a server-side poll rather than subscribing to the tracking
    registry.** Precision has to be recomputed per frame, because a link shared
    before pickup must stay coarse until the trip is moving, and revocation has
    to take effect within seconds rather than at the end of the trip. Reading
    the ride each tick gets both for free. It is still meaningfully better for
    the viewer than the HTTP polling the share page falls back to: no repeated
    TLS handshake, no token re-validation per request, and a revoked link
    closes the socket instead of returning 404 on the next poll.

    The socket stops when the ride leaves the viewable set, when the token is
    revoked or expires, or at the duration ceiling above.
    """
    await websocket.accept()

    sessionmaker = get_sessionmaker()
    started = time.monotonic()
    last_signature: tuple | None = None

    try:
        while True:
            if time.monotonic() - started > SHARE_MAX_DURATION_S:
                await websocket.send_json(
                    {"type": "ended", "reason": "session_expired"}
                )
                await websocket.close(code=1000, reason="session expired")
                return

            async with sessionmaker() as session:
                try:
                    # Re-resolved every tick, which is what makes revocation
                    # take effect while somebody is watching rather than after.
                    ride = await sharing.resolve_token(session, token)
                except VoraError as exc:
                    await _send_error(websocket, exc.code)
                    await websocket.close(code=CLOSE_POLICY, reason="link not valid")
                    return

                view = await sharing.build_share_view(session, ride)
                await session.commit()

            payload = view.model_dump(mode="json")

            # Only when something changed. A viewer on a mobile connection
            # should not pay for a frame per tick saying the car has not moved.
            signature = (
                payload["ride_status"],
                (payload.get("current_location") or {}).get("lat"),
                (payload.get("current_location") or {}).get("lng"),
                (payload.get("current_location") or {}).get("precision"),
            )
            if signature != last_signature:
                await websocket.send_json({"type": "share_update", **payload})
                last_signature = signature

            if RideStatus(view.ride_status) not in sharing.VIEWABLE:
                await websocket.send_json(
                    {"type": "ended", "reason": view.ride_status}
                )
                await websocket.close(code=1000, reason="trip finished")
                return

            await asyncio.sleep(SHARE_POLL_S)

    except WebSocketDisconnect:
        logger.info("share_socket_closed")
    except Exception:
        logger.exception("share_socket_error")
        with contextlib.suppress(Exception):
            await websocket.close(code=CLOSE_INTERNAL, reason="internal error")


__all__ = ["router"]
