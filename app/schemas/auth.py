"""Authentication contract.

The OTP request endpoint returns the same 202 body whether or not the phone is
registered, and Phase 1 will make it take the same time either way. Anything
else turns this endpoint into a free account-enumeration oracle.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import VoraModel
from app.schemas.user import User

# E.164. Phase 1 normalises and validates properly with `phonenumbers`; this
# pattern is only the boundary sanity check so junk never reaches that layer.
PHONE_PATTERN = r"^\+[1-9]\d{7,14}$"


class OtpRequestRequest(VoraModel):
    phone: str = Field(pattern=PHONE_PATTERN, examples=["+237600000001"])


class OtpRequestResponse(VoraModel):
    """Identical shape for known and unknown numbers. Do not add a field that
    varies with registration state."""

    challenge_id: UUID
    expires_at: datetime
    resend_after_s: int = Field(ge=0)


class OtpVerifyRequest(VoraModel):
    challenge_id: UUID
    code: str = Field(min_length=4, max_length=8, pattern=r"^\d{4,8}$")


class TokenPair(VoraModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(description="Access token lifetime in seconds.")


class AuthSessionResponse(VoraModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: User


class RefreshRequest(VoraModel):
    refresh_token: str = Field(min_length=16, max_length=4096)


class RefreshResponse(VoraModel):
    """Refresh rotates. The token presented here is dead after this call, and
    presenting it again revokes the whole family (Phase 1 reuse detection)."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class LogoutRequest(VoraModel):
    """Optional body for POST /auth/logout.

    §6 specifies a bodyless logout, so this stays optional and that call keeps
    working unchanged. Supplying the refresh token narrows the revocation to
    that one device's token family instead of signing the user out everywhere.
    """

    refresh_token: str | None = Field(default=None, min_length=16, max_length=4096)
