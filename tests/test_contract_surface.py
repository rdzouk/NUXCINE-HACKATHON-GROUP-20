"""Contract surface tests.

These exist in Phase 0 rather than Phase 7 because their job is to catch a
later phase silently changing a response shape while a mobile client is built
against it. A contract nobody checks is a comment.
"""

from __future__ import annotations

import pytest

from app.errors.codes import DEFAULT_STATUS, ErrorCode

API = "/api/v1"

# The complete §6 surface. A route removed or renamed fails here.
EXPECTED_ROUTES: set[tuple[str, str]] = {
    ("GET", f"{API}/health"),
    ("POST", f"{API}/auth/otp/request"),
    ("POST", f"{API}/auth/otp/verify"),
    ("POST", f"{API}/auth/refresh"),
    ("POST", f"{API}/auth/logout"),
    ("GET", f"{API}/me"),
    ("PATCH", f"{API}/me"),
    ("GET", f"{API}/me/balance"),
    ("GET", f"{API}/places/search"),
    ("GET", f"{API}/places/reverse"),
    ("POST", f"{API}/rides/quote"),
    ("POST", f"{API}/rides"),
    ("GET", f"{API}/rides"),
    ("GET", f"{API}/rides/{{ride_id}}"),
    ("POST", f"{API}/rides/{{ride_id}}/cancel"),
    ("POST", f"{API}/rides/{{ride_id}}/share"),
    ("DELETE", f"{API}/rides/{{ride_id}}/share"),
    ("POST", f"{API}/rides/{{ride_id}}/messages"),
    ("POST", f"{API}/rides/{{ride_id}}/sos"),
    ("POST", f"{API}/rides/{{ride_id}}/report"),
    ("POST", f"{API}/rides/{{ride_id}}/arrived"),
    ("POST", f"{API}/rides/{{ride_id}}/start"),
    ("POST", f"{API}/rides/{{ride_id}}/complete"),
    ("POST", f"{API}/driver/online"),
    ("POST", f"{API}/driver/offline"),
    ("GET", f"{API}/driver/kyc"),
    ("GET", f"{API}/driver/offers"),
    ("POST", f"{API}/driver/offers/{{offer_id}}/accept"),
    ("POST", f"{API}/driver/offers/{{offer_id}}/decline"),
    ("GET", f"{API}/vehicles/capabilities"),
    # What a passenger may ask for on a ride, plus the text a driver signs
    # before being offered one. Needs, never diagnoses (I9).
    ("GET", f"{API}/ride-needs"),
    ("GET", f"{API}/share/{{token}}"),
    # Added at Phase 1. Not in the original §6 list: deliverable 5 requires
    # document upload and an admin approval step, and §6 specified neither.
    # Flagged in docs/CONTRACT_DECISIONS.md rather than added silently.
    ("POST", f"{API}/driver/kyc/documents"),
    ("GET", f"{API}/admin/drivers"),
    ("POST", f"{API}/admin/drivers/{{driver_id}}/kyc"),
}



def _http_routes(app) -> set[tuple[str, str]]:
    """Read the surface from the generated OpenAPI document.

    Deliberately not app.routes: FastAPI nests included routers behind an
    internal wrapper, and walking that is a private API that will break. The
    OpenAPI document is what mobile actually consumes, so asserting against it
    tests the thing that matters.
    """
    return {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method.upper() not in {"HEAD", "OPTIONS"}
    }


def test_every_contract_route_exists(app):
    missing = EXPECTED_ROUTES - _http_routes(app)
    assert not missing, f"routes missing from the API: {sorted(missing)}"


def test_no_undeclared_routes(app):
    """An added route is a contract change and has to be declared here."""
    from app.api.v1 import dev

    expected = set(EXPECTED_ROUTES)
    if dev.is_enabled():
        # Development-only, and not registered at all in production. That this
        # set changes with the environment is the point: an endpoint which
        # fabricates GPS positions for arbitrary rides must not exist on a real
        # deployment, so it is absent from the route table rather than guarded
        # inside each handler.
        expected |= {
            ("POST", f"{API}/dev/simulate-driver"),
            ("GET", f"{API}/dev/realtime-stats"),
            # Reads back the last OTP the console sender delivered, so a demo
            # does not stop while somebody greps the container logs. On the dev
            # router for the same reason as the simulator: the path does not
            # exist unless DEBUG is on outside production.
            ("GET", f"{API}/dev/otp/{{phone}}"),
        }

    extra = _http_routes(app) - expected
    assert not extra, f"undeclared routes present: {sorted(extra)}"


