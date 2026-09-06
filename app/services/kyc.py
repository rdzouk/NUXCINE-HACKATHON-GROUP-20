"""Driver KYC.

§4.2 sets the asymmetry this implements: passengers are gated on a verified
phone only, drivers carry full KYC. That is not an oversight in favour of
drivers, it is the inclusion argument. Large numbers of Cameroonians lack a
birth certificate and therefore lack a CNI, so ID-gating passenger signup would
exclude legitimate users. A driver is the higher-risk party and is already
professionally licensed, so the same requirement costs nothing there.

What is stored, and what is not:

  the document reference    AES-GCM ciphertext, bound to the driver id
  the CNI number            never stored; only a keyed hash, for deduplication
                            and for banning a person rather than an account
  a face scan               never. Law 2024/017 prohibits biometric processing,
                            which rules out face-match verification entirely

The state machine is pending -> verified | rejected, with suspended reachable
from verified. Transitions are validated against a table rather than scattered
conditionals, for the same reason Phase 3's ride machine will be: an unlisted
transition is a bug, and a table makes that checkable.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.logging import get_logger
from app.models.user import Driver, KycDocument
from app.schemas.driver import KycDocumentKind
from app.security.crypto import encrypt_field
from app.security.hashing import hash_reference

logger = get_logger("vora.kyc")

# What a driver must submit before an admin can verify them. The vehicle photo
# and driver photo are here because they are what a passenger checks at the
# kerb, which is the mitigation for third-party impersonation at pickup.
REQUIRED_DOCUMENTS: list[KycDocumentKind] = [
    KycDocumentKind.CNI,
    KycDocumentKind.DRIVING_LICENCE,
    KycDocumentKind.VEHICLE_REGISTRATION,
    KycDocumentKind.VEHICLE_PHOTO,
    KycDocumentKind.DRIVER_PHOTO,
]

# Legal transitions. Anything absent is rejected with 409.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"verified", "rejected"},
    "rejected": {"pending", "verified"},
    "verified": {"suspended"},
    "suspended": {"verified", "rejected"},
}


async def submitted_kinds(
    session: AsyncSession, *, driver_id: uuid.UUID
) -> set[KycDocumentKind]:
    result = await session.execute(
        select(KycDocument.kind).where(KycDocument.driver_id == driver_id)
    )
    return {KycDocumentKind(row) for row in result.scalars().all()}


async def submit_document(
    session: AsyncSession,
    *,
    driver: Driver,
    kind: KycDocumentKind,
    reference: str,
) -> KycDocument:
    """Store an encrypted document reference.

    Re-submitting a kind replaces the previous one, which is what a driver
    correcting a typo expects. The replacement resets nothing about review
    state on its own; an admin still has to look again.
    """
    if driver.kyc_status == "suspended":
        raise VoraError(
            ErrorCode.RIDE_STATE_CONFLICT,
            details={"reason": "kyc_suspended"},
            message="Votre compte chauffeur est suspendu.",
        )

    # Bound to the driver id, so a row moved to another driver fails to
    # decrypt rather than silently authenticating the wrong person.
    ciphertext = encrypt_field(reference, aad=str(driver.id))

    result = await session.execute(
        select(KycDocument).where(
            KycDocument.driver_id == driver.id, KycDocument.kind == kind.value
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        document = KycDocument(
            driver_id=driver.id, kind=kind.value, reference_enc=ciphertext
        )
        session.add(document)
    else:
        document.reference_enc = ciphertext
        document.reviewed_at = None

    if kind is KycDocumentKind.CNI:
        # Keyed, because national ID numbers are structured and low-entropy
        # enough to enumerate offline against an unkeyed hash.
        driver.cni_ref_hash = hash_reference(
            reference, key=settings.kyc_encryption_key.get_secret_value()
        )

    await session.flush()
    logger.info("kyc_document_submitted", driver_id=str(driver.id), kind=kind.value)
    return document


async def set_kyc_status(
    session: AsyncSession,
    *,
    driver: Driver,
    new_status: str,
    reviewer_id: uuid.UUID,
    reason: str | None = None,
) -> Driver:
    """Move a driver through the KYC state machine.

    Verification refuses to proceed while any required document is missing.
    That check lives here rather than in the admin UI so that a second
    interface, or a script, cannot bypass it.
    """
    from datetime import UTC, datetime

    current = driver.kyc_status
    if new_status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise VoraError(
            ErrorCode.RIDE_STATE_CONFLICT,
            details={"from": current, "to": new_status},
            message="Transition de statut non autorisee.",
        )

    if new_status == "verified":
        missing = [
            k.value
            for k in REQUIRED_DOCUMENTS
            if k not in await submitted_kinds(session, driver_id=driver.id)
        ]
        if missing:
            raise VoraError(
                ErrorCode.RIDE_STATE_CONFLICT,
                details={"missing_documents": missing},
                message="Documents manquants pour la validation.",
            )

    driver.kyc_status = new_status
    driver.kyc_reviewed_at = datetime.now(UTC)
    driver.kyc_rejection_reason = reason if new_status == "rejected" else None

    # A driver who is no longer verified cannot remain online. The database
    # CHECK would refuse the row anyway; doing it here makes the intent
    # explicit rather than surfacing as an integrity error.
    if new_status != "verified":
        driver.is_online = False
        driver.seats_free = 0

    await session.flush()
    # Admin actions on identity data are audited. Law 2024/017 requires an
    # annual security report, and "who approved this driver" is exactly the
    # question that report has to answer.
    logger.info(
        "kyc_status_changed",
        driver_id=str(driver.id),
        from_status=current,
        to_status=new_status,
        reviewer_id=str(reviewer_id),
    )
    return driver
