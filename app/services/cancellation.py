"""Cancellation policy and the debt ledger.

This is the economically real feature, and the one worth saying out loud to a
jury, because it is where we modelled an attacker who is a *legitimate user of
our own incentive system*.

**The policy.**

Free before a driver is assigned, and free for thirty seconds after acceptance:
somebody who taps by mistake should not pay, and a driver who has just accepted
has not yet spent anything but attention. After that a fee accrues, because the
driver has begun a journey they cannot bill for.

**Why a debt ledger and not a wallet.** A wallet requires pre-loading money,
which kills conversion in a cash market and needs a payment integration before
anything can be demonstrated. A debt row needs no money movement at all: it is
recorded, it blocks the next booking, and it settles in cash at the next ride.

**The anti-abuse case, which is the point.** A driver could accept rides and
idle, collecting compensation for cancellations they provoked by never moving.
So compensation pays out only if the server-held trace shows the driver
actually moved toward the pickup. The trace is already the source of truth for
the fare (I2); here it is the source of truth for whether work was done.

**Symmetry.** Drivers incur fees for late cancellation too. Without that they
cherry-pick: accept everything, then dump the cheap fares once a better offer
appears, which is worse for passengers than never having been matched.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging import get_logger
from app.models.ride import Ride
from app.models.safety import LedgerEntry
from app.schemas.ride import ActorType, CancelReason, RideStatus
from app.services.fare import round_to_coins

logger = get_logger("vora.cancellation")

# A grace window after acceptance. Long enough to undo a misfire, short enough
# that it cannot be used to hold a driver and release them repeatedly.
GRACE_AFTER_ACCEPT_S = 30

# Flat fees, in XAF, rounded to what people can actually hand over.
# Deliberately modest: this is a deterrent and a contribution to the driver's
# wasted trip, not a revenue line.
PASSENGER_CANCEL_FEE_XAF = 500
DRIVER_CANCEL_FEE_XAF = 500

# What a driver receives when a passenger cancels late, conditional on movement.
DRIVER_COMPENSATION_XAF = 300

# How far a driver must have moved toward the pickup to have earned
# compensation. Below this they have not left where they were: GPS jitter alone
# covers a hundred metres over a few minutes, and paying for that is exactly
# the farming behaviour this guards against.
MIN_MOVEMENT_M = 150.0


@dataclass(frozen=True)
class CancellationOutcome:
    fee_xaf: int
    fee_reason: str
    compensation_xaf: int
    compensation_withheld: bool
    driver_moved_m: float | None


def _is_free(ride: Ride, *, now: datetime) -> tuple[bool, str]:
    """Whether this cancellation costs nothing, and why."""
    status = RideStatus(ride.status)

    if status in (RideStatus.REQUESTED, RideStatus.MATCHING):
        return True, "no_driver_assigned"

    if ride.accepted_at is not None:
        accepted_at = ride.accepted_at
        if accepted_at.tzinfo is None:
            accepted_at = accepted_at.replace(tzinfo=UTC)
        if (now - accepted_at).total_seconds() <= GRACE_AFTER_ACCEPT_S:
            return True, "within_grace_period"

    return False, ""


async def driver_movement_toward_pickup(
    session: AsyncSession, ride: Ride
) -> float | None:
    """How far the driver has closed the gap to the pickup, in metres.

    Measured as the *reduction in distance to the pickup* between the first and
    the latest accepted trace point, not as distance travelled. A driver
    circling their own neighbourhood covers ground without approaching anybody,
    and paying for that would be paying for the exact behaviour this exists to
    detect.

    Rejected points are excluded, so a forged approach earns nothing.
    """
    row = (
        await session.execute(
            text(
                """
                WITH pts AS (
                    SELECT geom, seq
                    FROM ride_traces
                    WHERE ride_id = :ride_id AND NOT rejected
                    ORDER BY seq
                ),
                bounds AS (
                    SELECT
                        (SELECT geom FROM pts ORDER BY seq ASC  LIMIT 1) AS first_geom,
                        (SELECT geom FROM pts ORDER BY seq DESC LIMIT 1) AS last_geom
                )
                SELECT
                    ST_Distance(b.first_geom, r.pickup_geom) AS started_at_m,
                    ST_Distance(b.last_geom,  r.pickup_geom) AS now_at_m
                FROM bounds b, rides r
                WHERE r.id = :ride_id
                  AND b.first_geom IS NOT NULL
                  AND b.last_geom IS NOT NULL
                """
            ),
            {"ride_id": ride.id},
        )
    ).first()

    if row is None or row.started_at_m is None:
        # No trace at all. Not proof of idling, but not proof of movement
        # either, and the burden sits with the claim.
        return None

    return float(row.started_at_m) - float(row.now_at_m)


async def _add_entry(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    ride_id: uuid.UUID,
    kind: str,
    amount_xaf: int,
    note: str,
) -> LedgerEntry | None:
    """Append one ledger row, tolerating a duplicate.

    The unique index on (ride_id, kind, user_id) is what stops a retried
    cancellation charging twice. Colliding with it is a successful retry, not
    an error, so it returns None rather than raising.
    """
    entry = LedgerEntry(
        user_id=user_id,
        ride_id=ride_id,
        kind=kind,
        amount_xaf=amount_xaf,
        note=note,
    )
    session.add(entry)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        logger.info(
            "ledger_entry_already_exists", ride_id=str(ride_id), kind=kind
        )
        return None
    return entry


async def cancel_ride(
    session: AsyncSession,
    *,
    ride: Ride,
    actor: ActorType,
    actor_user_id: uuid.UUID,
    reason: CancelReason,
) -> CancellationOutcome:
    """Cancel a ride and write whatever the policy says is owed.

    Returns what was charged and what was paid, including whether driver
    compensation was withheld for lack of movement. That last field exists so
    the demo can show the anti-abuse case rather than assert it.
    """
    now = datetime.now(UTC)
    free, free_reason = _is_free(ride, now=now)

    target = (
        RideStatus.CANCELLED_PASSENGER
        if actor is ActorType.PASSENGER
        else RideStatus.CANCELLED_DRIVER
    )

    fee = 0
    compensation = 0
    withheld = False
    moved: float | None = None

    if free:
        fee_reason = free_reason
    elif actor is ActorType.PASSENGER:
        fee = round_to_coins(PASSENGER_CANCEL_FEE_XAF)
        fee_reason = "cancelled_after_driver_assigned"

        # Negative: owed by the passenger.
        await _add_entry(
            session,
            user_id=ride.passenger_id,
            ride_id=ride.id,
            kind="cancel_fee",
            amount_xaf=-fee,
            note=f"Annulation apres acceptation ({reason.value})",
        )

        # The anti-abuse gate. Compensation is earned by movement, not by
        # having accepted.
        if ride.driver_id is not None:
            moved = await driver_movement_toward_pickup(session, ride)
            if moved is not None and moved >= MIN_MOVEMENT_M:
                compensation = round_to_coins(DRIVER_COMPENSATION_XAF)
                driver_user_id = await session.scalar(
                    text("SELECT user_id FROM drivers WHERE id = :id"),
                    {"id": ride.driver_id},
                )
                if driver_user_id is not None:
                    await _add_entry(
                        session,
                        user_id=driver_user_id,
                        ride_id=ride.id,
                        kind="cancel_compensation",
                        amount_xaf=compensation,
                        note=f"Deplacement verifie: {int(moved)} m vers le client",
                    )
            else:
                withheld = True
                logger.info(
                    "compensation_withheld_no_movement",
                    ride_id=str(ride.id),
                    driver_id=str(ride.driver_id),
                    moved_m=moved,
                )
    else:
        fee = round_to_coins(DRIVER_CANCEL_FEE_XAF)
        fee_reason = "driver_cancelled_after_accepting"
        driver_user_id = await session.scalar(
            text("SELECT user_id FROM drivers WHERE id = :id"),
            {"id": ride.driver_id},
        )
        if driver_user_id is not None:
            await _add_entry(
                session,
                user_id=driver_user_id,
                ride_id=ride.id,
                kind="cancel_fee",
                amount_xaf=-fee,
                note=f"Annulation chauffeur ({reason.value})",
            )

    ride.cancel_reason = reason.value
    ride.cancelled_by = actor.value
    ride.cancel_fee_xaf = fee

    from app.services.rides import transition_ride

    await transition_ride(
        session,
        ride=ride,
        target=target,
        actor_type=actor,
        actor_id=actor_user_id,
        reason=reason.value,
        metadata={
            "fee_xaf": fee,
            "fee_reason": fee_reason,
            "compensation_xaf": compensation,
            "compensation_withheld": withheld,
            "driver_moved_m": round(moved, 1) if moved is not None else None,
        },
    )

    logger.info(
        "ride_cancelled",
        ride_id=str(ride.id),
        actor=actor.value,
        fee_xaf=fee,
        compensation_xaf=compensation,
        withheld=withheld,
    )

    return CancellationOutcome(
        fee_xaf=fee,
        fee_reason=fee_reason,
        compensation_xaf=compensation,
        compensation_withheld=withheld,
        driver_moved_m=moved,
    )


async def outstanding_balance(session: AsyncSession, user_id: uuid.UUID) -> int:
    """What this user owes, as a positive number. Zero if nothing.

    Only negative unsettled rows count. A driver with unpaid compensation owed
    *to* them is not in debt, and netting the two would let somebody cancel
    repeatedly as long as they were owed enough elsewhere.
    """
    total = await session.scalar(
        text(
            "SELECT coalesce(sum(amount_xaf), 0) FROM ledger_entries "
            "WHERE user_id = :user_id AND settled_at IS NULL AND amount_xaf < 0"
        ),
        {"user_id": user_id},
    )
    return abs(int(total or 0))


async def list_entries(session: AsyncSession, user_id: uuid.UUID, limit: int = 50):
    result = await session.execute(
        select(LedgerEntry)
        .where(LedgerEntry.user_id == user_id)
        .order_by(LedgerEntry.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def settle_all(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Mark outstanding debt settled. Returns how many rows were cleared.

    Cash settlement, which is the honest default for this market: the driver
    collects at the next ride and the debt clears. There is no payment
    integration behind this and the demo does not pretend otherwise.
    """
    result = await session.execute(
        text(
            "UPDATE ledger_entries SET settled_at = now() "
            "WHERE user_id = :user_id AND settled_at IS NULL AND amount_xaf < 0"
        ),
        {"user_id": user_id},
    )
    logger.info("ledger_settled", user_id=str(user_id), entries=result.rowcount)
    return result.rowcount
