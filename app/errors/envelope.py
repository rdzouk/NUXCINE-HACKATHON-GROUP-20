"""The one error shape. Nothing in this service may emit any other.

§6 fixes this envelope. It is identical on every failure, which is what lets
the mobile client write one error path instead of ten.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.errors.codes import DEFAULT_STATUS, ErrorCode


class ErrorBody(BaseModel):
    code: ErrorCode = Field(..., description="Stable SCREAMING_SNAKE error code.")
    message: str = Field(..., description="Human-readable. French unless Accept-Language says otherwise.")
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str = Field(..., description="Correlates with the server log line for this request.")


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class VoraError(Exception):
    """Raise this anywhere. The handler turns it into the envelope.

    Handlers never build error responses by hand, so the shape cannot drift.
    """

    def __init__(
        self,
        code: ErrorCode,
        *,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        message: str | None = None,
    ) -> None:
        self.code = code
        self.status_code = status_code if status_code is not None else DEFAULT_STATUS[code]
        self.details = details or {}
        # Override only for cases the static i18n table cannot express. Prefer
        # putting variable parts in `details` so the message stays translatable.
        self.message_override = message
        super().__init__(code.value)
