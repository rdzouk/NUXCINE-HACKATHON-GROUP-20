"""Global per-request timeout.

Bounds the blast radius of a hung dependency: without this a stalled OSRM or a
lock-waiting query holds a worker slot open indefinitely, and on a demo box
that is how the whole API stops responding.
"""

from __future__ import annotations

import asyncio

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.errors.codes import DEFAULT_STATUS, ErrorCode
from app.i18n import message_for, negotiate_language
from app.logging import get_logger, request_id_ctx

logger = get_logger("vora.timeout")


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, timeout_s: int) -> None:
        super().__init__(app)
        self.timeout_s = timeout_s

    async def dispatch(self, request: Request, call_next):
        # WebSocket upgrades never reach BaseHTTPMiddleware, so long-lived
        # sockets are unaffected by this timeout.
        try:
            return await asyncio.wait_for(call_next(request), timeout=self.timeout_s)
        except TimeoutError:
            code = ErrorCode.REQUEST_TIMEOUT
            logger.warning(
                "request_timeout", method=request.method, path=request.url.path
            )
            lang = negotiate_language(request.headers.get("accept-language"))
            return JSONResponse(
                status_code=DEFAULT_STATUS[code],
                content={
                    "error": {
                        "code": code.value,
                        "message": message_for(code, lang),
                        "details": {"timeout_s": self.timeout_s},
                        "request_id": request_id_ctx.get(),
                    }
                },
            )
