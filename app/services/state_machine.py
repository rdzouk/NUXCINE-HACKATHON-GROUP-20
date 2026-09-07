"""The ride state machine, as a table.

A table rather than scattered `if` statements, for a reason that is not
aesthetic: with ten states and two actors there are a hundred and sixty
possible transition attempts, and conditionals spread across eight handlers
cannot be read as a whole or tested exhaustively. A table can be printed, shown
to a jury, and enumerated by a test.

Each entry also names **who** may make the transition. That is half the
security of this phase: a passenger must not be able to mark a ride
`in_progress`, and a driver must not be able to cancel it as though the
passenger did, because the two produce different fees and different ledger
entries.

Illegal transitions return 409, never 500. Being asked to do something
impossible is a client bug or a race, not a server fault.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.schemas.ride import ActorType, RideStatus


@dataclass(frozen=True)
class Transition:
    to: RideStatus
    actors: frozenset[ActorType]
    event: str


PASSENGER = ActorType.PASSENGER
DRIVER = ActorType.DRIVER
SYSTEM = ActorType.SYSTEM
ADMIN = ActorType.ADMIN


# from-status -> the transitions legal out of it.
TRANSITIONS: dict[RideStatus, tuple[Transition, ...]] = {
    RideStatus.REQUESTED: (
        Transition(RideStatus.MATCHING, frozenset({SYSTEM}), "matching_started"),
        Transition(
            RideStatus.CANCELLED_PASSENGER,
            frozenset({PASSENGER, ADMIN}),
            "cancelled_before_match",
        ),
        Transition(RideStatus.EXPIRED, frozenset({SYSTEM}), "expired_no_driver"),
    ),
    RideStatus.MATCHING: (
        # Only the system moves a ride to accepted. A driver accepts an
        # *offer*; the claim transaction then performs this transition. Routing
        # it through the system actor keeps the atomic claim as the single
        # place a driver can ever be attached to a ride.
        Transition(RideStatus.ACCEPTED, frozenset({SYSTEM}), "driver_accepted"),
        Transition(
            RideStatus.CANCELLED_PASSENGER,
            frozenset({PASSENGER, ADMIN}),
            "cancelled_while_matching",
        ),
        Transition(RideStatus.EXPIRED, frozenset({SYSTEM}), "expired_no_driver"),
    ),
    RideStatus.ACCEPTED: (
        Transition(RideStatus.ARRIVING, frozenset({DRIVER, SYSTEM}), "driver_en_route"),
        Transition(RideStatus.ARRIVED, frozenset({DRIVER}), "driver_arrived"),
        Transition(
            RideStatus.CANCELLED_PASSENGER,
            frozenset({PASSENGER, ADMIN}),
            "cancelled_after_accept",
        ),
        Transition(
            RideStatus.CANCELLED_DRIVER,
            frozenset({DRIVER, ADMIN}),
            "driver_cancelled",
        ),
    ),
    RideStatus.ARRIVING: (
        Transition(RideStatus.ARRIVED, frozenset({DRIVER}), "driver_arrived"),
        Transition(
            RideStatus.CANCELLED_PASSENGER,
            frozenset({PASSENGER, ADMIN}),
            "cancelled_while_arriving",
        ),
        Transition(
            RideStatus.CANCELLED_DRIVER,
            frozenset({DRIVER, ADMIN}),
            "driver_cancelled",
        ),
    ),
    RideStatus.ARRIVED: (
        # Requires the PIN. That check lives in the handler because it is an
        # authentication step, not a state question, but the transition is
        # still only legal from here.
        Transition(RideStatus.IN_PROGRESS, frozenset({DRIVER}), "trip_started"),
        Transition(
            RideStatus.CANCELLED_PASSENGER,
            frozenset({PASSENGER, ADMIN}),
            "cancelled_at_pickup",
        ),
        Transition(
            RideStatus.CANCELLED_DRIVER,
            frozenset({DRIVER, ADMIN}),
            "driver_cancelled_at_pickup",
        ),
    ),
    RideStatus.IN_PROGRESS: (
        Transition(RideStatus.COMPLETED, frozenset({DRIVER, SYSTEM}), "trip_completed"),
        # No passenger cancellation once moving. A trip in progress that ends
        # early is a completion with a shorter trace, or an incident. Allowing
        # a cancel here would let a passenger ride and then void the fare.
        Transition(
            RideStatus.CANCELLED_DRIVER,
            frozenset({ADMIN}),
            "voided_by_admin",
        ),
    ),
    # Terminal.
    RideStatus.COMPLETED: (),
    RideStatus.CANCELLED_PASSENGER: (),
    RideStatus.CANCELLED_DRIVER: (),
    RideStatus.EXPIRED: (),
}

TERMINAL = frozenset(
    {
        RideStatus.COMPLETED,
        RideStatus.CANCELLED_PASSENGER,
        RideStatus.CANCELLED_DRIVER,
        RideStatus.EXPIRED,
    }
)

# Statuses in which a ride occupies a passenger and, once accepted, a driver.
LIVE = frozenset(
    {
        RideStatus.REQUESTED,
        RideStatus.MATCHING,
        RideStatus.ACCEPTED,
        RideStatus.ARRIVING,
        RideStatus.ARRIVED,
        RideStatus.IN_PROGRESS,
    }
)


def legal_targets(current: RideStatus) -> tuple[RideStatus, ...]:
    return tuple(t.to for t in TRANSITIONS.get(current, ()))


def find_transition(
    current: RideStatus, target: RideStatus
) -> Transition | None:
    for transition in TRANSITIONS.get(current, ()):
        if transition.to is target:
            return transition
    return None


def assert_transition(
    current: RideStatus, target: RideStatus, actor: ActorType
) -> Transition:
    """Validate a transition, or raise.

    Two distinct failures, deliberately answered the same way. An illegal
    transition and a transition the caller is not entitled to make both return
    409 with the current status in `details`, because telling a driver "you may
    not cancel as the passenger" is more information than they need in order to
    do their job, and slightly more than an attacker should get for free.
    """
    transition = find_transition(current, target)
    if transition is None:
        raise VoraError(
            ErrorCode.RIDE_STATE_CONFLICT,
            details={
                "current_status": current.value,
                "requested_status": target.value,
                "allowed": [s.value for s in legal_targets(current)],
            },
        )

    if actor not in transition.actors:
        raise VoraError(
            ErrorCode.RIDE_STATE_CONFLICT,
            details={
                "current_status": current.value,
                "requested_status": target.value,
            },
        )

    return transition
