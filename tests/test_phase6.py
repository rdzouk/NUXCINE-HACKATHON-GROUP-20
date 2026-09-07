"""Accessibility, corridor economics and payment abstraction.

Pure-logic tests: no database, no network. The corridor arithmetic in
particular is worth pinning here rather than only in an integration run,
because it is the number the pitch rests on and it must hold for every trip
length, not just the one in the demo.
"""

from __future__ import annotations

import pytest

from app.schemas.common import VehicleCapability
from app.schemas.ride import RideStatus
from app.services import accessibility
from app.services.corridor import (
    MAX_DETOUR_RATIO,
    MAX_DETOUR_SECONDS,
    MAX_LEGS,
)
from app.services.fare import (
    DEFAULT_FARE_CONFIG,
    compute_corridor_fare,
    compute_exclusive_fare,
)
from app.services.payments import (
    CashProvider,
    MockPaymentProvider,
    MtnMoMoProvider,
    OrangeMoneyProvider,
    PaymentMethod,
    PaymentStatus,
)

# ----------------------------------------------------------- accessibility --


def test_every_capability_has_both_languages():
    """Served rather than hardcoded in the client, so a bad translation can be
    fixed without shipping an app release. A missing one would render blank."""
    for info in accessibility.CAPABILITIES:
        assert info.label_fr and info.label_en
        assert info.description_fr and info.description_en


def test_the_capability_list_covers_the_whole_enum():
    """A capability the matcher understands but the filter UI cannot show is a
    requirement no passenger can ever ask for."""
    served = {c.key for c in accessibility.CAPABILITIES}
    assert served == set(VehicleCapability)


def test_capability_wording_describes_the_vehicle_not_the_person():
    """I9, enforced as a test rather than only as a comment.

    Law 2024/017 prohibits processing health data. "Vehicule equipe d'une
    rampe" is a fact about a car; "pour personnes handicapees" would be a
    record about a person, and it is the kind of wording that creeps in during
    a copy edit by somebody who has not read the law.
    """
    forbidden = [
        "handicap", "disabled", "invalide", "malade", "illness",
        "wheelchair user", "medical", "patient",
    ]
    for info in accessibility.CAPABILITIES:
        text = " ".join(
            [info.label_fr, info.label_en, info.description_fr, info.description_en]
        ).lower()
        for word in forbidden:
            assert word not in text, f"{info.key} describes a person: {word!r}"


def test_profile_maps_only_vehicle_capabilities():
    """`prefers_text_contact` is a communication preference, not a vehicle
    capability. Feeding it to the matcher would shrink the driver pool for a
    reason that has nothing to do with the car."""

    class FakeUser:
        requires_ramp = True
        requires_boot_space = False
        requires_front_seat = False
        requires_driver_assist = False
        allows_guide_animal = True
        prefers_text_contact = True

    required = accessibility.required_from_profile(FakeUser())
    assert set(required) == {"ramp", "guide_animal"}
    assert "prefers_text_contact" not in required


def test_announcements_exist_for_every_status_a_passenger_sees():
    for status in (
        RideStatus.ACCEPTED,
        RideStatus.ARRIVING,
        RideStatus.ARRIVED,
        RideStatus.IN_PROGRESS,
        RideStatus.COMPLETED,
    ):
        assert accessibility.announcement(status, locale="fr")
        assert accessibility.announcement(status, locale="en")


def test_the_arrival_announcement_carries_the_pin():
    """It is the one moment the PIN is useful, and the passenger is about to
    say it aloud anyway."""
    spoken = accessibility.announcement(
        RideStatus.ARRIVED,
        locale="fr",
        vehicle="Toyota Corolla",
        color="blanc",
        plate="CE 404 XY",
        pin="4821",
    )
    assert "4821" in spoken
    assert "CE 404 XY" in spoken


def test_no_other_announcement_leaks_the_pin():
    for status in (RideStatus.ACCEPTED, RideStatus.ARRIVING, RideStatus.IN_PROGRESS):
        spoken = accessibility.announcement(status, locale="fr", pin="4821")
        assert "4821" not in (spoken or "")


def test_announcement_survives_missing_details():
    """A ride with no vehicle yet must not render 'None' at somebody."""
    spoken = accessibility.announcement(RideStatus.IN_PROGRESS, locale="fr")
    assert spoken and "None" not in spoken


# --------------------------------------------------------------- corridor --


