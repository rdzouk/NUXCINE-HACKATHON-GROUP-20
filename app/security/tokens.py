"""JWT access tokens.

PyJWT rather than python-jose: a worse CVE history there, and we need no JWE.

Three details that are security-relevant rather than stylistic:

`algorithms=["HS256"]` is passed explicitly on decode. Omitting it is the
classic JWT vulnerability: a library that honours the token's own `alg` header
will accept `alg: none`, or accept an HMAC signed with the public key when the
server expects RS256. The allow-list has to come from the server, never the
token.

Both `iss` and `aud` are verified. Without them, a token minted for the share
service or a future admin console would be accepted by the ride API.

`jti` is present so a Phase 5 revocation list has something to key on. It is not
checked yet, and that is recorded rather than implied: an access token lives
fifteen minutes, so the window is bounded by expiry alone for now.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.config import settings
from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError

ALGORITHM = "HS256"
ISSUER = "vora"
AUDIENCE = "vora-app"


# Tolerance on the time claims, for clock skew between machines. See the note
# in decode_access_token. Conventional value; small against a 900-second token.
CLOCK_SKEW_LEEWAY_S = 30


def create_access_token(
    *, user_id: uuid.UUID, role: str, expires_in_s: int | None = None
) -> tuple[str, int]:
    """Mint an access token. Returns (token, lifetime_seconds)."""
    ttl = expires_in_s if expires_in_s is not None else settings.access_token_ttl_s
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=ttl),
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(
        payload, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM
    )
    return token, ttl


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify and decode. Raises VoraError on anything suspect.

    Expiry is reported distinctly from invalidity so the client knows to
    refresh rather than to send the user back to the login screen. That
    distinction leaks nothing: both outcomes mean the token is unusable, and
    the client already knows when it last refreshed.
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            audience=AUDIENCE,
            # RFC 7519 allows a small leeway on the time claims for clock skew,
            # and this is why it exists. Two API instances behind a load
            # balancer will not agree on the second, so without leeway a token
            # minted by one can be rejected as "not yet valid" by the other for
            # as long as they disagree. The failure is intermittent, affects
            # tokens that were working moments earlier, and reports as
            # INVALID_TOKEN, which sends you looking at the signature.
            #
            # Found the hard way: the development host's clock was oscillating
            # by 57 seconds, and live tokens kept becoming immature under it.
            # Leeway is the right fix for ordinary skew between machines. It is
            # not a fix for a broken clock, and it is not treated as one.
            #
            # Thirty seconds is the conventional value and is deliberately far
            # smaller than the fifteen-minute token lifetime, so it widens the
            # window an expired token stays usable by 3 percent.
            leeway=CLOCK_SKEW_LEEWAY_S,
            options={"require": ["exp", "iat", "nbf", "sub", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise VoraError(ErrorCode.TOKEN_EXPIRED) from exc
    except jwt.InvalidTokenError as exc:
        raise VoraError(ErrorCode.INVALID_TOKEN) from exc
