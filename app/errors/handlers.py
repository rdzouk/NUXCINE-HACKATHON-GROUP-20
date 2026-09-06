"""Every failure path in the service funnels through here.

Two contract details worth naming:

1. FastAPI answers a schema failure with 422. §6 reserves 422 for *semantically*
   invalid requests (a dropoff outside the service area) and assigns schema
   failure to 400, so RequestValidationError is remapped. Mobile keys off the
   status, and getting this wrong makes "bad JSON" and "outside Yaounde" look
   identical to the client.

2. The catch-all never returns an exception string. A stack trace in a response
   body is a free source map for an attacker; it goes to the log, keyed by the
   request_id the caller already holds.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors.codes import DEFAULT_STATUS, ErrorCode
from app.errors.envelope import VoraError
from app.i18n import message_for, negotiate_language
from app.logging import get_logger, request_id_ctx

logger = get_logger("vora.errors")

# Starlette raises bare HTTPExceptions for routing failures. Map the ones that
# can occur before any handler runs onto real contract codes.
_STATUS_TO_CODE = {
    401: ErrorCode.UNAUTHENTICATED,
    403: ErrorCode.FORBIDDEN_ROLE,
    404: ErrorCode.RIDE_NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    413: ErrorCode.REQUEST_TOO_LARGE,
    429: ErrorCode.RATE_LIMITED,
    503: ErrorCode.DEPENDENCY_UNAVAILABLE,
}


def _envelope(
    request: Request,
    code: ErrorCode,
    status_code: int,
    details: dict | None = None,
    message: str | None = None,
) -> JSONResponse:
    lang = negotiate_language(request.headers.get("accept-language"))
    payload = {
        "error": {
            "code": code.value,
            "message": message or message_for(code, lang),
            "details": details or {},
            "request_id": getattr(request.state, "request_id", None) or request_id_ctx.get(),
        }
    }
    headers: dict[str, str] = {}
    # §6: 429 always carries Retry-After. 503 carries retry_after_s in details.
    # Both statuses emit both forms so the client only implements one path.
    retry_after = (details or {}).get("retry_after_s")
    if retry_after is not None and status_code in (429, 503):
        headers["Retry-After"] = str(int(retry_after))
    return JSONResponse(status_code=status_code, content=payload, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(VoraError)
    async def _vora_error(request: Request, exc: VoraError) -> JSONResponse:
        logger.info(
            "vora_error",
            code=exc.code.value,
            status=exc.status_code,
            path=request.url.path,
        )
        return _envelope(
            request, exc.code, exc.status_code, exc.details, exc.message_override
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields = []
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query")]
            fields.append({"field": ".".join(loc) or "body", "issue": err.get("msg", "")})
        code = ErrorCode.VALIDATION_FAILED
        return _envelope(request, code, DEFAULT_STATUS[code], {"fields": fields})

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = _STATUS_TO_CODE.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        return _envelope(request, code, exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", path=request.url.path)
        code = ErrorCode.INTERNAL_ERROR
        return _envelope(request, code, DEFAULT_STATUS[code])
