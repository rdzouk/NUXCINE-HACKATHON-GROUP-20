"""Plausibility filter tests.

Two failure directions, and they are not symmetric.

A **false accept** lets a forged point inflate a fare, which is theft from a
passenger. A **false reject** discards a real driver's real distance, which is
theft from a driver. The second is the one that erodes trust fastest, because
it happens to honest people going about their day, so the thresholds are set
loose and these tests spend as much effort on what must be accepted as on what
must be refused.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.services.plausibility import (
    MAX_ACCURACY_M,
    MAX_SPEED_MPS,
    Point,
    RejectReason,
    check,
)

NOW = datetime(2026, 9, 7, 12, 0, 0, tzinfo=UTC)
# Points are placed relative to NOW, and the filter is asked to judge them from
# a clock a few minutes later. Judging from NOW itself would make every point
# with a positive offset "in the future" and mask the check under test.
LATER = NOW + timedelta(minutes=5)

# Carrefour Warda and a point about 60 m away.
WARDA = (3.8760, 11.5120)
NEARBY = (3.87655, 11.51225)
DOUALA = (4.0511, 9.7679)


def point(coords, *, offset_s: float = 0, accuracy: float | None = 8.0) -> Point:
    return Point(
        lat=coords[0],
        lng=coords[1],
        recorded_at=NOW + timedelta(seconds=offset_s),
        accuracy_m=accuracy,
    )


def test_the_first_point_of_a_trace_is_accepted():
    """Nothing to compare against, so it stands on its own."""
    assert check(point(WARDA), None, now=LATER).accepted


def test_an_ordinary_urban_hop_is_accepted():
    """Roughly 60 m in 10 s, about 22 km/h. A completely normal fix."""
    verdict = check(point(NEARBY, offset_s=10), point(WARDA), now=LATER)
    assert verdict.accepted, verdict.reason


@pytest.mark.parametrize("speed_kmh", [5, 20, 40, 60, 90, 120])
def test_every_realistic_road_speed_is_accepted(speed_kmh):
    """A driver on the motorway out of town must not be treated as an attacker."""
    metres = (speed_kmh / 3.6) * 10
    # About 1 degree of latitude per 111 km.
    moved = (WARDA[0] + metres / 111_000, WARDA[1])
    verdict = check(point(moved, offset_s=10), point(WARDA), now=LATER)
    assert verdict.accepted, f"{speed_kmh} km/h rejected as {verdict.reason}"


def test_teleport_across_the_country_is_rejected():
    """Yaounde to Douala between two fixes. The classic fare inflation."""
    verdict = check(point(DOUALA, offset_s=10), point(WARDA), now=LATER)
    assert verdict.rejected
    assert verdict.reason is RejectReason.TELEPORT


def test_impossible_speed_is_rejected():
    """A plausible distance in an implausible time.

    Deliberately under the teleport threshold, so this exercises the speed
    check rather than being caught by the distance one first.
    """
    metres = MAX_SPEED_MPS * 10 * 3  # three times the limit
    moved = (WARDA[0] + metres / 111_000, WARDA[1])
    verdict = check(point(moved, offset_s=10), point(WARDA), now=LATER)
    assert verdict.rejected
    assert verdict.reason in (
        RejectReason.IMPOSSIBLE_SPEED,
        RejectReason.TELEPORT,
    )


def test_poor_accuracy_is_rejected():
    """A phone reporting a 500 m radius is not telling us where it is."""
    verdict = check(point(NEARBY, offset_s=10, accuracy=500), point(WARDA), now=LATER)
    assert verdict.rejected
    assert verdict.reason is RejectReason.POOR_ACCURACY


def test_accuracy_right_at_the_threshold_is_accepted():
    """Boundary. Urban canyons routinely report close to this."""
    verdict = check(
        point(NEARBY, offset_s=10, accuracy=MAX_ACCURACY_M), point(WARDA), now=LATER
    )
    assert verdict.accepted


def test_missing_accuracy_is_not_treated_as_bad_accuracy():
    """Plenty of clients omit it. Absent is not the same as terrible."""
    verdict = check(point(NEARBY, offset_s=10, accuracy=None), point(WARDA), now=LATER)
    assert verdict.accepted


def test_going_backwards_in_time_is_rejected():
    """Reordering the trace is how a teleport is made to look like a detour."""
    verdict = check(point(NEARBY, offset_s=-30), point(WARDA), now=LATER)
    assert verdict.rejected
    assert verdict.reason is RejectReason.NON_MONOTONIC


def test_two_points_at_the_same_instant_are_rejected():
    """Zero elapsed time implies infinite speed. Allowing it would let an
    attacker stack distance without any time to pay for it."""
    verdict = check(point(NEARBY, offset_s=0), point(WARDA, offset_s=0), now=LATER)
    assert verdict.rejected
    assert verdict.reason is RejectReason.NON_MONOTONIC


def test_a_timestamp_from_the_future_is_rejected():
    # Judged from NOW, so an offset of ten minutes really is ahead of the clock.
    verdict = check(point(WARDA, offset_s=600), None, now=NOW)
    assert verdict.rejected
    assert verdict.reason is RejectReason.FUTURE_TIMESTAMP


def test_small_clock_skew_is_tolerated():
    """Phone clocks drift. A couple of seconds ahead is not an attack."""
    assert check(point(WARDA, offset_s=2), None, now=NOW).accepted


@pytest.mark.parametrize(
    "coords",
    [(91.0, 11.5), (-91.0, 11.5), (3.87, 181.0), (3.87, -181.0)],
)
def test_coordinates_outside_the_globe_are_rejected(coords):
    verdict = check(point(coords), None, now=LATER)
    assert verdict.rejected
    assert verdict.reason is RejectReason.OUT_OF_RANGE


def test_gps_jitter_on_a_stationary_car_is_not_an_attack():
    """A parked phone drifts a few metres between fixes.

    Over a short interval that implies a high speed, and rejecting it would
    punish every driver waiting at a pickup. Below the movement floor the
    implied speed is treated as noise rather than evidence.
    """
    jitter = (WARDA[0] + 0.00002, WARDA[1] + 0.00002)  # about 3 m
    verdict = check(point(jitter, offset_s=0.5), point(WARDA), now=LATER)
    assert verdict.accepted, verdict.reason


def test_a_rejected_verdict_carries_the_numbers_behind_it():
    """The reason alone is not evidence. The implied speed and distance are
    what make a forgery attempt legible in an incident report."""
    verdict = check(point(DOUALA, offset_s=10), point(WARDA), now=LATER)
    assert verdict.rejected
    assert verdict.distance_m is not None
    assert verdict.distance_m > 100_000
