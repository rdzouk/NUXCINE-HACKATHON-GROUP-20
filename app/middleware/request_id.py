"""Assign and propagate a request ID.

An inbound X-Request-ID is accepted only if it looks like a UUID. Echoing an
arbitrary client string straight into structured logs is a log-injection and
log-forging primitive, so anything unrecognised is replaced.
"""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging import get_logger, request_id_ctx

logger = get_logger("vora.access")

HEADER = "X-Request-ID"


def _coerce_request_id(raw: str | None) -> str:
    if not raw:
        return str(uuid.uuid4())
    try:
        return str(uuid.UUID(raw))
    except (ValueError, AttributeError, TypeError):
        return str(uuid.uuid4())


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = _coerce_request_id(request.headers.get(HEADER))
        token = request_id_ctx.set(rid)
        request.state.request_id = rid
        started = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            raise
        else:
            response.headers[HEADER] = rid
            logger.info(
                "request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            return response
        finally:
            request_id_ctx.reset(token)
