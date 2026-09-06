"""Field-level encryption for KYC references.

AES-256-GCM, which is authenticated: ciphertext that has been tampered with
fails to decrypt rather than silently yielding altered plaintext. That matters
here because these fields feed identity decisions.

A fresh 96-bit nonce is generated per encryption and stored alongside the
ciphertext. GCM nonce reuse under one key is catastrophic (it leaks the
authentication key), so the nonce is never derived from the record, never a
counter, and never reused.

Why encrypt at all: Law 2024/017 prohibits processing several categories of
data outright and makes a breach notifiable without delay, with fines from 5 to
50 million FCFA. A `SELECT *` on this table yields ciphertext, so a database
compromise is an incident rather than a disclosure of national identity numbers.

The key comes from KYC_ENCRYPTION_KEY, which is distinct from the JWT and quote
secrets on purpose: compromise of a signing key must not also decrypt identity
documents.
"""

from __future__ import annotations

import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

NONCE_BYTES = 12
_VERSION = b"\x01"


def _key() -> bytes:
    # The configured secret is 64 hex characters; SHA-256 folds it to exactly
    # the 32 bytes AES-256 requires, whatever length the operator supplied.
    return hashlib.sha256(
        settings.kyc_encryption_key.get_secret_value().encode()
    ).digest()


def encrypt_field(plaintext: str, *, aad: str = "") -> bytes:
    """Encrypt a value for storage.

    `aad` binds the ciphertext to a context, such as the driver id. A record
    moved to another driver's row then fails to decrypt instead of silently
    authenticating the wrong person.
    """
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(_key()).encrypt(nonce, plaintext.encode(), aad.encode())
    # Version prefix so the format can change later without ambiguity.
    return _VERSION + nonce + ciphertext


def decrypt_field(blob: bytes, *, aad: str = "") -> str:
    if not blob or blob[:1] != _VERSION:
        raise ValueError("unrecognised ciphertext format")
    nonce = blob[1 : 1 + NONCE_BYTES]
    ciphertext = blob[1 + NONCE_BYTES :]
    try:
        return AESGCM(_key()).decrypt(nonce, ciphertext, aad.encode()).decode()
    except InvalidTag as exc:
        raise ValueError("ciphertext failed authentication") from exc
