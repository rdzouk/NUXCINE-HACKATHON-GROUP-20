"""Admin routes.

Not in §6. Phase 1 deliverable 5 requires an admin approval step for driver
KYC, and §6 specified no admin surface at all. Added here and flagged in
docs/CONTRACT_DECISIONS.md rather than introduced silently.

Kept deliberately thin. This is the approval stub the build plan asked for, not
an admin console: two endpoints, no bulk operations, no free-text search, no
way to read a decrypted document. An admin account is the highest-value target
in the system, so the blast radius of one being compromised is bounded by there
being very little here to abuse.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.v1._stub import COMMON_ERRORS
from app.deps import AdminUser, SessionDep
from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.logging import get_logger
from app.models.user import Driver
from app.schemas.driver import DriverAdminView, KycDecisionRequest
from app.schemas.user import KycStatus
from app.services import kyc as kyc_service

router = APIRouter(prefix="/admin", tags=["admin"])
logger = get_logger("vora.admin")


async def _to_view(session, driver: Driver) -> DriverAdminView:
    submitted = await kyc_service.submitted_kinds(session, driver_id=driver.id)
    return DriverAdminView(
        driver_id=driver.id,
        user_id=driver.user_id,
        display_name=driver.user.display_name,
        kyc_status=KycStatus(driver.kyc_status),
        submitted=sorted(submitted, key=lambda k: k.value),
        missing=[k for k in kyc_service.REQUIRED_DOCUMENTS if k not in submitted],
        is_online=driver.is_online,
        reviewed_at=driver.kyc_reviewed_at,
        rejection_reason=driver.kyc_rejection_reason,
    )


@router.get(
    "/drivers",
    response_model=list[DriverAdminView],
    responses=COMMON_ERRORS,
    summary="List drivers by KYC status",
    description=(
        "Review queue. Returns no phone numbers and no decrypted document "
        "references: approving KYC needs to know which documents exist, not "
        "what they say, so an admin session compromise leaks neither."
    ),
)
async def list_drivers(
    admin: AdminUser,
    session: SessionDep,
    kyc_status: KycStatus = Query(default=KycStatus.PENDING),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[DriverAdminView]:
    result = await session.execute(
        select(Driver)
        .where(Driver.kyc_status == kyc_status.value)
        .order_by(Driver.created_at)
        .limit(limit)
    )
    drivers = result.scalars().all()
    return [await _to_view(session, d) for d in drivers]


@router.post(
    "/drivers/{driver_id}/kyc",
    response_model=DriverAdminView,
    responses=COMMON_ERRORS,
    summary="Approve, reject or suspend a driver",
    description=(
        "Moves the driver through the KYC state machine. Verification is "
        "refused while any required document is missing, and that check lives "
        "in the service rather than in a console, so no second interface can "
        "bypass it. Every decision is written to the audit log with the "
        "reviewer's id: Law 2024/017 requires an annual security report, and "
        "'who approved this driver' is exactly what it has to answer."
    ),
)
async def decide_kyc(
    driver_id: UUID,
    payload: KycDecisionRequest,
    admin: AdminUser,
    session: SessionDep,
) -> DriverAdminView:
    driver = await session.get(Driver, driver_id)
    if driver is None:
        raise VoraError(ErrorCode.RIDE_NOT_FOUND, message="Chauffeur introuvable.")

    if payload.status is KycStatus.REJECTED and not payload.reason:
        raise VoraError(
            ErrorCode.VALIDATION_FAILED,
            details={"field": "reason"},
            message="Un motif est requis pour un rejet.",
        )

    await kyc_service.set_kyc_status(
        session,
        driver=driver,
        new_status=payload.status.value,
        reviewer_id=admin.id,
        reason=payload.reason,
    )
    await session.commit()
    await session.refresh(driver)
    return await _to_view(session, driver)