@pytest.mark.parametrize(
    "app_env,debug,enabled",
    [
        ("development", True, True),
        ("development", False, False),
        # Both of these would be enabled if the gate were DEBUG alone.
        ("production", True, False),
        ("prod", True, False),
    ],
)
def test_dev_routes_need_both_conditions(monkeypatch, app_env, debug, enabled):
    """The gate is DEBUG *and* not-production, never either alone.

    A single condition would be one typo away from exposing an endpoint that
    fabricates GPS positions for arbitrary rides on a real deployment.
    """
    from app.api.v1 import dev
    from app.config import settings

    monkeypatch.setattr(settings, "app_env", app_env)
    monkeypatch.setattr(settings, "debug", debug)
    assert dev.is_enabled() is enabled


def test_share_socket_refuses_a_bad_token(client):
    """A forged, expired or revoked link is answered alike.

    Distinguishing them would tell somebody working through forwarded links
    which ones were ever real. The socket says no and closes rather than
    hanging, so a viewer sees an error instead of an empty map.
    """
    with client.websocket_connect(f"{API}/ws/share/sometokenvalue123456") as socket:
        frame = socket.receive_json()
        assert frame["type"] == "error"
        assert frame["code"] == "SHARE_TOKEN_INVALID"
        assert "NOT_IMPLEMENTED" not in frame["code"]


