"""Fare engine tests.

These matter more than they look. The fare is the one number a passenger and a
driver both check, and a pricing bug is a charge on somebody's money rather
than a broken screen.
"""

from __future__ import annotations

import pytest

from app.services.fare import (
    DEFAULT_FARE_CONFIG,
    FareConfig,
    compute_exclusive_fare,
    quote_both,
    round_to_coins,
)


@pytest.mark.parametrize(
    "raw,expected",
    [(0, 0), (24, 0), (25, 50), (49, 50), (74, 50), (75, 100), (1237, 1250), (1263, 1250)],
)
def test_rounds_to_fifty(raw, expected):
    """People pay in coins. A fare of 1 237 XAF cannot be handed over."""
    assert round_to_coins(raw) == expected


@pytest.mark.parametrize(
    "distance_m,duration_s",
    [(500, 120), (2_000, 480), (7_500, 1_500), (15_000, 2_700), (30_000, 5_400)],
)
def test_every_fare_is_payable_in_cash(distance_m, duration_s):
    fare = compute_exclusive_fare(distance_m, duration_s)
    assert fare % 50 == 0, f"{fare} cannot be paid without hunting for change"


def test_minimum_fare_protects_the_driver_on_a_short_trip():
    """A 200 m hop must not price below the floor."""
    assert compute_exclusive_fare(200, 60) >= DEFAULT_FARE_CONFIG.minimum_fare_xaf


def test_ceiling_caps_an_absurd_distance():
    """A GPS spike or a broken route must not produce an unbounded charge.

    This is the guard that turns a pricing bug into a visible incident instead
    of a charge somebody has to dispute.
    """
    assert compute_exclusive_fare(5_000_000, 900_000) == round_to_coins(
        DEFAULT_FARE_CONFIG.ceiling_fare_xaf
    )


def test_fare_rises_with_distance():
    fares = [compute_exclusive_fare(d, d // 8) for d in (1_000, 3_000, 6_000, 12_000)]
    assert fares == sorted(fares)
    assert len(set(fares)) == len(fares), "distinct distances must price distinctly"


@pytest.mark.parametrize(
    "distance_m,duration_s",
    [(1_500, 400), (4_000, 900), (9_000, 1_800), (14_000, 2_600)],
)
def test_corridor_always_beats_exclusive(distance_m, duration_s):
    """The whole proposition of the corridor model.

    If a seat ever cost as much as the vehicle, there would be no reason for a
    passenger to accept sharing.
    """
    quote = quote_both(distance_m, duration_s)
    assert quote.corridor_xaf < quote.exclusive_xaf
    assert quote.is_corridor_cheaper


def test_a_full_corridor_earns_the_driver_more_than_one_exclusive_fare():
    """The other half of the proposition: riders pay less, the driver earns more.

    Three passengers at the corridor rate must exceed one exclusive fare, or
    the driver is worse off for sharing and will simply refuse.
    """
    quote = quote_both(8_000, 1_500)
    assert quote.corridor_xaf * 3 > quote.exclusive_xaf


def test_corridor_is_never_more_expensive_even_on_a_tiny_trip():
    """Rounding plus two separate clamps could otherwise invert the order."""
    for distance_m in range(100, 3_000, 100):
        quote = quote_both(distance_m, distance_m // 5)
        assert quote.corridor_xaf <= quote.exclusive_xaf, f"inverted at {distance_m} m"


def test_surge_is_a_plain_multiplier():
    """Config, not a model. We have no historical data to justify anything else."""
    base = compute_exclusive_fare(5_000, 900)
    surged = compute_exclusive_fare(
        5_000, 900, FareConfig(surge_multiplier=1.5)
    )
    assert surged > base


def test_config_rejects_nonsense_at_construction():
    with pytest.raises(ValueError):
        FareConfig(corridor_rate=1.4)  # corridor dearer than exclusive
    with pytest.raises(ValueError):
        FareConfig(corridor_rate=0)
    with pytest.raises(ValueError):
        FareConfig(surge_multiplier=0.5)  # underprices the driver
    with pytest.raises(ValueError):
        FareConfig(minimum_fare_xaf=20_000, ceiling_fare_xaf=1_000)


def test_negative_inputs_are_rejected():
    """A negative distance means a bug upstream; pricing it would hide that."""
    with pytest.raises(ValueError):
        quote_both(-100, 60)
    with pytest.raises(ValueError):
        quote_both(100, -60)


def test_pricing_is_deterministic():
    """Same inputs, same fare, every time. A quote is shown then re-derived at
    ride creation, and the two must agree exactly."""
    first = quote_both(6_200, 1_140)
    second = quote_both(6_200, 1_140)
    assert first.exclusive_xaf == second.exclusive_xaf
    assert first.corridor_xaf == second.corridor_xaf
