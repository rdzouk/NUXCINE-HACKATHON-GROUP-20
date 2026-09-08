"""Driver routes.

The KYC gate is enforced in three independent places, on purpose:

  1. this handler returns 409 KYC_NOT_VERIFIED, per §6
  2. a database CHECK constraint refuses the row outright
  3. the matching query in Phase 3 filters on kyc_status as well

Defence in depth here is cheap and the failure mode is not: an unverified
driver going online is an unvetted stranger being sent to a passenger's
location. Any one of the three can have a bug; all three failing at once is
much less likely than one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import text

from app.api.v1._stub import COMMON_ERRORS, PUBLIC_ERRORS
from app.api.v1.rides import _render as render_ride
from app.deps import CurrentDriver, SessionDep
from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.logging import get_logger
from app.schemas.driver import (
    DriverOffersResponse,
    DriverOnlineRequest,
    DriverPresence,
    DriverPresenceResponse,
    KycDocumentRequest,
    KycDocumentResponse,
    KycStatusResponse,
    OfferAcceptResponse,
    RideNeedInfo,
    RideNeedsResponse,
    VehicleCapabilitiesResponse,
)
from app.schemas.user import KycStatus
from app.services import accessibility, matching, ride_needs
from app.services import kyc as kyc_service
from app.services import matching as offers_service

router = APIRouter(tags=["driver"])
logger = get_logger("vora.driver")


def _presence(driver) -> DriverPresenceResponse:
    return DriverPresenceResponse(
        presence=DriverPresence(
            is_online=driver.is_online,
            seats_free=driver.seats_free,
            kyc_status=KycStatus(driver.kyc_status),
            updated_at=driver.updated_at,
        )
    )


@router.post(
    "/driver/online",
    response_model=DriverPresenceResponse,
    responses=COMMON_ERRORS,
    summary="Go online",
    description=(
        "Returns 409 KYC_NOT_VERIFIED unless the driver's documents are "
        "verified. The driver is the higher-risk party and is already "
        "professionally licensed, so full KYC here costs nothing in inclusion. "
        "Location is accepted and validated but not yet persisted; the "
        "driver_presence geometry lands in Phase 2."
    ),
)
async def go_online(
    payload: DriverOnlineRequest, driver: CurrentDriver, session: SessionDep
) -> DriverPresenceResponse:
    if driver.kyc_status != "verified":
        raise VoraError(
            ErrorCode.KYC_NOT_VERIFIED, details={"kyc_status": driver.kyc_status}
        )

    driver.is_online = True
    driver.seats_free = payload.seats_free
    driver.went_online_at = datetime.now(UTC)

    # Write the position, not just the flag.
    #
    # This was missing, and the effect was that going online did nothing
    # matchable. `find_candidates` selects from `driver_presence` and discards
    # anything older than PRESENCE_MAX_AGE_S, so a driver who flipped online
    # without a fresh position was invisible to the matcher forever: online on
    # their own screen, never offered a single ride, with nothing to explain
    # it. The request already carries the coordinates; they simply were not
    # being stored.
    #
    # Upserted because a driver has exactly one presence row, and going online
    # a second time must move the pin rather than fail on the primary key.
    await session.execute(
        text(
            "INSERT INTO driver_presence "
            "  (driver_id, geom, heading, recorded_at) "
            "VALUES "
            "  (:driver_id, ST_MakePoint(:lng, :lat)::geography, :heading, now()) "
            "ON CONFLICT (driver_id) DO UPDATE SET "
            "  geom = EXCLUDED.geom, "
            "  heading = EXCLUDED.heading, "
            "  recorded_at = EXCLUDED.recorded_at, "
            "  is_stale = false"
        ),
        {
            "driver_id": driver.id,
            "lat": payload.lat,
            "lng": payload.lng,
            "heading": payload.heading,
        },
    )

    await session.commit()
    await session.refresh(driver)

    logger.info(
        "driver_online",
        driver_id=str(driver.id),
        seats_free=payload.seats_free,
    )
    return _presence(driver)


@router.post(
    "/driver/offline",
    response_model=DriverPresenceResponse,
    responses=COMMON_ERRORS,
    summary="Go offline",
)
async def go_offline(driver: CurrentDriver, session: SessionDep) -> DriverPresenceResponse:
    driver.is_online = False
    driver.seats_free = 0
    await session.commit()
    await session.refresh(driver)
    logger.info("driver_offline", driver_id=str(driver.id))
    return _presence(driver)


@router.get(
    "/driver/kyc",
    response_model=KycStatusResponse,
    responses=COMMON_ERRORS,
    summary="KYC status and what is still missing",
)
async def get_kyc_status(
    driver: CurrentDriver, session: SessionDep
) -> KycStatusResponse:
    submitted = await kyc_service.submitted_kinds(session, driver_id=driver.id)
    missing = [k for k in kyc_service.REQUIRED_DOCUMENTS if k not in submitted]
    return KycStatusResponse(
        kyc_status=KycStatus(driver.kyc_status),
        submitted=sorted(submitted, key=lambda k: k.value),
        missing=missing,
        reviewed_at=driver.kyc_reviewed_at,
        rejection_reason=driver.kyc_rejection_reason,
    )


@router.get(
    "/driver/offers",
    response_model=DriverOffersResponse,
    responses=COMMON_ERRORS,
    summary="Open ride offers for this driver",
    description=(
        "Offers still open and unexpired. An offer carries the operational "
        "facts needed to decide and nothing that identifies the passenger: "
        "before acceptance the driver has no relationship to them (I3)."
    ),
)
async def list_offers(
    driver: CurrentDriver, session: SessionDep
) -> DriverOffersResponse:
    return DriverOffersResponse(
        offers=await offers_service.list_open_offers(session, driver=driver)
    )


@router.post(
    "/driver/offers/{offer_id}/accept",
    response_model=OfferAcceptResponse,
    responses=COMMON_ERRORS,
    summary="Accept an offer",
    description=(
        "Atomic. Concurrent accepts on one offer, and concurrent accepts of "
        "different offers on the same ride, both resolve to exactly one "
        "winner. Every loser gets 409 OFFER_TAKEN rather than a 500. "
        "scripts/race_test.py fires N of these at once and asserts one 200."
    ),
)
async def accept_offer(
    offer_id: UUID, driver: CurrentDriver, session: SessionDep
) -> OfferAcceptResponse:
    ride = await matching.claim_offer(session, offer_id=offer_id, driver=driver)
    await session.commit()
    await session.refresh(ride)
    return OfferAcceptResponse(
        ride=await render_ride(session, ride, "driver")
    )


@router.post(
    "/driver/offers/{offer_id}/decline",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=COMMON_ERRORS,
    summary="Decline an offer",
    description="A declined offer is never re-issued to this driver in a later wave.",
)
async def decline_offer(
    offer_id: UUID, driver: CurrentDriver, session: SessionDep
) -> None:
    await matching.decline_offer(session, offer_id=offer_id, driver=driver)
    await session.commit()


@router.get(
    "/vehicles/capabilities",
    response_model=VehicleCapabilitiesResponse,
    responses=PUBLIC_ERRORS,
    summary="Vehicle capability vocabulary",
    description=(
        "Drives the client's accessibility filter UI. These are properties of "
        "vehicles. They are never a record of anything about a person (I9)."
    ),
)
async def list_capabilities() -> VehicleCapabilitiesResponse:
    return VehicleCapabilitiesResponse(capabilities=accessibility.CAPABILITIES)


@router.get(
    # Not /rides/needs: that is matched by /rides/{ride_id} with the id
    # "needs", so it would demand authentication and 401. Relying on
    # router ordering to disambiguate is a trap for whoever reorders them
    # next, so the path is distinct instead.
    "/ride-needs",
    response_model=RideNeedsResponse,
    responses=PUBLIC_ERRORS,
    summary="What a passenger can ask for on a ride",
    description=(
        "Drives the request picker, and carries the wording so a phrasing "
        "correction is a server change rather than an app release.\n\n"
        "Every entry is a **need**, meaning something the driver does. None is "
        "a record of anything about a person: a tall passenger, a passenger "
        "who gets carsick and a passenger with a mobility impairment all "
        "select the same option and the system cannot tell them apart. Law "
        "2024/017 prohibits processing health data, and this is what that "
        "looks like in practice (I9).\n\n"
        "`undertakings_*` is the text a driver signs before being offered a "
        "ride carrying any of these. Without it a passenger would be relying "
        "on behaviour nobody agreed to, and could be surcharged for asking."
    ),
)
async def list_ride_needs() -> RideNeedsResponse:
    return RideNeedsResponse(
        needs=[
            RideNeedInfo(
                key=info.key.value,
                label_fr=info.label_fr,
                label_en=info.label_en,
                driver_action_fr=info.driver_action_fr,
                driver_action_en=info.driver_action_en,
                requires_undertaking=(
                    info.key in ride_needs.NEEDS_REQUIRING_UNDERTAKING
                ),
                vehicle_capability=info.vehicle_capability,
            )
            for info in ride_needs.NEEDS
        ],
        undertakings_fr=ride_needs.UNDERTAKINGS_FR,
        undertakings_en=ride_needs.UNDERTAKINGS_EN,
        undertakings_version=ride_needs.UNDERTAKINGS_VERSION,
    )



@router.post(
    "/driver/kyc/documents",
    response_model=KycDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
    summary="Submit a KYC document reference",
    description=(
        "Not in the original §6 route list. Added at Phase 1 because deliverable 5 "
        "requires document upload endpoints and §6 specified none. Flagged in "
        "docs/CONTRACT_DECISIONS.md rather than added silently. "
        "The reference is encrypted with AES-GCM and bound to the driver id "
        "before storage, and is never returned by any endpoint. For a CNI only a "
        "keyed hash is retained, which is enough to deduplicate registrations and "
        "ban a person rather than an account, without holding the number itself."
    ),
)
async def submit_kyc_document(
    payload: KycDocumentRequest, driver: CurrentDriver, session: SessionDep
) -> KycDocumentResponse:
    document = await kyc_service.submit_document(
        session, driver=driver, kind=payload.kind, reference=payload.reference
    )
    await session.commit()

    submitted = await kyc_service.submitted_kinds(session, driver_id=driver.id)
    return KycDocumentResponse(
        kind=payload.kind,
        submitted_at=document.updated_at,
        kyc_status=KycStatus(driver.kyc_status),
        missing=[k for k in kyc_service.REQUIRED_DOCUMENTS if k not in submitted],
    )


__all__ = ["router"]
