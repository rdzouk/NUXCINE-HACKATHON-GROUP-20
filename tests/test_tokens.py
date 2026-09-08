"""Access token issuance and verification.

The clock-skew tests here exist because of a real failure: the development
host's wall clock was oscillating by 57 seconds, and every time it jumped
backward, live tokens became "not yet valid" and were rejected as
INVALID_TOKEN. That reads like a signature problem and sends you looking in
entirely the wrong place.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import settings
from app.errors.envelope import VoraError
from app.security.tokens import (
    ALGORITHM,
    AUDIENCE,
    CLOCK_SKEW_LEEWAY_S,
    ISSUER,
    create_access_token,
    decode_access_token,
)


def mint_at(moment: datetime, *, user_id: uuid.UUID | None = None) -> str:
    """A token whose time claims are written as if minted at `moment`.

    Built directly rather than by patching a clock. `create_access_token` reads
    `datetime.now`, so patching `time.time` shifts nothing and produces a test
    that passes without exercising anything, which is exactly what the first
    version of this file did.
    """
    subject = user_id or uuid.uuid4()
    payload = {
        "sub": str(subject),
        "role": "passenger",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": moment,
        "nbf": moment,
        "exp": moment + timedelta(seconds=settings.access_token_ttl_s),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(
        payload, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM
    )


def test_a_normal_token_round_trips():
    user_id = uuid.uuid4()
    token, ttl = create_access_token(user_id=user_id, role="passenger")

    claims = decode_access_token(token)
    assert claims["sub"] == str(user_id)
    assert claims["role"] == "passenger"
    assert ttl == settings.access_token_ttl_s


# ------------------------------------------------------------ clock skew --


def test_there_is_leeway_on_the_time_claims():
    """Two API instances will not agree on the second. Without leeway a token
    minted by one is rejected by the other as not yet valid for as long as
    their clocks differ."""
    assert CLOCK_SKEW_LEEWAY_S > 0


def test_the_leeway_stays_small_against_the_token_lifetime():
    """Leeway also widens the window an expired token keeps working, so it has
    to stay a rounding error against the lifetime, not an extension of it."""
    assert CLOCK_SKEW_LEEWAY_S <= 60
    assert settings.access_token_ttl_s * 0.1 > CLOCK_SKEW_LEEWAY_S


def test_a_token_minted_slightly_ahead_is_accepted():
    """The exact failure seen on a host whose clock was oscillating.

    A backward jump leaves every live token's `nbf` in the future, and without
    leeway PyJWT raises ImmatureSignatureError, which surfaces as
    INVALID_TOKEN on a token that worked seconds earlier.
    """
    user_id = uuid.uuid4()
    ahead = datetime.now(UTC) + timedelta(seconds=CLOCK_SKEW_LEEWAY_S / 2)

    claims = decode_access_token(mint_at(ahead, user_id=user_id))
    assert claims["sub"] == str(user_id)


def test_a_token_from_far_ahead_is_still_refused():
    """Leeway is tolerance for skew, not a hole. Beyond it `nbf` has to keep
    meaning something, or a forged future token is honoured indefinitely."""
    far_ahead = datetime.now(UTC) + timedelta(seconds=CLOCK_SKEW_LEEWAY_S + 3600)

    with pytest.raises(VoraError):
        decode_access_token(mint_at(far_ahead))


def test_an_expired_token_is_still_refused_past_the_leeway():
    """The leeway must not become a quiet extension of the token lifetime."""
    long_ago = datetime.now(UTC) - timedelta(
        seconds=settings.access_token_ttl_s + CLOCK_SKEW_LEEWAY_S + 60
    )

    with pytest.raises(VoraError):
        decode_access_token(mint_at(long_ago))


def test_a_token_signed_with_another_secret_is_refused():
    """Leeway changes the time claims only. Nothing about it touches the
    signature."""
    payload = {
        "sub": str(uuid.uuid4()),
        "role": "passenger",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": datetime.now(UTC),
        "nbf": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(seconds=900),
        "jti": str(uuid.uuid4()),
    }
    forged = jwt.encode(payload, "not-the-real-secret", algorithm=ALGORITHM)

    with pytest.raises(VoraError):
        decode_access_token(forged)
