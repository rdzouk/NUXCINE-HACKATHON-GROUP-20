"""Hashing primitives.

Two different algorithms on purpose, because the two things being hashed have
completely different threat profiles.

**OTP codes: argon2.** A four-digit code has ten thousand possible values. Any
fast hash over that keyspace is a lookup table, so a leaked `otp_challenges`
table would hand an attacker every live code. Argon2 is memory-hard and tuned
below so that a full sweep costs far more than the five-minute window is worth.

**Refresh tokens: SHA-256.** These are 256 bits of `secrets.token_urlsafe`
entropy, so there is nothing to brute-force and a slow hash would only tax the
server on every refresh. The reason to hash at all is that a stolen database
backup must not be a set of working sessions.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, InvalidHashError, VerifyMismatchError

# Deliberately lighter than password defaults. An OTP lives five minutes and is
# verified on a hot path; the memory cost still puts a full 10k sweep far beyond
# what the TTL allows, which is the property that matters.
_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=32 * 1024,  # 32 MiB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)

OTP_LENGTH = 4


def generate_otp_code() -> str:
    """A cryptographically random OTP.

    `secrets`, never `random`. The Mersenne Twister behind `random` is
    predictable from a handful of observed outputs, and an attacker who can
    request codes for their own number gets those observations for free.
    """
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


def hash_otp(code: str) -> str:
    return _hasher.hash(code)


def verify_otp(code_hash: str, code: str) -> bool:
    """Constant-time verification, and it never raises.

    Argon2 comparison is constant-time internally, which is what keeps the
    response from leaking how many leading digits were correct.
    """
    try:
        return _hasher.verify(code_hash, code)
    except (VerifyMismatchError, InvalidHashError, InvalidHash):
        return False


def generate_refresh_token() -> str:
    """256 bits of entropy, URL-safe."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def hash_reference(value: str, *, key: str) -> str:
    """Keyed hash for a CNI or licence reference.

    Keyed, because national ID numbers are structured and low-entropy enough to
    be enumerated offline against an unkeyed hash. This gives a stable
    identifier for deduplication and banning without ever storing the number.
    """
    return hmac.new(key.encode(), value.encode(), hashlib.sha256).hexdigest()
