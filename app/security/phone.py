"""E.164 phone normalisation and policy.

Uses `phonenumbers` rather than a regex. Cameroonian mobile numbering moved to
nine digits behind the 6 prefix, local writing habits vary (`+237 6XX`, `00237
6XX`, bare `6XX`), and a hand-rolled pattern gets some of those wrong in a way
that silently locks real users out. The library also gives us the region check
for free, which is what enforces the `+237`-only policy.

Normalising at the boundary matters beyond tidiness: `users.phone_e164` is
UNIQUE, so two spellings of one number must collapse to one row or the same
person can hold two accounts and route around a ban.
"""

from __future__ import annotations

import hashlib
import hmac

import phonenumbers

from app.config import settings
from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError

DEFAULT_REGION = "CM"


def normalise_phone(raw: str) -> str:
    """Parse anything a user might type into canonical E.164.

    Raises VoraError(PHONE_NOT_ALLOWED) for unparseable, impossible, or
    out-of-policy numbers. The caller never sees a distinction between those
    cases, because telling an attacker *why* a number was rejected helps them
    enumerate valid ranges.
    """
    candidate = (raw or "").strip().replace(" ", "").replace("-", "")
    if candidate.startswith("00"):
        candidate = "+" + candidate[2:]

    # Test numbers are checked before validity, not after.
    #
    # libphonenumber rejects a synthetic number whose prefix is not an
    # allocated Cameroonian mobile range, which is correct for real traffic and
    # useless for a test fixture: any number that passes is a number that
    # reaches a real handset. So a value matching the configured test prefix is
    # accepted without a validity check.
    #
    # The bypass is narrow on purpose. It requires the flag *and* a non-production
    # environment *and* an exact prefix match, so it cannot be reached by
    # accident and cannot be reached at all in production.
    if _is_test_candidate(candidate):
        return candidate

    try:
        parsed = phonenumbers.parse(candidate, DEFAULT_REGION)
    except phonenumbers.NumberParseException as exc:
        raise VoraError(ErrorCode.PHONE_NOT_ALLOWED) from exc

    if not phonenumbers.is_valid_number(parsed):
        raise VoraError(ErrorCode.PHONE_NOT_ALLOWED)

    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

    if str(parsed.country_code) not in settings.allowed_country_code_list:
        raise VoraError(ErrorCode.PHONE_NOT_ALLOWED)

    return e164


def _is_test_candidate(candidate: str) -> bool:
    if settings.is_production or not settings.allow_test_numbers:
        return False
    prefix = settings.test_number_prefix
    if not prefix or not candidate.startswith(prefix):
        return False
    # Everything after the prefix must be digits, and the whole thing must look
    # like E.164, so the bypass cannot be used to smuggle arbitrary strings
    # into a UNIQUE column that the rest of the system treats as a phone number.
    suffix = candidate[len(prefix) :]
    return suffix.isdigit() and 1 <= len(suffix) <= 4 and len(candidate) <= 16


def is_test_number(e164: str) -> bool:
    """Whether a normalised number is a synthetic test number."""
    return _is_test_candidate(e164)


def hash_phone(e164: str) -> str:
    """Keyed hash of a phone number, for logs and rate-limit keys.

    A plain SHA-256 of a phone number is reversible in practice: the Cameroonian
    mobile keyspace is small enough to enumerate exhaustively in seconds. Keying
    it with a server secret means log access alone does not deanonymise anyone.
    Truncated to 16 hex characters, which is ample to avoid collisions at this
    scale and keeps log lines readable.
    """
    digest = hmac.new(
        settings.jwt_secret.get_secret_value().encode(),
        e164.encode(),
        hashlib.sha256,
    ).hexdigest()
    return digest[:16]
