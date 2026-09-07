#!/usr/bin/env python3
"""Trust and safety check. Phase 5 acceptance, alongside cancel_matrix.py.

    python scripts/safety_smoke.py

Covers share links, SOS, incident reports and canned messages. The assertions
that matter are the negative ones: what the public share view does *not*
contain, and what the message endpoint refuses to accept.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import uuid

import httpx

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"
ANSI = re.compile(r"\x1b\[[0-9;]*m")

WARDA = {"lat": 3.8760, "lng": 11.5120, "label": "Carrefour Warda"}
CENTRAL = {"lat": 3.8660, "lng": 11.5170, "label": "Marche Central"}

_passed = 0
_failed = 0


def check(label: str, condition: bool, detail: str = "") -> bool:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"{GREEN}  PASS{RESET}  {label}")
    else:
        _failed += 1
        print(f"{RED}  FAIL{RESET}  {label}")
        if detail:
            print(f"{DIM}        {detail}{RESET}")
    return condition


def psql(sql: str) -> str:
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "vora",
         "-d", "vora", "-tAc", sql],
        capture_output=True, text=True, timeout=120, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
    return lines[0] if lines else ""


def uid(value: str) -> str:
    return str(uuid.UUID(value))


def reset_limits() -> None:
    subprocess.run(
        ["docker", "compose", "exec", "-T", "redis", "sh", "-c",
         "redis-cli --scan --pattern 'rl:*' | xargs -r redis-cli DEL"],
        capture_output=True, text=True, timeout=120, check=False,
    )


def latest_code() -> str | None:
    result = subprocess.run(
        ["docker", "compose", "logs", "--tail", "400", "api"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    codes = []
    for line in result.stdout.splitlines():
        clean = ANSI.sub("", line)
        if "otp_console_delivery" in clean:
            m = re.search(r'code["\']?\s*[:=]\s*["\']?(\d{4})', clean)
            if m:
                codes.append(m.group(1))
    return codes[-1] if codes else None


def login(client: httpx.Client, base: str) -> tuple[str, str]:
    reset_limits()
    phone = f"+23760000000{uuid.uuid4().int % 10000:04d}"
    r = client.post(f"{base}/auth/otp/request", json={"phone": phone})
    r.raise_for_status()
    challenge_id = r.json()["challenge_id"]
    code = latest_code()
    if not code:
        raise RuntimeError("could not read the OTP from the api logs")
    r = client.post(
        f"{base}/auth/otp/verify",
        json={"challenge_id": challenge_id, "code": code},
    )
    r.raise_for_status()
    body = r.json()
    token, user_id = body["access_token"], body["user"]["id"]

    # Prove the token works before handing it back.
    #
    # `deps.py` answers INVALID_TOKEN for two unrelated situations: a token
    # that will not decode, and one that decodes to a user id no longer in the
    # database. Those want completely different investigations and the error
    # alone does not say which, so check here where the phone and the user id
    # are still in hand, and report both.
    probe = client.get(f"{base}/me", headers={"Authorization": f"Bearer {token}"})
    if probe.status_code != 200:
        still_there = psql(f"SELECT count(*) FROM users WHERE id = '{uid(user_id)}'")
        raise RuntimeError(
            f"a freshly minted token was refused: {probe.status_code} "
            f"{probe.text[:120]} (phone={phone}, user_id={user_id}, "
            f"row_still_in_db={still_there})"
        )

    return token, user_id


def make_driver(user_id: str) -> str:
    psql(f"UPDATE users SET role='driver' WHERE id='{uid(user_id)}'")
    driver_id = psql(
        f"INSERT INTO drivers (user_id, kyc_status, is_online, seats_free) "
        f"VALUES ('{uid(user_id)}', 'verified', true, 4) "
        f"ON CONFLICT (user_id) DO UPDATE SET is_online = true, "
        f"kyc_status = 'verified' RETURNING id"
    )
    psql(
        f"INSERT INTO vehicles (driver_id, plate, make, model, color, seats) "
        f"VALUES ('{uid(driver_id)}', 'CE 404 XY', 'Toyota', 'Corolla', "
        f"'blanc', 4)"
    )
    psql(
        f"INSERT INTO driver_presence (driver_id, geom, recorded_at) VALUES "
        f"('{uid(driver_id)}', "
        f"ST_MakePoint({WARDA['lng']}, {WARDA['lat']})::geography, now())"
    )
    return driver_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8080/api/v1")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    client = httpx.Client(timeout=90.0)
    print(f"VORA safety smoke against {base}\n")

    print("setup")
    p_token, _ = login(client, base)
    d_token, d_user = login(client, base)
    stranger_token, _ = login(client, base)
    make_driver(d_user)

    passenger = {"Authorization": f"Bearer {p_token}"}
    driver = {"Authorization": f"Bearer {d_token}"}
    stranger = {"Authorization": f"Bearer {stranger_token}"}

    q = client.post(
        f"{base}/rides/quote", headers=passenger,
        json={"pickup": WARDA, "dropoff": CENTRAL, "seats": 1, "mode": "exclusive"},
    )
    # Checked rather than parsed straight through.
    #
    # A bare q.json()["quote_id"] raises KeyError when the quote fails, and a
    # KeyError in the setup of a safety suite sends somebody reading the share
    # and SOS code looking for a bug that is really a 504 from a loaded box.
    # The status is what says which.
    if not check("setup: quote returned 200", q.status_code == 200,
                 f"got {q.status_code}: {q.text[:200]}"):
        return summarise()

    r = client.post(
        f"{base}/rides", headers={**passenger, "Idempotency-Key": str(uuid.uuid4())},
        json={"quote_id": q.json()["quote_id"], "seats": 1,
              "accessibility_required": []},
    )
    if not check("ride created", r.status_code == 201, f"got {r.status_code}"):
        return summarise()
    ride_id = r.json()["ride"]["id"]

    offers = client.get(f"{base}/driver/offers", headers=driver).json()["offers"]
    mine = [o for o in offers if o["ride_id"] == ride_id]
    if not check("driver got the offer", bool(mine)):
        return summarise()
    client.post(f"{base}/driver/offers/{mine[0]['id']}/accept", headers=driver)

    # A position to show on the share view.
    psql(
        f"INSERT INTO ride_traces (ride_id, seq, geom, recorded_at, rejected) "
        f"VALUES ('{uid(ride_id)}', 0, "
        f"ST_MakePoint({WARDA['lng']}, {WARDA['lat']})::geography, now(), false)"
    )
    print()

    print("share link")
    share = client.post(f"{base}/rides/{ride_id}/share", headers=passenger)
    if not check("passenger can mint a link", share.status_code == 201,
                 f"got {share.status_code}: {share.text[:200]}"):
        return summarise()
    url = share.json()["url"]
    token = url.rsplit("/", 1)[-1]
    print(f"{DIM}  {url[:78]}...{RESET}")

    denied = client.post(f"{base}/rides/{ride_id}/share", headers=driver)
    check("a driver cannot share the passenger's trip", denied.status_code == 409,
          f"got {denied.status_code}")

    view = client.get(f"{base}/share/{token}")
    if not check("the link resolves without auth", view.status_code == 200,
                 f"got {view.status_code}: {view.text[:200]}"):
        return summarise()

    body = view.json()
    raw = view.text
    check("shows the driver's first name", bool(body.get("driver_first_name")))
    check("shows the vehicle plate", body["vehicle"]["plate"] == "CE 404 XY")
    check("shows the destination", body["dropoff_label"] == CENTRAL["label"])
    print()

    print("what the public view must NOT contain")
    check("no phone number", not re.search(r"\+237\d{6,}", raw))
    check("no fare", "fare" not in raw.lower())
    check("no PIN", "pin" not in raw.lower())
    check("no passenger identity", "passenger" not in raw.lower())
    check("no trace history", "trace" not in raw.lower())
    check("no ride id", ride_id not in raw,
          "the id would let a holder try it against authenticated routes")
    print()

    print("location precision")
    loc = body.get("current_location")
    if check("a position is shown", loc is not None):
        check("coarse before the trip starts", loc["precision"] == "coarse",
              f"got {loc['precision']}; a link shared while waiting would "
              f"reveal exactly where the passenger is standing")
        check("and it really is rounded",
              round(loc["lat"], 3) == loc["lat"],
              f"{loc['lat']} is not coarsened")

    client.post(f"{base}/rides/{ride_id}/arrived", headers=driver)
    pin = psql(f"SELECT pin FROM rides WHERE id='{uid(ride_id)}'")
    client.post(f"{base}/rides/{ride_id}/start", headers=driver, json={"pin": pin})

    moving = client.get(f"{base}/share/{token}").json()
    if moving.get("current_location"):
        check("precise once the trip is in progress",
              moving["current_location"]["precision"] == "precise",
              f"got {moving['current_location']['precision']}")
    print()

    print("revocation")
    revoke = client.delete(f"{base}/rides/{ride_id}/share", headers=passenger)
    check("passenger can revoke", revoke.status_code == 204,
          f"got {revoke.status_code}")

    dead = client.get(f"{base}/share/{token}")
    check("the revoked link stops working", dead.status_code == 404,
          f"got {dead.status_code}")
    check("and says only that it is invalid",
          dead.json()["error"]["code"].startswith("SHARE_TOKEN"),
          "distinguishing revoked from expired would leak which links were real")

    forged = client.get(f"{base}/share/{'x' * 40}")
    check("a forged token is refused", forged.status_code == 404,
          f"got {forged.status_code}")
    print()

    print("canned messages")
    msg = client.post(
        f"{base}/rides/{ride_id}/messages", headers=passenger,
        json={"template_key": "at_gate"},
    )
    if check("passenger can send a template", msg.status_code == 201,
             f"got {msg.status_code}: {msg.text[:200]}"):
        check("the server renders the text", bool(msg.json()["message"]["text"]))
        print(f"{DIM}  \"{msg.json()['message']['text']}\"{RESET}")

    free_text = client.post(
        f"{base}/rides/{ride_id}/messages", headers=passenger,
        json={"template_key": "appelle moi au 699000000"},
    )
    check("free text is refused", free_text.status_code == 400,
          f"got {free_text.status_code}; free text would reintroduce every "
          f"problem I3 exists to remove")

    outsider = client.post(
        f"{base}/rides/{ride_id}/messages", headers=stranger,
        json={"template_key": "at_gate"},
    )
    check("a stranger cannot message the ride", outsider.status_code == 404,
          f"got {outsider.status_code}")
    print()

    print("SOS")
    sos = client.post(f"{base}/rides/{ride_id}/sos", headers=passenger)
    if not check("SOS is accepted", sos.status_code == 201,
                 f"got {sos.status_code}: {sos.text[:200]}"):
        return summarise()
    incident_id = sos.json()["incident_id"]
    print(f"{DIM}  incident {incident_id}{RESET}")

    check("SOS takes no body",
          "description" not in sos.text,
          "somebody pressing this is not going to type")

    snapshot = psql(
        f"SELECT snapshot::text FROM incident_reports WHERE id='{uid(incident_id)}'"
    )
    check("a snapshot was sealed", len(snapshot) > 50, f"{len(snapshot)} chars")
    for field in ("sealed_at", "vehicle", "trace", "driver_id"):
        check(f"snapshot carries {field}", field in snapshot)

    is_sos = psql(
        f"SELECT is_sos FROM incident_reports WHERE id='{uid(incident_id)}'"
    )
    check("it is flagged as an SOS, not an ordinary report", is_sos == "t")

    # The seal has to be real, not a comment.
    try:
        psql(
            f"UPDATE incident_reports SET snapshot = '{{}}'::jsonb "
            f"WHERE id='{uid(incident_id)}'"
        )
        check("the snapshot is immutable", False,
              "the UPDATE succeeded; the evidence can be edited after the fact")
    except RuntimeError as exc:
        check("the snapshot is immutable (database trigger)",
              "sealed" in str(exc).lower(), str(exc)[:160])

    stranger_sos = client.post(f"{base}/rides/{ride_id}/sos", headers=stranger)
    check("a stranger cannot raise an SOS on somebody's ride",
          stranger_sos.status_code == 404, f"got {stranger_sos.status_code}")
    print()

    print("incident report")
    report = client.post(
        f"{base}/rides/{ride_id}/report", headers=passenger,
        json={"category": "vehicle_condition", "description": "Ceinture cassee"},
    )
    if check("a report is accepted", report.status_code == 201,
             f"got {report.status_code}: {report.text[:200]}"):
        rid = report.json()["incident_id"]
        cat = psql(
            f"SELECT category FROM incident_reports WHERE id='{uid(rid)}'"
        )
        check("the category is stored", cat == "vehicle_condition", cat)
        sealed = psql(
            f"SELECT snapshot::text FROM incident_reports WHERE id='{uid(rid)}'"
        )
        check("a report seals evidence too", "sealed_at" in sealed)

    events = int(psql(
        f"SELECT count(*) FROM ride_events WHERE ride_id='{uid(ride_id)}' "
        f"AND event_type IN ('sos_raised','incident_reported',"
        f"'share_link_created','share_links_revoked','message_sent')"
    ) or 0)
    check("every safety action is in the audit trail (I7)", events >= 5,
          f"only {events} events")

    return summarise()


def summarise() -> int:
    print("\n-----------------------------------------")
    print(f"passed: {_passed}   failed: {_failed}")
    if _failed:
        print(f"{RED}safety smoke FAILED{RESET}")
        return 1
    print(f"{GREEN}safety smoke passed{RESET}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"{RED}error: {exc}{RESET}", file=sys.stderr)
        raise SystemExit(2) from exc
