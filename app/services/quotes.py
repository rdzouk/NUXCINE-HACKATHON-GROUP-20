"""Signed fare quotes.

This module is what makes invariant I2 hold. The fare a passenger is charged is
derived from a quote the server itself signed; a price in a request body is
never read.

A quote is a self-contained HMAC-signed blob, not a database row. That choice
buys statelessness and costs one thing, which is handled explicitly below:
a signed blob is replayable. Signing proves the server minted it, not that it
has only been used once. So each quote carries a `jti` that is burned in Redis
on first use, and a second attempt gets 409 QUOTE_ALREADY_USED. Without that,
one quote creates unlimited rides under different idempotency keys.

The signing key is `QUOTE_HMAC_SECRET`, separate from `JWT_SECRET` on purpose.
Compromise of the token-signing key must not also let an attacker mint fares.

`compare_digest` for verification, never `==`: string comparison short-circuits
on the first differing byte, which leaks the correct prefix through timing.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import asdict, dataclass

from app.config import settings
from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.schemas.common import RideMode

QUOTE_TTL_S = 300
_VERSION = "v1"


@dataclass(frozen=True)
class QuotePayload:
    """Everything ride creation needs, so it re-derives rather than trusts.

    The route polyline is deliberately absent: it can run to several kilobytes,
    and a quote id travels in a request body on a mobile network. Ride creation
    re-requests the route, which also means a ride is never created against a
    route the routing engine no longer agrees with.
    """

    jti: str
    pickup_lat: float
    pickup_lng: float
    pickup_label: str
    dropoff_lat: float
    dropoff_lng: float
    dropoff_label: str
    distance_m: int
    duration_s: int
    seats: int
    mode: str
    exclusive_fare_xaf: int
    corridor_fare_xaf: int
    routing_source: str
    issued_at: int
    expires_at: int


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(body: bytes) -> str:
    digest = hmac.new(
        settings.quote_hmac_secret.get_secret_value().encode(), body, hashlib.sha256
    ).digest()
    return _b64url_encode(digest)


def mint_quote(
    *,
    pickup_lat: float,
    pickup_lng: float,
    pickup_label: str,
    dropoff_lat: float,
    dropoff_lng: float,
    dropoff_label: str,
    distance_m: int,
    duration_s: int,
    seats: int,
    mode: RideMode,
    exclusive_fare_xaf: int,
    corridor_fare_xaf: int,
    routing_source: str,
) -> tuple[str, QuotePayload]:
    """Mint a signed quote. Returns (quote_id, payload)."""
    now = int(time.time())
    payload = QuotePayload(
        jti=str(uuid.uuid4()),
        pickup_lat=round(pickup_lat, 6),
        pickup_lng=round(pickup_lng, 6),
        pickup_label=pickup_label[:160],
        dropoff_lat=round(dropoff_lat, 6),
        dropoff_lng=round(dropoff_lng, 6),
        dropoff_label=dropoff_label[:160],
        distance_m=distance_m,
        duration_s=duration_s,
        seats=seats,
        mode=mode.value,
        exclusive_fare_xaf=exclusive_fare_xaf,
        corridor_fare_xaf=corridor_fare_xaf,
        routing_source=routing_source,
        issued_at=now,
        expires_at=now + QUOTE_TTL_S,
    )
    # Sorted keys and no whitespace, so the bytes that get signed are the same
    # bytes on every machine and every Python version.
    body = json.dumps(asdict(payload), sort_keys=True, separators=(",", ":")).encode()
    return f"{_VERSION}.{_b64url_encode(body)}.{_sign(body)}", payload


def verify_quote(quote_id: str) -> QuotePayload:
    """Verify a quote's signature and expiry.

    Does not check single use: that requires Redis and lives in
    `burn_quote_jti`, which the ride-creation path calls inside its
    transaction. Splitting them keeps this function pure and testable.
    """
    try:
        version, body_b64, signature = quote_id.split(".")
    except (ValueError, AttributeError) as exc:
        raise VoraError(ErrorCode.QUOTE_INVALID) from exc

    if version != _VERSION:
        raise VoraError(ErrorCode.QUOTE_INVALID)

    try:
        body = _b64url_decode(body_b64)
    except (ValueError, TypeError) as exc:
        raise VoraError(ErrorCode.QUOTE_INVALID) from exc

    # Constant time. A byte-by-byte comparison leaks the correct prefix.
    if not hmac.compare_digest(_sign(body), signature):
        raise VoraError(ErrorCode.QUOTE_INVALID)

    try:
        payload = QuotePayload(**json.loads(body))
    except (ValueError, TypeError) as exc:
        raise VoraError(ErrorCode.QUOTE_INVALID) from exc

    if payload.expires_at <= int(time.time()):
        raise VoraError(ErrorCode.QUOTE_EXPIRED)

    return payload


async def burn_quote_jti(redis, jti: str) -> None:
    """Mark a quote as used. Raises QUOTE_ALREADY_USED on a second call.

    SET NX is atomic, so two concurrent ride creations from one quote resolve
    to exactly one winner rather than both reading "unused" and proceeding.
    The TTL matches the quote lifetime: once a quote has expired, its jti can
    no longer be replayed anyway, so keeping the key costs memory for nothing.
    """
    claimed = await redis.set(f"quote:used:{jti}", "1", nx=True, ex=QUOTE_TTL_S)
    if not claimed:
        raise VoraError(ErrorCode.QUOTE_ALREADY_USED)
