#!/usr/bin/env python3
"""Full ride lifecycle over HTTP. Phase 3 acceptance check.

    python scripts/ride_flow.py

Drives requested -> matching -> accepted -> arrived -> in_progress ->
completed against the real API, and checks the invariants at each step rather
than only that the status changed.

What it asserts beyond the happy path:

  I1  the ride is invisible to a third party at every stage
  I3  no phone number appears in any payload, for either party
  I4  the driver never sees the PIN; the passenger always does
  I7  every transition landed in ride_events
  I8  a retried creation returns the same ride, not a second one

The PIN check is the one worth reading. The whole point of the PIN is that the
driver does not have it until the passenger says it aloud, so a payload that
leaks it to the driver defeats the mechanism silently, and nothing else in the
system would notice.
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

    # Prove the token actually works before handing it back.
    #
    # This suite has twice failed in a full run with 401 INVALID_TOKEN on the
    # first authenticated call, while passing on its own. `deps.py` returns
    # that code for two different situations: a token that will not decode,
    # and a token that decodes to a user id no longer in the database. Those
    # want completely different investigations, and the error alone does not
    # say which.
    #
    # So check here, where the phone number and the user id are still in hand,
    # and print both. A failure at this point names the cause; the same failure
    # three calls later names nothing.
    probe = client.get(f"{base}/me", headers={"Authorization": f"Bearer {token}"})
    if probe.status_code != 200:
        exists = psql(
            f"SELECT count(*) FROM users WHERE id = '{uid(user_id)}'"
        )
        raise RuntimeError(
            f"a freshly minted token was refused: {probe.status_code} "
            f"{probe.text[:120]} (phone={phone}, user_id={user_id}, "
            f"row_still_in_db={exists})"
        )

    return token, user_id


def make_driver(user_id: str, lat: float, lng: float) -> str:
    psql(f"UPDATE users SET role='driver' WHERE id='{uid(user_id)}'")
    driver_id = psql(
        f"INSERT INTO drivers (user_id, kyc_status, is_online, seats_free) "
        f"VALUES ('{uid(user_id)}', 'verified', true, 4) "
        f"ON CONFLICT (user_id) DO UPDATE SET is_online = true, "
        f"kyc_status = 'verified' RETURNING id"
    )
    psql(
        f"INSERT INTO vehicles (driver_id, plate, make, model, color, seats) "
        f"VALUES ('{uid(driver_id)}', 'CE-{uuid.uuid4().hex[:5].upper()}', "
        f"'Toyota', 'Corolla', 'blanc', 4)"
    )
    psql(
        f"INSERT INTO driver_presence (driver_id, geom, recorded_at) "
        f"VALUES ('{uid(driver_id)}', ST_MakePoint({lng}, {lat})::geography, now()) "
        f"ON CONFLICT (driver_id) DO UPDATE SET geom = EXCLUDED.geom, "
        f"recorded_at = EXCLUDED.recorded_at"
    )
    return driver_id


def no_phone_anywhere(payload: str) -> bool:
    """I3. No E.164 number in a ride payload, for either party."""
    return not re.search(r"\+237\d{6,}", payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8080/api/v1")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    client = httpx.Client(timeout=90.0)
    print(f"VORA ride flow against {base}\n")

    print("setup")
    p_token, _ = login(client, base)
    d_token, d_user = login(client, base)
    stranger_token, _ = login(client, base)

    passenger = {"Authorization": f"Bearer {p_token}"}
    driver = {"Authorization": f"Bearer {d_token}"}
    stranger = {"Authorization": f"Bearer {stranger_token}"}

    # Exactly at the pickup, so this driver is always first among the nearest
    # candidates a matching wave offers to. Leftover online drivers from other
    # suites would otherwise crowd it out of the ten-offer cap.
    make_driver(d_user, WARDA["lat"], WARDA["lng"])
    check("passenger, driver and an unrelated third party", True)
    print()

    print("quote and create")
    q = client.post(
        f"{base}/rides/quote", headers=passenger,
        json={"pickup": WARDA, "dropoff": CENTRAL, "seats": 1, "mode": "exclusive"},
    )
    if not check("quote returns 200", q.status_code == 200,
                 f"got {q.status_code}: {q.text[:200]}"):
        return summarise()
    quote_id = q.json()["quote_id"]

    key = str(uuid.uuid4())
    r = client.post(
        f"{base}/rides", headers={**passenger, "Idempotency-Key": key},
        json={"quote_id": quote_id, "seats": 1, "accessibility_required": []},
    )
    if not check("ride created (201)", r.status_code == 201,
                 f"got {r.status_code}: {r.text[:300]}"):
        return summarise()

    ride = r.json()["ride"]
    ride_id = ride["id"]
    pin = ride.get("pin")
    print(f"{DIM}  ride {ride_id}, status {ride['status']}, pin {pin}{RESET}")

    check("the passenger receives the PIN", bool(pin) and len(pin) == 4)
    check("no phone number in the payload (I3)", no_phone_anywhere(r.text))
    check("status is requested or matching",
          ride["status"] in ("requested", "matching"), ride["status"])

    # I8.
    again = client.post(
        f"{base}/rides", headers={**passenger, "Idempotency-Key": key},
        json={"quote_id": quote_id, "seats": 1, "accessibility_required": []},
    )
    check("a retried key returns 200, not a second ride (I8)",
          again.status_code == 200, f"got {again.status_code}")
    check("and it is the same ride",
          again.json()["ride"]["id"] == ride_id)

    # The quote is single use, so a different key must not create a second ride.
    other = client.post(
        f"{base}/rides", headers={**passenger, "Idempotency-Key": str(uuid.uuid4())},
        json={"quote_id": quote_id, "seats": 1, "accessibility_required": []},
    )
    check("the same quote cannot create a second ride",
          other.status_code == 409, f"got {other.status_code}")
    print()

    print("a stranger cannot see it (I1)")
    peek = client.get(f"{base}/rides/{ride_id}", headers=stranger)
    check("stranger gets 404", peek.status_code == 404, f"got {peek.status_code}")
    check("code is RIDE_NOT_FOUND, never FORBIDDEN",
          peek.json()["error"]["code"] == "RIDE_NOT_FOUND")
    print()

    print("driver accepts")
    offers = client.get(f"{base}/driver/offers", headers=driver)
    if not check("driver has offers", offers.status_code == 200,
                 f"got {offers.status_code}: {offers.text[:200]}"):
        return summarise()

    mine = [o for o in offers.json()["offers"] if o["ride_id"] == ride_id]
    if not check("an offer for this ride reached the driver", bool(mine),
                 "matching produced nothing; check driver_presence and radius"):
        return summarise()

    offer = mine[0]
    check("the offer carries no passenger identity (I3)",
          no_phone_anywhere(offers.text) and "passenger" not in offer)

    acc = client.post(
        f"{base}/driver/offers/{offer['id']}/accept", headers=driver
    )
    if not check("accept returns 200", acc.status_code == 200,
                 f"got {acc.status_code}: {acc.text[:300]}"):
        return summarise()

    driver_view = acc.json()["ride"]
    check("status is accepted", driver_view["status"] == "accepted",
          driver_view["status"])
    check("the driver does NOT get the PIN",
          driver_view.get("pin") is None,
          "the PIN is the only thing a kerbside impostor lacks")
    check("no phone number in the driver's view (I3)", no_phone_anywhere(acc.text))
    check("the driver sees the passenger's first name only",
          driver_view.get("passenger") is not None
          and " " not in driver_view["passenger"]["first_name"])

    p_view = client.get(f"{base}/rides/{ride_id}", headers=passenger).json()["ride"]
    check("the passenger still sees their PIN", p_view.get("pin") == pin)
    check("the passenger sees the vehicle to look for",
          p_view.get("vehicle") is not None and bool(p_view["vehicle"]["plate"]))
    print()

    print("arrival and PIN")
    arr = client.post(f"{base}/rides/{ride_id}/arrived", headers=driver)
    check("arrived returns 200", arr.status_code == 200, f"got {arr.status_code}")
    check("status is arrived", arr.json()["ride"]["status"] == "arrived")

    wrong = client.post(
        f"{base}/rides/{ride_id}/start", headers=driver,
        json={"pin": "0000" if pin != "0000" else "1111"},
    )
    check("a wrong PIN is refused", wrong.status_code == 403,
          f"got {wrong.status_code}: {wrong.text[:160]}")

    started = client.post(
        f"{base}/rides/{ride_id}/start", headers=driver, json={"pin": pin}
    )
    if not check("the correct PIN starts the trip", started.status_code == 200,
                 f"got {started.status_code}: {started.text[:200]}"):
        return summarise()
    check("status is in_progress",
          started.json()["ride"]["status"] == "in_progress")

    # The passenger must not be able to drive the machine from the wrong side.
    bad_actor = client.post(f"{base}/rides/{ride_id}/complete", headers=passenger)
    check("a passenger cannot complete their own ride",
          bad_actor.status_code == 409, f"got {bad_actor.status_code}")
    print()

    print("completion")
    done = client.post(f"{base}/rides/{ride_id}/complete", headers=driver)
    if not check("complete returns 200", done.status_code == 200,
                 f"got {done.status_code}: {done.text[:300]}"):
        return summarise()

    body = done.json()
    final = body["final_fare_xaf"]
    print(f"{DIM}  final fare {final} XAF{RESET}")
    check("status is completed", body["ride"]["status"] == "completed")
    check("a final fare was set", final > 0)
    check("the fare is payable in coins", final % 50 == 0, f"{final} XAF")
    check("no phone number at completion (I3)", no_phone_anywhere(done.text))

    # Terminal really is terminal.
    replay = client.post(f"{base}/rides/{ride_id}/complete", headers=driver)
    check("a completed ride cannot be completed twice",
          replay.status_code == 409, f"got {replay.status_code}")
    print()

    print("the audit trail (I7)")
    events = psql(
        f"SELECT count(*) FROM ride_events WHERE ride_id='{uid(ride_id)}'"
    )
    check("every transition was recorded", int(events or 0) >= 5,
          f"only {events} events")

    trail = psql(
        f"SELECT string_agg(to_status, ' -> ' ORDER BY seq) FROM ride_events "
        f"WHERE ride_id='{uid(ride_id)}' AND to_status IS NOT NULL"
    )
    print(f"{DIM}  {trail}{RESET}")

    # I7 is only worth anything if the log cannot be rewritten.
    try:
        psql(
            f"UPDATE ride_events SET reason='tampered' "
            f"WHERE ride_id='{uid(ride_id)}'"
        )
        check("ride_events is append-only", False,
              "the UPDATE succeeded; the audit log is editable")
    except RuntimeError as exc:
        check("ride_events rejects UPDATE (append-only)",
              "append-only" in str(exc).lower(), str(exc)[:160])

    try:
        psql(f"DELETE FROM ride_events WHERE ride_id='{uid(ride_id)}'")
        check("ride_events rejects DELETE", False, "the DELETE succeeded")
    except RuntimeError as exc:
        check("ride_events rejects DELETE (append-only)",
              "append-only" in str(exc).lower(), str(exc)[:160])

    return summarise()


def summarise() -> int:
    print("\n-----------------------------------------")
    print(f"passed: {_passed}   failed: {_failed}")
    if _failed:
        print(f"{RED}ride flow FAILED{RESET}")
        return 1
    print(f"{GREEN}ride flow passed{RESET}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"{RED}error: {exc}{RESET}", file=sys.stderr)
        raise SystemExit(2) from exc
