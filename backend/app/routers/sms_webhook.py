"""Proposed HTTPSMS inbound webhook.

DRAFT ONLY: do not register this router in the production FastAPI app until
webhook verification, OTP identity mapping, persistence, and place resolution
have been approved by the backend owner.
"""

from fastapi import APIRouter, Request

from app.services.httpsms_client import send_sms
from app.services.sms_parser import parse_ride_request

router = APIRouter(prefix="/webhooks/sms", tags=["sms"])


@router.post("/incoming")
async def incoming_sms(request: Request) -> dict:
    """Reply to a draft SMS request without creating a ride yet."""
    # TODO: Validate the HTTPSMS webhook signature before reading the event.
    event = await request.json()
    data = event.get("data", {})
    from_number = data.get("from")
    content = data.get("content")

    if not from_number or not content:
        return {"status": "ignored"}

    parsed = parse_ride_request(content)
    if not parsed:
        await send_sms(
            from_number,
            "Format not recognized. Send: RIDE origin;destination",
        )
        return {"status": "invalid_format"}

    # TODO: Resolve both places through the approved gazetteer/search service.
    # TODO: Map this phone number to the approved OTP/auth identity.
    # TODO: Once the ride schema is approved, create a ride with channel='sms'.
    await send_sms(
        from_number,
        f"Ride requested: {parsed['origin']} -> {parsed['destination']}. "
        "Looking for a driver...",
    )
    return {"status": "ok"}
