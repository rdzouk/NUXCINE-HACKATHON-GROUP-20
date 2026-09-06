"""Reject oversized request bodies.

Content-Length is checked first so an oversized upload is refused before it is
read. That header is client-controlled and may be absent on a chunked request,
so the receive channel is also metered: a body that lies about its size is cut
off at the same limit rather than being buffered to exhaustion.
"""

from __future__ import annotations

import json

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.errors.codes import DEFAULT_STATUS, ErrorCode
from app.i18n import message_for, negotiate_language


class BodySizeLimitMiddleware:
    """Pure ASGI, not BaseHTTPMiddleware, so it can meter the receive stream."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        declared = headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > self.max_bytes:
                    await self._reject(scope, send)
                    return
            except ValueError:
                pass  # Unparseable length; the metered receive below still applies.

        seen = 0
        too_large = False

        async def metered_receive() -> Message:
            nonlocal seen, too_large
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.max_bytes:
                    too_large = True
                    # Truncate rather than hand the app a partial body.
                    return {"type": "http.disconnect"}
            return message

        await self.app(scope, metered_receive, send)

    async def _reject(self, scope: Scope, send: Send) -> None:
        headers = Headers(scope=scope)
        lang = negotiate_language(headers.get("accept-language"))
        code = ErrorCode.REQUEST_TOO_LARGE
        body = json.dumps(
            {
                "error": {
                    "code": code.value,
                    "message": message_for(code, lang),
                    "details": {"max_bytes": self.max_bytes},
                    # This middleware runs outside the request-ID context, so
                    # the envelope stays well-formed with an explicit sentinel.
                    "request_id": "-",
                }
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": DEFAULT_STATUS[code],
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
