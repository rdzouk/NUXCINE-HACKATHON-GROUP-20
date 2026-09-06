"""Ride routes. The quote lands in Phase 2, the lifecycle in Phase 3,
safety in Phase 5.

Every route below that takes a `{ride_id}` will be wrapped by the single
`require_ride_participant` dependency in Phase 3 (I1). It is one dependency
applied to every route, not a per-handler check, because per-handler checks
miss one and the one they miss is the IDOR.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header, Query, status

from app.api.v1._stub import COMMON_ERRORS, not_implemented
from app.schemas.ride import (
    IncidentReportRequest,
    IncidentResponse,
    RideCancelRequest,
    RideCancelResponse,
    RideCompleteResponse,
    RideCreateRequest,
    RideListResponse,
    RideMessageRequest,
    RideMessageResponse,
    RideResponse,
    RideStartRequest,
    RideStatus,
    ShareLinkResponse,
)

router = APIRouter(tags=["rides"])


@router.post(
    "/rides",
    response_model=RideResponse,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
    summary="Create a ride from a quote",
    description=(
        "Requires an Idempotency-Key header (I8). Mobile networks here drop and "
        "retry; without de-duplication one tap creates two rides. The key is "
        "scoped per user and expires after 24 hours."
    ),
)
async def create_ride(
    payload: RideCreateRequest,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        description="Client-generated. Reuse it verbatim when retrying.",
    ),
) -> RideResponse:
    not_implemented("Phase 3")


@router.get(
    "/rides",
    response_model=RideListResponse,
    responses=COMMON_ERRORS,
    summary="List the caller's rides",
)
async def list_rides(
    status_filter: RideStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None, max_length=512),
) -> RideListResponse:
    not_implemented("Phase 3")


@router.get(
    "/rides/{ride_id}",
    response_model=RideResponse,
    responses=COMMON_ERRORS,
    summary="Read one ride",
    description=(
        "A caller who is not the passenger, the assigned driver or an admin "
        "receives 404 RIDE_NOT_FOUND, never 403. The existence of a ride is "
        "itself information."
    ),
)
async def get_ride(ride_id: UUID) -> RideResponse:
    not_implemented("Phase 3")


@router.post(
    "/rides/{ride_id}/cancel",
    response_model=RideCancelResponse,
    responses=COMMON_ERRORS,
    summary="Cancel a ride",
    description=(
        "Free before acceptance, or within 30 s of it. After that a fee accrues "
        "to the ledger and must be settled before the next booking."
    ),
)
async def cancel_ride(ride_id: UUID, payload: RideCancelRequest) -> RideCancelResponse:
    not_implemented("Phase 5")


@router.post(
    "/rides/{ride_id}/share",
    response_model=ShareLinkResponse,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
    summary="Mint a trip-share link",
)
async def create_share_link(ride_id: UUID) -> ShareLinkResponse:
    not_implemented("Phase 5")


@router.delete(
    "/rides/{ride_id}/share",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=COMMON_ERRORS,
    summary="Revoke every share link for this ride",
)
async def revoke_share_link(ride_id: UUID) -> None:
    not_implemented("Phase 5")


@router.post(
    "/rides/{ride_id}/messages",
    response_model=RideMessageResponse,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
    summary="Send a canned message",
    description=(
        "Template keys only. Free text is never accepted here. This replaces "
        "phone contact between the parties entirely (I3)."
    ),
)
async def send_message(
    ride_id: UUID, payload: RideMessageRequest
) -> RideMessageResponse:
    not_implemented("Phase 5")


@router.post(
    "/rides/{ride_id}/sos",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
    summary="Raise an SOS",
    description=(
        "Seals an immutable snapshot: trace summary, driver and vehicle "
        "identifiers, timestamps, both parties. This path gets its own error "
        "handling and must succeed under partial system degradation."
    ),
)
async def raise_sos(ride_id: UUID) -> IncidentResponse:
    not_implemented("Phase 5")


@router.post(
    "/rides/{ride_id}/report",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
    summary="File an incident report",
)
async def report_incident(
    ride_id: UUID, payload: IncidentReportRequest
) -> IncidentResponse:
    not_implemented("Phase 5")


@router.post(
    "/rides/{ride_id}/arrived",
    response_model=RideResponse,
    responses=COMMON_ERRORS,
    summary="Driver reports arrival at pickup",
)
async def driver_arrived(ride_id: UUID) -> RideResponse:
    not_implemented("Phase 3")


@router.post(
    "/rides/{ride_id}/start",
    response_model=RideResponse,
    responses=COMMON_ERRORS,
    summary="Start the trip with the passenger's PIN",
    description=(
        "The passenger reads the four-digit PIN aloud and the driver enters it. "
        "This is what makes impersonation at pickup fail. Wrong PIN returns 403; "
        "five failures escalate to support."
    ),
)
async def start_ride(ride_id: UUID, payload: RideStartRequest) -> RideResponse:
    not_implemented("Phase 5")


@router.post(
    "/rides/{ride_id}/complete",
    response_model=RideCompleteResponse,
    responses=COMMON_ERRORS,
    summary="Complete the trip",
    description=(
        "The final fare is computed from the server-held GPS trace, never from "
        "a client-reported distance (I2)."
    ),
)
async def complete_ride(ride_id: UUID) -> RideCompleteResponse:
    not_implemented("Phase 3")
