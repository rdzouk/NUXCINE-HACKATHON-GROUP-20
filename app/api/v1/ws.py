"""WebSocket routes. Implemented in Phase 4.

Declared now so the paths are fixed and mobile can wire its socket layer. Each
one accepts the connection, sends an error frame naming the phase, and closes.
Accepting before closing is deliberate: a client that gets a clean close with a
readable reason can show something useful, whereas a rejected handshake gives
it nothing to distinguish "not built yet" from "network is down".

FastAPI does not describe WebSocket routes in OpenAPI, so the frame models in
app/schemas/ws.py are injected into openapi.json by scripts/export_openapi.py.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket

from app.errors.codes import ErrorCode
from app.i18n import message_for
from app.logging import get_logger
from app.schemas.ws import ErrorFrame

router = APIRouter(prefix="/ws", tags=["websocket"])
logger = get_logger("vora.ws")

# 1011: the server encountered a condition that prevented it fulfilling the
# request. Closest standard code for "this endpoint exists but does nothing yet".
CLOSE_NOT_IMPLEMENTED = 1011


async def _close_stub(websocket: WebSocket, phase: str) -> None:
    await websocket.accept()
    frame = ErrorFrame(
        code=ErrorCode.NOT_IMPLEMENTED.value,
        message=message_for(ErrorCode.NOT_IMPLEMENTED),
    )
    await websocket.send_json({**frame.model_dump(mode="json"), "planned_phase": phase})
    await websocket.close(code=CLOSE_NOT_IMPLEMENTED, reason=f"not implemented until {phase}")


@router.websocket("/driver")
async def driver_socket(websocket: WebSocket) -> None:
    """Driver socket.

    Inbound: location frames, rate limited to one per 2 s.
    Outbound: offer, ride_update, ping.
    Auth by Authorization header on connect or a first `auth` frame. Never by
    query string: query strings are recorded in access and proxy logs.
    """
    await _close_stub(websocket, "Phase 4")


@router.websocket("/passenger")
async def passenger_socket(websocket: WebSocket) -> None:
    """Passenger socket.

    Outbound only: ride_update, driver_location, message, ping. Driver location
    is fanned out to the one subscribed passenger of the active ride, and only
    between accepted and completed (I4).
    """
    await _close_stub(websocket, "Phase 4")


@router.websocket("/share/{token}")
async def share_socket(websocket: WebSocket, token: str) -> None:
    """Public share socket. No authentication, token-scoped.

    Outbound: share_update only, throttled, and coarse until in_progress.
    """
    await _close_stub(websocket, "Phase 5")
