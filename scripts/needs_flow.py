#!/usr/bin/env python3
"""Prove a ride need survives the whole journey from picker to driver screen.

    python3 scripts/needs_flow.py

The chain has five links and had a break in the middle of it: the picker
collected needs, the booking screen carried them, `POST /rides` ignored them,
the row never stored them and the driver component read a field that was never
serialised. Every individual piece looked finished, and the feature did
nothing. So this walks the whole thing rather than any one part.

It also checks the boundary that matters legally. A need is an action the
driver takes, never a fact about the passenger, so what the driver receives
must be an instruction and must carry no reason (I9, Law 2024/017).

Standard library only, so it runs without the virtualenv.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid


def _base_from_argv() -> str:
    """Accept `--base URL` like every other harness, or a bare URL."""
    if "--base" in sys.argv:
        return sys.argv[sys.argv.index("--base") + 1]
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        return sys.argv[1]
    return "http://localhost:8080/api/v1"


BASE = _base_from_argv()

DRIVER = "+237600000009000"

LIVE_STATUSES = {
    "requested", "matching", "accepted", "arriving", "arrived", "in_progress",
}

# Two needs with different shapes: one that also implies a vehicle capability,
# one that is purely something the driver says. Plus the free-text case.
NEEDS = ["extra_legroom", "spoken_itinerary", "other"]
NOTE = "Je voyage avec un bagage encombrant."

PICKUP = {"lat": 3.87664, "lng": 11.51303, "label": "Carrefour Warda"}
DROPOFF = {"lat": 3.86600, "lng": 11.51700, "label": "Marche Central"}

GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"
RESET = "\033[0m"

failures: list[str] = []


def call(method, path, body=None, token=None, headers=None):
    url = f"{BASE}{path}"
    if not url.startswith(("http://", "https://")):
        raise SystemExit(f"base URL must be http or https, got {BASE!r}")

    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)  # noqa: S310 - scheme checked above
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for key, value in (headers or {}).items():
        req.add_header(key, value)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310 - scheme checked above
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"null")


def reset_limits() -> None:
    """Clear the OTP resend window so a rerun is not refused.

    A 60-second resend delay is correct in production and only gets in the way
    of a harness that logs the same two accounts in repeatedly. Clearing the
    buckets is honest about what it is; weakening the limit would not be.
    """
    subprocess.run(
        ["docker", "compose", "exec", "-T", "redis", "sh", "-c",
         "redis-cli --scan --pattern 'rl:*' | xargs -r redis-cli DEL"],
        capture_output=True, text=True, timeout=120, check=False,
    )


def login(phone: str) -> str:
    # The challenge id comes from the request, not from the dev endpoint. That
    # endpoint returns only the code, deliberately: it is a development
    # convenience, not a second way to authenticate.
    reset_limits()
    status, challenge = call("POST", "/auth/otp/request", {"phone": phone})
    if "challenge_id" not in challenge:
        raise SystemExit(f"OTP request for {phone} returned {status}: {challenge}")
    challenge_id = challenge["challenge_id"]
    _, payload = call("GET", f"/dev/otp/{urllib.parse.quote(phone, safe='')}")
    code = payload["code"]
    _, tokens = call(
        "POST", "/auth/otp/verify", {"challenge_id": challenge_id, "code": code}
    )
    return tokens["access_token"]


def check(label: str, ok: bool, detail: str = "") -> None:
    mark = f"{GREEN}pass{RESET}" if ok else f"{RED}FAIL{RESET}"
    print(f"  {mark}  {label}")
    if detail:
        print(f"{DIM}        {detail}{RESET}")
    if not ok:
        failures.append(label)


def main() -> int:
    print("ride needs, picker to driver screen\n")

    # ------------------------------------------------------- vocabulary --
    status, catalogue = call("GET", "/ride-needs")
    keys = {n["key"] for n in catalogue.get("needs", [])}
    check("GET /ride-needs serves the vocabulary", status == 200 and len(keys) >= 7,
          f"{len(keys)} needs, undertakings version {catalogue.get('undertakings_version')}")
    check("every need carries a driver instruction, not a label alone",
          all(n.get("driver_action_fr") and n.get("driver_action_en")
              for n in catalogue.get("needs", [])))

    # ----------------------------------------------------------- driver --
    # Online before the booking, not after. Matching wave 1 fires the moment
    # the ride is created, so a driver who appears afterwards is not in the
    # candidate set and waits for a wave that has already gone out.
    driver = login(DRIVER)

    # The fleet is seeded, so this driver is shared with every other harness
    # and may still be on a ride from one. A partial unique index allows one
    # live ride per driver, so a leftover blocks this run.
    _, driver_rides = call("GET", "/rides?limit=10", token=driver)
    for prior in driver_rides.get("items", []):
        if prior["status"] in LIVE_STATUSES:
            call("POST", f"/rides/{prior['id']}/cancel",
                 {"reason": "other"}, token=driver)

    call("POST", "/driver/online",
         {"lat": PICKUP["lat"], "lng": PICKUP["lng"], "seats_free": 4},
         token=driver)

    # ---------------------------------------------------------- booking --
    # A fresh passenger per run, not the seeded one.
    #
    # The first version reused a seeded account and cleared its leftover ride
    # by cancelling it. That charged a cancellation fee, exactly as designed,
    # and the resulting debt then blocked the booking this suite exists to
    # make. The policy was right and the harness was wrong: a test that has to
    # defeat an anti-abuse rule to run is testing the wrong thing.
    passenger_phone = f"+23760000000{uuid.uuid4().int % 10000:04d}"
    passenger = login(passenger_phone)

    status, quote = call("POST", "/rides/quote", {
        "pickup": PICKUP, "dropoff": DROPOFF, "mode": "exclusive", "seats": 1,
    }, token=passenger)
    if status != 200:
        print(f"{RED}quoting failed: {quote}{RESET}")
        return 1

    status, created = call(
        "POST", "/rides",
        {
            "quote_id": quote["quote_id"],
            "seats": 1,
            "ride_needs": NEEDS,
            "ride_needs_note": NOTE,
        },
        token=passenger,
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    if status not in (200, 201):
        print(f"{RED}booking failed: {created}{RESET}")
        return 1

    ride = created["ride"]
    ride_id = ride["id"]
    check("POST /rides stores what was asked for",
          sorted(ride.get("ride_needs", [])) == sorted(NEEDS),
          f"got {ride.get('ride_needs')}")
    check("the free-text note survives", ride.get("ride_needs_note") == NOTE)

    # ------------------------------------------------------- passenger --
    status, reread = call("GET", f"/rides/{ride_id}", token=passenger)
    check("GET /rides/{id} returns them to the passenger",
          sorted(reread["ride"].get("ride_needs", [])) == sorted(NEEDS))

    # ------------------------------------------------- what reaches them --
    status, offers = call("GET", "/driver/offers", token=driver)
    mine = [o for o in offers.get("offers", []) if o.get("ride_id") == ride_id]
    check("the ride reaches a driver as an offer", bool(mine),
          f"{len(offers.get('offers', []))} offer(s) waiting")

    if mine:
        # Before the decision. An offer that hides what is being asked turns
        # the undertakings into a promise a willing driver can break by
        # accident.
        check("the offer itself says what is being asked",
              sorted(mine[0].get("ride_needs", [])) == sorted(NEEDS),
              f"got {mine[0].get('ride_needs')}")

    if mine:
        offer_id = mine[0]["id"]
        status, accepted = call(
            "POST", f"/driver/offers/{offer_id}/accept", {}, token=driver
        )
        if status == 200:
            driver_view = accepted["ride"]
            check("the driver receives the needs",
                  sorted(driver_view.get("ride_needs", [])) == sorted(NEEDS),
                  f"got {driver_view.get('ride_needs')}")
            check("the driver does NOT receive the PIN",
                  driver_view.get("pin") is None)
            # The whole point of the model. There is no field that could carry
            # a reason, because none was ever collected.
            check("nothing in the driver's view says why",
                  not any(k in driver_view for k in
                          ("disability", "condition", "health", "diagnosis")))

            # Drive it to completion rather than leaving it live.
            #
            # A harness that stops mid-ride leaves the shared seeded driver
            # holding a live ride, and the next run of anything is blocked by
            # the one-live-ride index. Finishing also checks the needs survive
            # every transition, not only the accept.
            pin = reread["ride"].get("pin")
            call("POST", f"/rides/{ride_id}/arrived", {}, token=driver)
            call("POST", f"/rides/{ride_id}/start", {"pin": pin}, token=driver)
            status, done = call("POST", f"/rides/{ride_id}/complete", {},
                                token=driver)
            finished = done.get("ride", {}) if status == 200 else {}
            check("they survive to the completed ride",
                  sorted(finished.get("ride_needs", [])) == sorted(NEEDS),
                  f"status {finished.get('status')}")
        else:
            check("driver accepts the offer", False, str(accepted))

    print()
    if failures:
        print(f"{RED}{len(failures)} check(s) failed{RESET}")
        return 1
    print(f"{GREEN}the chain holds end to end{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