@pytest.mark.parametrize(
    "distance_m,duration_s",
    [(2_000, 400), (5_000, 900), (9_000, 1_600), (14_000, 2_400)],
)
def test_three_corridor_seats_beat_one_exclusive_fare(distance_m, duration_s):
    """The economic proposition, and the sentence said to a jury.

    Riders pay less each and the driver earns more, because the vehicle is not
    being sold to one person. If this ever inverts, corridor is a worse deal
    for the driver and they will simply refuse it.
    """
    exclusive = compute_exclusive_fare(distance_m, duration_s, DEFAULT_FARE_CONFIG)
    seat = compute_corridor_fare(distance_m, duration_s, DEFAULT_FARE_CONFIG)

    assert seat < exclusive, "a seat must cost less than the whole vehicle"
    assert seat * 3 > exclusive, "three seats must beat one exclusive fare"


def test_a_corridor_seat_is_cheaper_at_every_length():
    """Not just at the demo's distance. Rounding and two separate clamps could
    otherwise invert the order on a short hop."""
    for distance_m in range(500, 20_000, 500):
        duration_s = distance_m // 6
        seat = compute_corridor_fare(distance_m, duration_s)
        whole = compute_exclusive_fare(distance_m, duration_s)
        assert seat <= whole, f"inverted at {distance_m} m"


def test_corridor_fares_are_payable_in_coins():
    for distance_m in (1_200, 4_800, 11_300):
        assert compute_corridor_fare(distance_m, distance_m // 6) % 50 == 0


def test_the_detour_cap_is_tight_enough_to_matter():
    """Without a cap the first passenger gets a tour of the city while the
    driver fills seats, and they never share again."""
    assert 0 < MAX_DETOUR_RATIO <= 0.10
    assert 0 < MAX_DETOUR_SECONDS <= 300


def test_legs_are_capped_at_three():
    """Beyond three the first passenger's journey stops resembling what they
    booked, and the routing stops being solvable in the time a driver waits."""
    assert MAX_LEGS == 3


# --------------------------------------------------------------- payments --


@pytest.mark.asyncio
async def test_cash_is_the_default_provider():
    """The honest default for this market, and a deliberate choice rather than
    a missing integration."""
    from app.services.payments import get_payment_provider

    assert get_payment_provider().method is PaymentMethod.CASH


@pytest.mark.asyncio
async def test_mock_provider_is_idempotent():
    """Same reasoning as I8, applied to money, where charging twice is worse
    than creating a duplicate ride."""
    provider = MockPaymentProvider()
    key = "one-tap"

    first = await provider.initiate(
        amount_xaf=1500, payer_msisdn="+237600000001", idempotency_key=key
    )
    second = await provider.initiate(
        amount_xaf=1500, payer_msisdn="+237600000001", idempotency_key=key
    )

    assert first.transaction_id == second.transaction_id
    assert first.status is PaymentStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_different_keys_are_different_transactions():
    provider = MockPaymentProvider()
    a = await provider.initiate(
        amount_xaf=1000, payer_msisdn="+237600000001", idempotency_key="a"
    )
    b = await provider.initiate(
        amount_xaf=1000, payer_msisdn="+237600000001", idempotency_key="b"
    )
    assert a.transaction_id != b.transaction_id


@pytest.mark.asyncio
async def test_refund_marks_the_transaction_refunded():
    provider = MockPaymentProvider()
    paid = await provider.initiate(
        amount_xaf=2000, payer_msisdn="+237600000001", idempotency_key="r"
    )
    refunded = await provider.refund(paid.transaction_id)
    assert refunded.status is PaymentStatus.REFUNDED

    after = await provider.status(paid.transaction_id)
    assert after.status is PaymentStatus.REFUNDED


@pytest.mark.asyncio
async def test_cash_initiate_leaves_the_fare_pending():
    """It is settled in the car, not by the server."""
    result = await CashProvider().initiate(
        amount_xaf=1500, payer_msisdn="+237600000001", idempotency_key="c"
    )
    assert result.status is PaymentStatus.PENDING
    assert result.method is PaymentMethod.CASH


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", [MtnMoMoProvider(), OrangeMoneyProvider()])
async def test_unwired_providers_refuse_loudly(provider):
    """A stub that quietly answers 'declined' is worse than one that refuses:
    the first sends somebody debugging a provider that was never contacted."""
    with pytest.raises(NotImplementedError) as exc:
        await provider.initiate(
            amount_xaf=1000, payer_msisdn="+237600000001", idempotency_key="x"
        )
    assert "stub" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_a_payment_result_carries_no_payer_details():
    """A payment log is the highest-value thing in an incident, and a
    provider's error body routinely carries the credential that failed."""
    provider = MockPaymentProvider()
    result = await provider.initiate(
        amount_xaf=1500, payer_msisdn="+237699123456", idempotency_key="k"
    )
    assert "699123456" not in repr(result)
