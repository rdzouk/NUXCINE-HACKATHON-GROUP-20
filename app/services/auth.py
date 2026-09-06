"""Authentication service.

The two things worth reading closely are the uniform OTP response and the
refresh-token reuse detection.

**Uniform response.** `request_otp` returns the same shape, the same status and
the same timing whether or not the phone is registered. It does not create the
user. Account enumeration through a login endpoint is how an attacker turns a
stolen list of phone numbers into a list of confirmed customers, and in a
market where the phone number is the identity, that list has resale value.
The account is created at *verification*, once possession of the number is
proven.

**Reuse detection.** Refresh tokens rotate: every use issues a new token and
marks the old one rotated. If an already-rotated token is presented again, one
of two things happened, and we cannot tell which from here: either an attacker
stole the token and is using it, or the legitimate client is replaying after
the attacker already refreshed. Both cases mean the family is compromised, so
the whole family is revoked and both parties must sign in again. Revoking only
the presented token would leave the thief holding a valid chain.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.logging import get_logger
from app.models.user import OtpChallenge, RefreshToken, User
from app.security import hashing
from app.security.phone import hash_phone
from app.security.tokens import create_access_token

logger = get_logger("vora.auth")

OTP_TTL_S = 300
OTP_RESEND_AFTER_S = 60
MAX_OTP_ATTEMPTS = 5


async def create_otp_challenge(
    session: AsyncSession,
    *,
    phone_e164: str,
    request_ip: str | None,
) -> tuple[OtpChallenge, str]:
    """Create a challenge and return it with the plaintext code.

    The plaintext is returned to the caller only so it can be handed to the
    SmsSender. It is never persisted and never returned in an HTTP response.
    """
    # Invalidate any live challenge for this number. Without this, an attacker
    # who triggers a resend keeps the earlier code alive and gets several
    # concurrent guesses against the same five-minute window.
    now = datetime.now(UTC)
    await session.execute(
        update(OtpChallenge)
        .where(
            OtpChallenge.phone_e164 == phone_e164,
            OtpChallenge.consumed_at.is_(None),
            OtpChallenge.expires_at > now,
        )
        .values(consumed_at=now)
    )

    code = hashing.generate_otp_code()
    challenge = OtpChallenge(
        phone_e164=phone_e164,
        code_hash=hashing.hash_otp(code),
        max_attempts=MAX_OTP_ATTEMPTS,
        expires_at=now + timedelta(seconds=OTP_TTL_S),
        request_ip=request_ip,
    )
    session.add(challenge)
    await session.flush()
    return challenge, code


async def verify_otp_challenge(
    session: AsyncSession, *, challenge_id: uuid.UUID, code: str
) -> str:
    """Verify a code and return the phone number it proves possession of.

    A failed attempt increments the counter. Hitting the cap burns the
    challenge outright rather than merely refusing: leaving it alive would let
    an attacker keep guessing after a pause.
    """
    now = datetime.now(UTC)
    challenge = await session.get(OtpChallenge, challenge_id, with_for_update=True)

    # Unknown, consumed and expired all answer the same way. Distinguishing
    # them tells an attacker whether a challenge id was ever real.
    if challenge is None or challenge.consumed_at is not None:
        raise VoraError(ErrorCode.OTP_CHALLENGE_NOT_FOUND)

    if challenge.expires_at <= now:
        raise VoraError(ErrorCode.OTP_EXPIRED)

    if challenge.attempts >= challenge.max_attempts:
        challenge.consumed_at = now
        raise VoraError(ErrorCode.OTP_ATTEMPTS_EXCEEDED)

    challenge.attempts += 1

    if not hashing.verify_otp(challenge.code_hash, code):
        remaining = challenge.max_attempts - challenge.attempts
        if remaining <= 0:
            challenge.consumed_at = now
        logger.info(
            "otp_verify_failed",
            phone=hash_phone(challenge.phone_e164),
            attempts=challenge.attempts,
        )
        await session.flush()
        if remaining <= 0:
            raise VoraError(ErrorCode.OTP_ATTEMPTS_EXCEEDED)
        raise VoraError(ErrorCode.OTP_INVALID, details={"attempts_remaining": remaining})

    challenge.consumed_at = now
    await session.flush()
    return challenge.phone_e164


async def get_or_create_user(session: AsyncSession, *, phone_e164: str) -> User:
    """Fetch the user, creating one on first successful verification.

    Creation happens here rather than at OTP request so that an unverified
    number never produces a row. That keeps `request_otp` free of side effects
    and stops an attacker populating the users table with numbers they do not
    control.
    """
    result = await session.execute(select(User).where(User.phone_e164 == phone_e164))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    user = User(
        phone_e164=phone_e164,
        # A placeholder the user replaces via PATCH /me. Asking for a name
        # before the first ride is friction that costs conversion.
        display_name=f"Client {phone_e164[-4:]}",
        role="passenger",
        status="active",
        locale="fr",
    )
    session.add(user)
    await session.flush()
    # Load the driver relationship explicitly. A freshly constructed instance
    # has it unloaded, and the serializer reads it; under asyncio a lazy load
    # at attribute-access time raises MissingGreenlet rather than quietly
    # emitting a query. It is always None here, but relying on that would break
    # the moment a driver is created through this path.
    await session.refresh(user, attribute_names=["driver"])
    logger.info("user_created", user_id=str(user.id), phone=hash_phone(phone_e164))
    return user


async def issue_token_pair(
    session: AsyncSession, *, user: User, family_id: uuid.UUID | None = None
) -> tuple[str, str, int]:
    """Mint an access token and a refresh token. Returns (access, refresh, ttl)."""
    if user.status == "suspended":
        raise VoraError(ErrorCode.ACCOUNT_SUSPENDED)

    access_token, ttl = create_access_token(user_id=user.id, role=user.role)

    refresh_plain = hashing.generate_refresh_token()
    refresh = RefreshToken(
        user_id=user.id,
        token_hash=hashing.hash_token(refresh_plain),
        family_id=family_id or uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.refresh_token_ttl_s),
    )
    session.add(refresh)
    await session.flush()
    return access_token, refresh_plain, ttl


async def rotate_refresh_token(
    session: AsyncSession, *, presented: str
) -> tuple[str, str, int]:
    """Rotate a refresh token, detecting reuse.

    Returns (access, refresh, ttl). Raises REFRESH_TOKEN_REUSED after revoking
    the family if the presented token was already rotated.
    """
    now = datetime.now(UTC)
    token_hash = hashing.hash_token(presented)

    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    stored = result.scalar_one_or_none()

    if stored is None:
        raise VoraError(ErrorCode.REFRESH_TOKEN_INVALID)

    # The reuse signal. A token that has already been rotated is being
    # presented a second time, so the chain is in two places at once.
    if stored.rotated_at is not None:
        await _revoke_family(session, family_id=stored.family_id, reason="reuse_detected")
        logger.warning(
            "refresh_token_reuse_detected",
            user_id=str(stored.user_id),
            family_id=str(stored.family_id),
        )
        raise VoraError(ErrorCode.REFRESH_TOKEN_REUSED)

    if stored.revoked_at is not None or stored.expires_at <= now:
        raise VoraError(ErrorCode.REFRESH_TOKEN_INVALID)

    user = await session.get(User, stored.user_id)
    if user is None or user.status == "suspended":
        raise VoraError(ErrorCode.REFRESH_TOKEN_INVALID)

    stored.rotated_at = now
    # Same family, so a later replay of any link in the chain is detectable.
    return await issue_token_pair(session, user=user, family_id=stored.family_id)


async def _revoke_family(
    session: AsyncSession, *, family_id: uuid.UUID, reason: str
) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    logger.info("refresh_family_revoked", family_id=str(family_id), reason=reason)


async def revoke_refresh_token(session: AsyncSession, *, presented: str) -> None:
    """Logout. Revokes the whole family, not just this token.

    Revoking one link would leave any other device in the family signed in,
    which is not what a user means when they tap log out.
    """
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hashing.hash_token(presented)
        )
    )
    stored = result.scalar_one_or_none()
    if stored is not None:
        await _revoke_family(session, family_id=stored.family_id, reason="logout")


async def revoke_all_for_user(session: AsyncSession, *, user_id: uuid.UUID) -> None:
    """Revoke every live refresh token for a user.

    Used by a bodyless logout, and by Phase 5's graduated enforcement when an
    account is restricted or suspended: a suspension that leaves live sessions
    running is not a suspension.
    """
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    logger.info("all_sessions_revoked", user_id=str(user_id))
