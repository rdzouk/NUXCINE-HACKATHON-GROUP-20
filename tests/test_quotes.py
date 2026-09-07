"""Signed quote tests.

This is invariant I2's test file. Every case here is an attempt to make the
server accept a price it did not compute.
"""

from __future__ import annotations

import base64
import json
import time

import pytest

from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.schemas.common import RideMode
from app.services import quotes


def mint(**overrides):
    kwargs = {
        "pickup_lat": 3.8480,
        "pickup_lng": 11.5021,
        "pickup_label": "Carrefour Warda",
        "dropoff_lat": 3.8660,
        "dropoff_lng": 11.5170,
        "dropoff_label": "Marche Central",
        "distance_m": 4200,
        "duration_s": 900,
        "seats": 1,
        "mode": RideMode.EXCLUSIVE,
        "exclusive_fare_xaf": 1800,
        "corridor_fare_xaf": 1100,
        "routing_source": "osrm",
    }
    kwargs.update(overrides)
    return quotes.mint_quote(**kwargs)


def test_a_freshly_minted_quote_verifies():
    quote_id, payload = mint()
    verified = quotes.verify_quote(quote_id)
    assert verified.jti == payload.jti
    assert verified.exclusive_fare_xaf == 1800
    assert verified.distance_m == 4200


def test_tampering_with_the_fare_is_rejected():
    """The attack this whole module exists to stop.

    A patched client decodes the quote, lowers the fare, re-encodes, and sends
    it. Without a signature check the server would charge the attacker's number.
    """
    quote_id, _ = mint()
    version, body_b64, signature = quote_id.split(".")

    padding = "=" * (-len(body_b64) % 4)
    body = json.loads(base64.urlsafe_b64decode(body_b64 + padding))
    body["exclusive_fare_xaf"] = 50  # a 1 800 XAF trip for 50

    forged_body = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    forged_b64 = base64.urlsafe_b64encode(forged_body).rstrip(b"=").decode()
    forged = f"{version}.{forged_b64}.{signature}"

    with pytest.raises(VoraError) as exc:
        quotes.verify_quote(forged)
    assert exc.value.code is ErrorCode.QUOTE_INVALID


def test_tampering_with_the_distance_is_rejected():
    """Inflating distance is the driver-side version of the same attack."""
    quote_id, _ = mint()
    version, body_b64, signature = quote_id.split(".")
    padding = "=" * (-len(body_b64) % 4)
    body = json.loads(base64.urlsafe_b64decode(body_b64 + padding))
    body["distance_m"] = 99_000

    forged_body = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    forged_b64 = base64.urlsafe_b64encode(forged_body).rstrip(b"=").decode()

    with pytest.raises(VoraError):
        quotes.verify_quote(f"{version}.{forged_b64}.{signature}")


def test_a_forged_signature_is_rejected():
    quote_id, _ = mint()
    version, body_b64, _ = quote_id.split(".")
    with pytest.raises(VoraError):
        quotes.verify_quote(f"{version}.{body_b64}.notarealsignature")


@pytest.mark.parametrize(
    "bad",
    ["", "garbage", "v1.only-two-parts", "v1..", "....", "v2.abc.def"],
)
def test_malformed_quotes_are_rejected_without_crashing(bad):
    """Every one of these is something a fuzzer or a broken client will send."""
    with pytest.raises(VoraError) as exc:
        quotes.verify_quote(bad)
    assert exc.value.code in (ErrorCode.QUOTE_INVALID, ErrorCode.QUOTE_EXPIRED)


def test_an_expired_quote_is_rejected(monkeypatch):
    quote_id, _ = mint()
    # Capture the real clock first. Patching `time.time` with a lambda that
    # calls `time.time()` recurses into the patch.
    later = time.time() + quotes.QUOTE_TTL_S + 1
    monkeypatch.setattr(time, "time", lambda: later)
    with pytest.raises(VoraError) as exc:
        quotes.verify_quote(quote_id)
    assert exc.value.code is ErrorCode.QUOTE_EXPIRED


def test_each_quote_gets_a_distinct_jti():
    """Single-use enforcement keys on the jti, so a repeat would let one quote
    create two rides."""
    seen = {mint()[1].jti for _ in range(50)}
    assert len(seen) == 50


def test_mode_and_seats_survive_the_round_trip():
    """Ride creation reads these from the quote, not from the request body."""
    quote_id, _ = mint(mode=RideMode.CORRIDOR, seats=3)
    verified = quotes.verify_quote(quote_id)
    assert verified.mode == "corridor"
    assert verified.seats == 3


def test_labels_are_length_capped():
    """The label is user-supplied text that ends up on a ride and in a payload."""
    quote_id, _ = mint(pickup_label="x" * 5_000)
    assert len(quotes.verify_quote(quote_id).pickup_label) <= 160


def test_routing_source_is_carried_so_the_client_can_say_it_is_an_estimate():
    quote_id, _ = mint(routing_source="haversine_fallback")
    assert quotes.verify_quote(quote_id).routing_source == "haversine_fallback"
