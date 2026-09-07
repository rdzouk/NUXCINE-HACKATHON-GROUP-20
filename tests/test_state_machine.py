"""Ride state machine tests.

The machine is a table precisely so it can be enumerated, and this file is what
cashes that in. With ten states and four actor types there are four hundred
possible transition attempts; a handful of spot checks would leave most of them
unexercised, and the dangerous ones are the combinations nobody thought about.

The security-relevant assertions here are the ones about *who* may make a
transition. A driver marking a ride cancelled-by-passenger, or a passenger
marking their own ride completed, would each produce the wrong fee and the
wrong ledger entry while looking like an ordinary state change.
"""

from __future__ import annotations

import itertools

import pytest

from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.schemas.ride import ActorType, RideStatus
from app.services.state_machine import (
    LIVE,
    TERMINAL,
    TRANSITIONS,
    assert_transition,
    find_transition,
    legal_targets,
)

ALL_STATUSES = list(RideStatus)
ALL_ACTORS = list(ActorType)


def test_every_status_appears_in_the_table():
    """A status with no entry is a hole: nothing can leave it, and no test
    would notice until a ride got stuck there in production."""
    missing = [s.value for s in ALL_STATUSES if s not in TRANSITIONS]
    assert not missing, f"statuses absent from the table: {missing}"


def test_terminal_states_have_no_exits():
    for status in TERMINAL:
        assert legal_targets(status) == (), f"{status.value} is not terminal"


def test_non_terminal_states_all_have_an_exit():
    """Every live state must be escapable, or a ride can strand there."""
    for status in ALL_STATUSES:
        if status in TERMINAL:
            continue
        assert legal_targets(status), f"{status.value} is a dead end"


def test_every_live_status_can_reach_a_terminal_state():
    """Breadth-first from each live state. A ride that cannot terminate is a
    row that stays in the passenger's active slot forever, and the partial
    unique index then blocks them from ever booking again."""
    for start in LIVE:
        seen: set[RideStatus] = set()
        queue = [start]
        reached_terminal = False
        while queue:
            current = queue.pop()
            if current in seen:
                continue
            seen.add(current)
            if current in TERMINAL:
                reached_terminal = True
                break
            queue.extend(legal_targets(current))
        assert reached_terminal, f"{start.value} cannot reach a terminal state"


def test_the_happy_path_is_walkable():
    path = [
        RideStatus.REQUESTED,
        RideStatus.MATCHING,
        RideStatus.ACCEPTED,
        RideStatus.ARRIVING,
        RideStatus.ARRIVED,
        RideStatus.IN_PROGRESS,
        RideStatus.COMPLETED,
    ]
    for current, target in itertools.pairwise(path):
        assert find_transition(current, target) is not None, (
            f"{current.value} -> {target.value} is not in the table"
        )


def test_a_ride_cannot_skip_the_pin():
    """arrived -> in_progress is the only way in, and it is the PIN gate."""
    for status in ALL_STATUSES:
        if status is RideStatus.ARRIVED:
            continue
        assert find_transition(status, RideStatus.IN_PROGRESS) is None, (
            f"{status.value} can reach in_progress without passing through arrived"
        )


def test_only_the_driver_starts_a_trip():
    assert_transition(RideStatus.ARRIVED, RideStatus.IN_PROGRESS, ActorType.DRIVER)
    for actor in (ActorType.PASSENGER, ActorType.SYSTEM, ActorType.ADMIN):
        with pytest.raises(VoraError):
            assert_transition(RideStatus.ARRIVED, RideStatus.IN_PROGRESS, actor)


def test_a_driver_cannot_cancel_as_the_passenger():
    """The two cancellations carry different fees and different ledger entries,
    so letting a driver pick which one is recorded is a money bug."""
    with pytest.raises(VoraError):
        assert_transition(
            RideStatus.ACCEPTED, RideStatus.CANCELLED_PASSENGER, ActorType.DRIVER
        )


def test_a_passenger_cannot_cancel_as_the_driver():
    with pytest.raises(VoraError):
        assert_transition(
            RideStatus.ACCEPTED, RideStatus.CANCELLED_DRIVER, ActorType.PASSENGER
        )


def test_a_passenger_cannot_cancel_a_trip_in_progress():
    """Otherwise a passenger rides to the destination and then voids the fare."""
    with pytest.raises(VoraError):
        assert_transition(
            RideStatus.IN_PROGRESS,
            RideStatus.CANCELLED_PASSENGER,
            ActorType.PASSENGER,
        )


def test_a_passenger_cannot_complete_their_own_ride():
    with pytest.raises(VoraError):
        assert_transition(
            RideStatus.IN_PROGRESS, RideStatus.COMPLETED, ActorType.PASSENGER
        )


def test_only_the_system_attaches_a_driver():
    """A driver accepts an *offer*; the atomic claim performs this transition.
    Keeping it system-only means the claim transaction is the single place a
    driver can ever be attached to a ride."""
    assert_transition(RideStatus.MATCHING, RideStatus.ACCEPTED, ActorType.SYSTEM)
    for actor in (ActorType.PASSENGER, ActorType.DRIVER):
        with pytest.raises(VoraError):
            assert_transition(RideStatus.MATCHING, RideStatus.ACCEPTED, actor)


@pytest.mark.parametrize("status", list(TERMINAL))
@pytest.mark.parametrize("actor", ALL_ACTORS)
def test_nothing_escapes_a_terminal_state(status, actor):
    """Exhaustive: every terminal state, every actor, every target."""
    for target in ALL_STATUSES:
        with pytest.raises(VoraError) as exc:
            assert_transition(status, target, actor)
        assert exc.value.code is ErrorCode.RIDE_STATE_CONFLICT


def test_illegal_transitions_are_409_not_500():
    """Being asked to do something impossible is a client bug or a race, not a
    server fault, and the difference matters to whoever reads the alerts."""
    with pytest.raises(VoraError) as exc:
        assert_transition(
            RideStatus.REQUESTED, RideStatus.COMPLETED, ActorType.DRIVER
        )
    assert exc.value.status_code == 409
    assert exc.value.code is ErrorCode.RIDE_STATE_CONFLICT


def test_the_refusal_names_what_was_allowed():
    """So a client can correct itself instead of guessing."""
    with pytest.raises(VoraError) as exc:
        assert_transition(
            RideStatus.REQUESTED, RideStatus.COMPLETED, ActorType.DRIVER
        )
    details = exc.value.details
    assert details["current_status"] == "requested"
    assert "allowed" in details


def test_an_unauthorised_actor_is_not_told_it_was_an_actor_problem():
    """A legal transition attempted by the wrong actor reports the same shape
    as an illegal one, without an `allowed` list. Telling a driver which actor
    *could* have done it is more than they need and slightly more than an
    attacker should get."""
    with pytest.raises(VoraError) as exc:
        assert_transition(
            RideStatus.ARRIVED, RideStatus.IN_PROGRESS, ActorType.PASSENGER
        )
    assert "allowed" not in exc.value.details


def test_live_and_terminal_partition_every_status():
    """No status is both live and finished, and none is neither. The partial
    unique indexes key on exactly this split, so a status that fell outside it
    would silently stop counting against the one-live-ride-per-passenger rule.
    """
    assert set(ALL_STATUSES) == LIVE | TERMINAL
    assert not (LIVE & TERMINAL)
