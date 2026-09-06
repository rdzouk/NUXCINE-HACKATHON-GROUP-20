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
    extra = _http_routes(app) - EXPECTED_ROUTES
    assert not extra, f"undeclared routes present: {sorted(extra)}"


@pytest.mark.parametrize(
    "path",
    [
        f"{API}/ws/driver",
        f"{API}/ws/passenger",
        f"{API}/ws/share/sometokenvalue123456",
    ],
)
def test_websocket_routes_accept_and_report_not_implemented(client, path):
    """Behavioural, not structural.

    A connect that succeeds and closes with a readable reason proves more than
    a route-table lookup: it is what the mobile client will actually see, and
    it distinguishes 'not built yet' from 'the network is down'.
    """
    with client.websocket_connect(path) as socket:
        frame = socket.receive_json()
        assert frame["type"] == "error"
        assert frame["code"] == "NOT_IMPLEMENTED"
        assert frame["planned_phase"].startswith("Phase")


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


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", f"{API}/rides/00000000-0000-0000-0000-000000000000"),
        ("GET", f"{API}/places/search?q=warda"),
        ("GET", f"{API}/vehicles/capabilities"),
    ],
)
def test_stubs_return_the_contract_envelope(client, method, path):
    response = client.request(method, path)
    assert response.status_code == 501
    body = response.json()
    assert set(body) == {"error"}
    error = body["error"]
    assert set(error) == {"code", "message", "details", "request_id"}
    assert error["code"] == "NOT_IMPLEMENTED"
    assert error["message"], "message must not be empty"
    assert error["request_id"], "request_id must not be empty"


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
    response = client.get(
        f"{API}/vehicles/capabilities", headers={"X-Request-ID": supplied}
    )
    assert response.headers["x-request-id"] == supplied
    assert response.json()["error"]["request_id"] == supplied


def test_malicious_request_id_is_replaced(client):
    """An arbitrary client string must never reach the structured logs."""
    forged = 'evil-not-a-uuid{"level":"info"}'
    response = client.get(
        f"{API}/vehicles/capabilities", headers={"X-Request-ID": forged}
    )
    assert response.headers["x-request-id"] != forged
    assert len(response.headers["x-request-id"]) == 36


def test_error_response_never_leaks_a_phone_number(client):
    """I3 smoke test. Widened in Phase 3 to cover populated ride payloads."""
    response = client.post(
        f"{API}/auth/otp/request", json={"phone": "+237600000001"}
    )
    assert "+237600000001" not in response.text


def test_french_is_the_default_language(client):
    response = client.get(f"{API}/vehicles/capabilities")
    assert response.json()["error"]["message"] == (
        "Cette fonctionnalite n'est pas encore disponible."
    )


def test_english_is_served_on_request(client):
    response = client.get(
        f"{API}/vehicles/capabilities", headers={"Accept-Language": "en-GB,en;q=0.9"}
    )
    assert response.json()["error"]["message"] == "This feature is not available yet."


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
