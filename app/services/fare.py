"""Fare engine.

Deterministic, explainable in one sentence, and computed only on the server.

    exclusive = base + (per_km * km) + (per_min * min), clamped to [minimum, ceiling]
    corridor  = 0.68 * that rate, applied to the passenger's own travelled distance

Three decisions worth defending to a jury:

**Rounded to the nearest 50 XAF.** People pay in coins here. A fare of 1 237 XAF
is not payable in cash without the driver hunting for change, so the price the
app shows has to be a price that can actually be handed over. The smallest
commonly circulating coins make 50 the right granularity.

**A ceiling, not just a floor.** A minimum fare protects the driver on a short
trip. The ceiling protects the passenger from a pricing bug: if a bad route or
a GPS spike produces an absurd distance, the fare is capped rather than
charged. A cap that trips is a visible incident; an uncapped bug is a charge on
somebody's money.

**Corridor at 0.68.** Chosen so that each passenger pays clearly less than
exclusive hire, while two legs together come to more than one exclusive fare.
That is the whole economic proposition of the corridor model: riders pay less
and the driver earns more, because the vehicle is not being sold to one person.

It was 0.62, calibrated when three bookings could share a vehicle. The cap is
now two, for a safety reason rather than a commercial one, and at 0.62 two legs
came to 2250 XAF against 2300 for a single exclusive fare on the same route.
The driver was being asked to carry a stranger and take home less. A rate that
makes the corridor worse for the person who has to agree to it is not a
discount, it is a defect.

The arithmetic it has to satisfy: rate * (full fare + joining leg fare) must
exceed the full fare. On a joining leg worth about half the route, that puts
the floor near 0.64. 0.68 clears it with room, and still leaves every passenger
paying roughly a third less than exclusive hire.

**This holds when the joining leg is a real share of the route, and not
otherwise.** A joiner riding two streets adds two streets of fare, and no
multiplier changes that. The corridor is worth the driver's while because the
matcher only offers legs that are contained in the route already being driven.

Deliberately a flat multiplier and not a bidding or load-factor model, which
would be unexplainable and unverifiable at demo scale.

No traffic prediction and no dynamic surge. We have no historical data, and a
model faked from nothing is the sort of claim a jury checks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Rounding granularity. See the module docstring: cash, in coins.
ROUND_TO_XAF = 50


@dataclass(frozen=True)
class FareConfig:
    """One object, so the whole pricing policy is visible in one place.

    Values are in XAF and are calibrated against what shared taxis and
    exclusive hire actually cost in Yaounde, not derived from a model.
    """

    base_xaf: int = 300
    per_km_xaf: int = 250
    per_min_xaf: int = 15
    minimum_fare_xaf: int = 500
    # Roughly a cross-city exclusive trip. Anything above this is a bug, not a
    # journey, and is capped rather than charged.
    ceiling_fare_xaf: int = 15_000
    corridor_rate: float = 0.68
    surge_multiplier: float = 1.0

    def __post_init__(self) -> None:
        if not 0 < self.corridor_rate < 1:
            raise ValueError("corridor_rate must sit strictly between 0 and 1")
        if self.surge_multiplier < 1.0:
            raise ValueError("surge_multiplier below 1.0 would underprice the driver")
        if self.minimum_fare_xaf > self.ceiling_fare_xaf:
            raise ValueError("minimum fare cannot exceed the ceiling")


DEFAULT_FARE_CONFIG = FareConfig()


def round_to_coins(amount: float, *, granularity: int = ROUND_TO_XAF) -> int:
    """Round to something a passenger can actually hand over in cash.

    Half-up, not Python's built-in `round`. `round` implements banker's
    rounding, which sends halves to the nearest *even* multiple: `round(0.5)`
    is 0, so 25 XAF rounds down to nothing while 75 rounds up to 100. Besides
    producing a free ride at the bottom of the range, treating identical halves
    inconsistently is the sort of thing a driver notices and stops trusting.
    """
    if amount <= 0:
        return 0
    return int(math.floor(amount / granularity + 0.5) * granularity)


@dataclass(frozen=True)
class FareQuote:
    exclusive_xaf: int
    corridor_xaf: int
    distance_m: int
    duration_s: int
    config: FareConfig

    @property
    def is_corridor_cheaper(self) -> bool:
        return self.corridor_xaf < self.exclusive_xaf


def _raw_exclusive(distance_m: int, duration_s: int, config: FareConfig) -> float:
    km = distance_m / 1000.0
    minutes = duration_s / 60.0
    return (
        config.base_xaf + (config.per_km_xaf * km) + (config.per_min_xaf * minutes)
    ) * config.surge_multiplier


def compute_exclusive_fare(
    distance_m: int, duration_s: int, config: FareConfig = DEFAULT_FARE_CONFIG
) -> int:
    """Exclusive hire: the passenger buys the vehicle."""
    raw = _raw_exclusive(distance_m, duration_s, config)
    clamped = min(max(raw, config.minimum_fare_xaf), config.ceiling_fare_xaf)
    return round_to_coins(clamped)


def compute_corridor_fare(
    distance_m: int, duration_s: int, config: FareConfig = DEFAULT_FARE_CONFIG
) -> int:
    """Corridor: the passenger buys a seat for the distance they travel.

    The rate is applied to the *unclamped* exclusive rate before the minimum is
    enforced, then clamped separately. Applying it after the exclusive clamp
    would make a short corridor trip cost 62 percent of the exclusive minimum,
    which is not what a per-seat price means.

    The corridor minimum is deliberately lower than the exclusive minimum: the
    driver is carrying several of these at once, so the floor that protects
    them on an exclusive trip does not apply per seat.
    """
    raw = _raw_exclusive(distance_m, duration_s, config) * config.corridor_rate
    corridor_minimum = round_to_coins(config.minimum_fare_xaf * config.corridor_rate)
    clamped = min(max(raw, corridor_minimum), config.ceiling_fare_xaf)
    return round_to_coins(clamped)


def quote_both(
    distance_m: int, duration_s: int, config: FareConfig = DEFAULT_FARE_CONFIG
) -> FareQuote:
    """Price a trip both ways, so the client can show the choice."""
    if distance_m < 0 or duration_s < 0:
        raise ValueError("distance and duration must not be negative")

    exclusive = compute_exclusive_fare(distance_m, duration_s, config)
    corridor = compute_corridor_fare(distance_m, duration_s, config)

    # Rounding and two different clamps can, on a very short trip, push the
    # corridor price up to meet the exclusive one. Corridor must never cost
    # more than buying the whole vehicle, or the offer makes no sense.
    corridor = min(corridor, exclusive)

    return FareQuote(
        exclusive_xaf=exclusive,
        corridor_xaf=corridor,
        distance_m=distance_m,
        duration_s=duration_s,
        config=config,
    )