@pytest.mark.parametrize("path", [f"{API}/ws/driver", f"{API}/ws/passenger"])
def test_live_sockets_refuse_an_unauthenticated_client(client, path):
    """The socket is accepted, then closed with a readable reason.

    Accepting before authenticating is deliberate: rejecting the handshake
    gives a browser no way to tell an expired token from a network failure,
    and a client that cannot distinguish those either retries forever or gives
    up on something recoverable.
    """
    with client.websocket_connect(path) as socket:
        socket.send_json({"type": "location", "lat": 3.8, "lng": 11.5})
        frame = socket.receive_json()
        assert frame["type"] == "error"
        assert frame["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize("path", [f"{API}/ws/driver", f"{API}/ws/passenger"])
def test_live_sockets_reject_a_forged_token(client, path):
    with client.websocket_connect(path) as socket:
        socket.send_json({"type": "auth", "token": "not.a.real.jwt"})
        frame = socket.receive_json()
        assert frame["type"] == "error"
        assert frame["code"] in ("INVALID_TOKEN", "TOKEN_EXPIRED")


def test_every_error_code_has_a_status():
    """A code with no status would crash VoraError at raise time."""
    missing = [c.value for c in ErrorCode if c not in DEFAULT_STATUS]
    assert not missing, f"ErrorCode entries with no DEFAULT_STATUS: {missing}"


def test_every_error_code_has_messages_in_both_languages():
    from app.i18n.en import MESSAGES as EN
    from app.i18n.fr import MESSAGES as FR

    missing_fr = [c.value for c in ErrorCode if c not in FR]
    missing_en = [c.value for c in ErrorCode if c not in EN]
    assert not missing_fr, f"no French message for: {missing_fr}"
    assert not missing_en, f"no English message for: {missing_en}"


def test_the_error_envelope_has_exactly_the_contract_shape(client):
    """Every error, whatever produced it, is the same four keys.

    Uses an unauthenticated request rather than a stub endpoint. Phase 6
    implemented the last 501, and pinning envelope behaviour to whichever route
    happens to be unfinished means the test dies the moment it is finished.
    An unauthenticated call to a protected route stays an error forever.
    """
    response = client.get(f"{API}/me")
    assert response.status_code == 401
    body = response.json()
    assert set(body) == {"error"}
    error = body["error"]
    assert set(error) == {"code", "message", "details", "request_id"}
    assert error["code"] == "UNAUTHENTICATED"
    assert error["message"], "message must not be empty"
    assert error["request_id"], "request_id must not be empty"


def test_no_route_in_the_contract_is_still_a_stub(client):
    """§6 is fully implemented as of Phase 6.

    A 501 reaching the jury is a feature that was promised in the contract and
    is not there, which is worse than one that was never listed.
    """
    schema = client.get("/openapi.json").json()
    stubs = []
    for path, methods in schema["paths"].items():
        for method in methods:
            if method not in ("get", "post", "patch", "put", "delete"):
                continue
            response = client.request(method.upper(), path)
            if response.status_code == 501:
                stubs.append(f"{method.upper()} {path}")
    assert not stubs, f"still returning 501: {stubs}"


def test_schema_failure_is_400_not_422(client):
    """§6 assigns 400 to schema failure and reserves 422 for semantic failure.

    FastAPI's default is 422 for both, which would make 'bad JSON' and
    'dropoff outside Yaounde' indistinguishable to the client.
    """
    response = client.post(f"{API}/auth/otp/request", json={"phone": "not-a-phone"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_unknown_route_returns_an_envelope(client):
    response = client.get(f"{API}/does-not-exist")
    assert response.status_code == 404
    assert set(response.json()["error"]) == {
        "code",
        "message",
        "details",
        "request_id",
    }


def test_security_headers_present(client):
    response = client.get(f"{API}/vehicles/capabilities")
    for header in (
        "x-content-type-options",
        "x-frame-options",
        "content-security-policy",
        "strict-transport-security",
        "referrer-policy",
        "x-request-id",
    ):
        assert header in response.headers, f"{header} missing"
    assert response.headers["x-frame-options"] == "DENY"


def test_request_id_is_echoed_when_valid(client):
    supplied = "11111111-2222-3333-4444-555555555555"
    response = client.get(f"{API}/me", headers={"X-Request-ID": supplied})
    assert response.headers["x-request-id"] == supplied
    assert response.json()["error"]["request_id"] == supplied


def test_malicious_request_id_is_replaced(client):
    """An arbitrary client string must never reach the structured logs."""
    forged = 'evil-not-a-uuid{"level":"info"}'
    response = client.get(f"{API}/me", headers={"X-Request-ID": forged})
    assert response.headers["x-request-id"] != forged
    assert len(response.headers["x-request-id"]) == 36


def test_error_response_never_leaks_a_phone_number(client):
    """I3 smoke test. Widened in Phase 3 to cover populated ride payloads."""
    response = client.post(
        f"{API}/auth/otp/request", json={"phone": "+237600000001"}
    )
    assert "+237600000001" not in response.text


def test_french_is_the_default_language(client):
    response = client.get(f"{API}/me")
    assert response.json()["error"]["message"] == "Authentification requise."


def test_english_is_served_on_request(client):
    response = client.get(
        f"{API}/me", headers={"Accept-Language": "en-GB,en;q=0.9"}
    )
    assert response.json()["error"]["message"] == "Authentication required."


def test_the_capability_vocabulary_is_served(client):
    """Phase 6. The client's accessibility filter is populated from the server,
    so a wording fix does not need an app release."""
    response = client.get(f"{API}/vehicles/capabilities")
    assert response.status_code == 200
    capabilities = response.json()["capabilities"]
    assert {c["key"] for c in capabilities} == {
        "ramp", "boot_space", "front_seat", "driver_assist", "guide_animal",
        "extra_legroom",
    }
    for capability in capabilities:
        assert capability["label_fr"] and capability["label_en"]


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", f"{API}/me"),
        ("PATCH", f"{API}/me"),
        ("GET", f"{API}/me/balance"),
        ("POST", f"{API}/driver/online"),
        ("POST", f"{API}/driver/offline"),
        ("GET", f"{API}/driver/kyc"),
        ("POST", f"{API}/driver/kyc/documents"),
        ("GET", f"{API}/admin/drivers"),
    ],
)
def test_protected_routes_reject_anonymous_callers(client, method, path):
    """Every authenticated route must refuse an anonymous caller.

    Parameterised over the route list rather than spot-checked, because the
    failure mode is a single route that forgot its dependency, and a spot check
    is exactly what misses that one.
    """
    response = client.request(method, path, json={})
    assert response.status_code == 401, f"{method} {path} did not require auth"
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_garbage_bearer_token_is_rejected(client):
    response = client.get(f"{API}/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"
