"""Canned messages between passenger and driver.

This replaces phone contact entirely (I3), and the replacement is better than
the thing it replaces on four counts at once, which is rare enough to say out
loud:

  it cannot carry harassment, because there is no free text
  it cannot leak a phone number, for the same reason
  it translates without a translation pipeline, because the server renders it
  it works on a bad network, because one template key is a few bytes

It also serves deaf and hard-of-hearing users, who cannot use a phone call at
all. That is not a side benefit bolted on afterwards; it falls out of the same
decision.

Rendering happens server-side in the *recipient's* locale, not the sender's. A
driver writing in French and a passenger reading in English is the ordinary
case here, and neither should have to think about it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.logging import get_logger
from app.models.ride import Ride
from app.models.safety import CannedMessage
from app.schemas.ride import ActorType, MessageTemplate, RideStatus
from app.services.rides import record_event

logger = get_logger("vora.messaging")

# The complete vocabulary. Adding an entry is a product decision, not a string
# change: every one of these has to be sayable by either party without context
# and translate cleanly.
TEMPLATES: dict[MessageTemplate, dict[str, str]] = {
    MessageTemplate.AT_GATE: {
        "fr": "Je suis au portail.",
        "en": "I am at the gate.",
    },
    MessageTemplate.TWO_MIN: {
        "fr": "J'arrive dans deux minutes.",
        "en": "I will be there in two minutes.",
    },
    MessageTemplate.CANT_FIND_YOU: {
        "fr": "Je ne vous trouve pas.",
        "en": "I cannot find you.",
    },
    MessageTemplate.PLEASE_WAIT_5: {
        "fr": "Merci de patienter cinq minutes.",
        "en": "Please wait five minutes.",
    },
    MessageTemplate.ON_MY_WAY: {
        "fr": "Je suis en route.",
        "en": "I am on my way.",
    },
    MessageTemplate.ARRIVED_WAITING: {
        "fr": "Je suis arrive et je vous attends.",
        "en": "I have arrived and I am waiting.",
    },
}

# Messaging is for a live ride. Before acceptance there is no counterparty; a
# completed ride does not need an open channel, and leaving one would turn a
# finished trip into a way to keep contacting somebody.
SENDABLE = frozenset(
    {
        RideStatus.ACCEPTED,
        RideStatus.ARRIVING,
        RideStatus.ARRIVED,
        RideStatus.IN_PROGRESS,
    }
)

# One message every few seconds is plenty for a fixed vocabulary, and it stops
# the channel being used to spam somebody with a template.
MIN_INTERVAL_S = 3


def render(template: MessageTemplate, locale: str) -> str:
    """Render in the reader's language, falling back to French."""
    strings = TEMPLATES.get(template)
    if strings is None:
        raise VoraError(ErrorCode.MESSAGE_TEMPLATE_UNKNOWN)
    return strings.get(locale) or strings["fr"]


async def send(
    session: AsyncSession,
    *,
    ride: Ride,
    sender_id: uuid.UUID,
    template: MessageTemplate,
) -> CannedMessage:
    """Record a canned message on a ride."""
    status = RideStatus(ride.status)
    if status not in SENDABLE:
        raise VoraError(
            ErrorCode.RIDE_STATE_CONFLICT,
            details={
                "current_status": status.value,
                "reason": "messaging is open only while the ride is live",
            },
        )

    if template not in TEMPLATES:
        raise VoraError(ErrorCode.MESSAGE_TEMPLATE_UNKNOWN)

    recent = (
        await session.execute(
            select(CannedMessage)
            .where(
                CannedMessage.ride_id == ride.id,
                CannedMessage.sender_id == sender_id,
            )
            .order_by(CannedMessage.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if recent is not None:
        created = recent.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if (datetime.now(UTC) - created).total_seconds() < MIN_INTERVAL_S:
            raise VoraError(
                ErrorCode.RATE_LIMITED, details={"retry_after_s": MIN_INTERVAL_S}
            )

    message = CannedMessage(
        ride_id=ride.id, sender_id=sender_id, template_key=template.value
    )
    session.add(message)
    await session.flush()

    await record_event(
        session,
        ride_id=ride.id,
        event_type="message_sent",
        actor_type=ActorType.PASSENGER
        if ride.passenger_id == sender_id
        else ActorType.DRIVER,
        actor_id=sender_id,
        metadata={"template_key": template.value},
    )

    logger.info(
        "canned_message_sent",
        ride_id=str(ride.id),
        template=template.value,
    )
    return message
