"""Auth routes.

The OTP request handler is the most attacked endpoint in the system, so its
ordering is deliberate and worth not rearranging casually:

  1. normalise the phone (rejects junk before it can consume any budget)
  2. consume the rate-limit buckets, most specific first
  3. only then create a challenge and send

Doing the limiter check before any database write means a flood costs one Redis
round trip rather than a transaction. Doing it after normalisation means two
spellings of one number cannot each get their own bucket.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from redis.exceptions import RedisError

from app.api.v1._stub import COMMON_ERRORS, PUBLIC_ERRORS
from app.deps import ClientIp, CurrentUser, SessionDep
from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.logging import get_logger
from app.schemas.auth import (
    AuthSessionResponse,
    LogoutRequest,
    OtpRequestRequest,
    OtpRequestResponse,
    OtpVerifyRequest,
    RefreshRequest,
    RefreshResponse,
)
from app.security.phone import hash_phone, normalise_phone
from app.services import auth as auth_service
from app.services.rate_limit import (
    OTP_GLOBAL_BREAKER,
    OTP_PER_IP_HOURLY,
    OTP_PER_PHONE_DAILY,
    OTP_PER_PHONE_HOURLY,
    OTP_VERIFY_PER_IP,
    limiter,
)
from app.services.serializers import serialize_user
from app.services.sms import get_sms_sender

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger("vora.auth.api")


async def _enforce(checks, *, context: str) -> None:
    """Apply rate-limit layers, failing closed if Redis is unreachable.

    Fail-closed is the whole point on the OTP path. If the limiter cannot be
    consulted, the alternative is an uncapped SMS spend for the duration of a
    Redis outage, which is exactly the condition an attacker would try to
    create.
    """
    try:
        decision = await limiter.check_all(checks)
    except RedisError as exc:
        logger.error("rate_limiter_down_failing_closed", context=context)
        raise VoraError(
            ErrorCode.DEPENDENCY_UNAVAILABLE, details={"retry_after_s": 30}
        ) from exc

    if not decision.allowed:
        raise VoraError(
            ErrorCode.RATE_LIMITED,
            details={
                "retry_after_s": max(decision.retry_after_s, 1),
                "limit": decision.limit_name,
            },
        )


@router.post(
    "/otp/request",
    response_model=OtpRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=PUBLIC_ERRORS,
    summary="Request an OTP",
    description=(
        "Returns 202 with an identical body whether or not the phone is "
        "registered. Rate limited per phone (3/hour, 10/day), per IP (20/hour), "
        "and behind a global circuit breaker that halts sending outright if "
        "system-wide volume crosses a threshold."
    ),
)
async def request_otp(
    payload: OtpRequestRequest, session: SessionDep, ip: ClientIp
) -> OtpRequestResponse:
    phone = normalise_phone(payload.phone)

    await _enforce(
        [
            (OTP_PER_PHONE_HOURLY, phone),
            (OTP_PER_PHONE_DAILY, phone),
            (OTP_PER_IP_HOURLY, ip),
            (OTP_GLOBAL_BREAKER, "all"),
        ],
        context="otp_request",
    )

    challenge, code = await auth_service.create_otp_challenge(
        session, phone_e164=phone, request_ip=ip
    )
    await session.commit()

    await get_sms_sender().send_otp(phone, code)

    # Logged with the number hashed. Auth logs are the most-read logs in any
    # incident, and a plaintext phone column in them is a standing leak.
    logger.info("otp_requested", phone=hash_phone(phone), challenge_id=str(challenge.id))

    # No field here varies with whether the number is registered.
    return OtpRequestResponse(
        challenge_id=challenge.id,
        expires_at=challenge.expires_at,
        resend_after_s=auth_service.OTP_RESEND_AFTER_S,
    )


@router.post(
    "/otp/verify",
    response_model=AuthSessionResponse,
    responses=PUBLIC_ERRORS,
    summary="Verify an OTP and open a session",
    description=(
        "Creates the account on first successful verification. The user row is "
        "not created at request time, so an unverified number never produces one."
    ),
)
async def verify_otp(
    payload: OtpVerifyRequest, session: SessionDep, ip: ClientIp
) -> AuthSessionResponse:
    # Verification is limited separately from sending. Without this, the
    # per-challenge attempt cap is the only barrier and an attacker simply
    # requests a fresh challenge for each batch of guesses.
    await _enforce([(OTP_VERIFY_PER_IP, ip)], context="otp_verify")

    phone = await auth_service.verify_otp_challenge(
        session, challenge_id=payload.challenge_id, code=payload.code
    )
    user = await auth_service.get_or_create_user(session, phone_e164=phone)
    access, refresh, ttl = await auth_service.issue_token_pair(session, user=user)
    await session.commit()

    logger.info("session_opened", user_id=str(user.id), role=user.role)

    return AuthSessionResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=ttl,
        user=serialize_user(user),
    )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    responses=PUBLIC_ERRORS,
    summary="Rotate the refresh token",
    description=(
        "The presented token is invalidated by this call. Presenting it again "
        "is treated as theft and revokes the entire token family, signing out "
        "every device in that chain."
    ),
)
async def refresh(payload: RefreshRequest, session: SessionDep) -> RefreshResponse:
    try:
        access, new_refresh, ttl = await auth_service.rotate_refresh_token(
            session, presented=payload.refresh_token
        )
    except VoraError:
        # Commit anyway: a reuse detection revokes the family, and that
        # revocation must survive the error response. Rolling back here would
        # leave a known-compromised family live.
        await session.commit()
        raise

    await session.commit()
    return RefreshResponse(
        access_token=access, refresh_token=new_refresh, expires_in=ttl
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=COMMON_ERRORS,
    summary="Revoke the current session",
    description=(
        "With a refresh_token in the body, revokes that token's family, which "
        "signs out this device. With no body, revokes every family for the "
        "caller, which signs out all their devices. Either way a family is "
        "revoked whole: revoking one link would leave the other devices in "
        "that chain signed in, which is not what a user means by log out.\n\n"
        "The body is optional so that §6's bodyless POST /auth/logout keeps "
        "working exactly as specified."
    ),
)
async def logout(
    session: SessionDep,
    user: CurrentUser,
    payload: LogoutRequest | None = None,
) -> None:
    if payload is not None and payload.refresh_token:
        await auth_service.revoke_refresh_token(
            session, presented=payload.refresh_token
        )
    else:
        await auth_service.revoke_all_for_user(session, user_id=user.id)
    await session.commit()
    logger.info("session_closed", user_id=str(user.id))
