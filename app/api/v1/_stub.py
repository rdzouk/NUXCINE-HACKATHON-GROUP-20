"""Phase 0 stub helpers.

Every route in the §6 surface exists and is fully typed, but returns
501 NOT_IMPLEMENTED in the standard envelope. That is the whole point of this
phase: mobile can generate a client, mock every call, and see the real error
shape, starting at hour three instead of hour forty.

As each phase lands, `not_implemented()` is deleted from the routes it covers.
A grep for it is an accurate progress report.
"""

from __future__ import annotations

from typing import Any, NoReturn

from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.schemas.common import ErrorResponse

_ERROR = {"model": ErrorResponse}

# Attached to every route so openapi.json documents the envelope on failures,
# not just on success. Mobile builds its error handling from this.
COMMON_ERRORS: dict[int | str, dict[str, Any]] = {
    400: {**_ERROR, "description": "Malformed request or schema failure"},
    401: {**_ERROR, "description": "Missing or invalid access token"},
    403: {**_ERROR, "description": "Authenticated but role-forbidden"},
    404: {**_ERROR, "description": "Not found, or not visible to the caller"},
    409: {**_ERROR, "description": "State conflict"},
    422: {**_ERROR, "description": "Semantically invalid"},
    429: {**_ERROR, "description": "Rate limited. Carries Retry-After."},
    500: {**_ERROR, "description": "Internal error"},
    501: {**_ERROR, "description": "Not implemented yet (Phase 0 stub)"},
    503: {**_ERROR, "description": "Dependency unavailable"},
}

PUBLIC_ERRORS: dict[int | str, dict[str, Any]] = {
    k: v for k, v in COMMON_ERRORS.items() if k not in (401, 403)
}


def not_implemented(phase: str) -> NoReturn:
    """Raise the contract's 501. `phase` tells a caller when to expect it."""
    raise VoraError(
        ErrorCode.NOT_IMPLEMENTED,
        details={"planned_phase": phase},
    )
