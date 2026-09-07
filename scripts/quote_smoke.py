#!/usr/bin/env python3
"""Fare quoting check. Second half of the Phase 2 acceptance check.

    python scripts/quote_smoke.py

Checks that quotes are sane and, more importantly, that a client cannot make
the server accept a price it did not compute (I2).
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

_passed = 0
_failed = 0

# Carrefour Warda to Marche Central, then a longer cross-city leg.
WARDA = {"lat": 3.8760, "lng": 11.5120, "label": "Carrefour Warda"}
CENTRAL = {"lat": 3.8660, "lng": 11.5170, "label": "Marche Central"}
MVAN = {"lat": 3.8080, "lng": 11.5140, "label": "Mvan"}


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


def login(client: httpx.Client, base: str) -> str:
    subprocess.run(
        ["docker", "compose", "exec", "-T", "redis", "sh", "-c",
         "redis-cli --scan --pattern 'rl:*' | xargs -r redis-cli DEL"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    phone = f"+23760000000{uuid.uuid4().int % 10000:04d}"
    r = client.post(f"{base}/auth/otp/request", json={"phone": phone})
    r.raise_for_status()
    challenge_id = r.json()["challenge_id"]
    code = latest_code()
    if not code:
        raise RuntimeError("could not read the OTP from the api logs")
    r = client.post(
        f"{base}/auth/otp/verify", json={"challenge_id": challenge_id, "code": code}
    )
    r.raise_for_status()
    return r.json()["access_token"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8080/api/v1")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    client = httpx.Client(timeout=45.0)
    print(f"VORA quote smoke against {base}\n")

    print("setup")
    token = login(client, base)
    auth = {"Authorization": f"Bearer {token}"}
    check("logged in", bool(token))
    print()

    print("quote shape and sanity")
    r = client.post(
        f"{base}/rides/quote", headers=auth,
        json={"pickup": WARDA, "dropoff": CENTRAL, "seats": 1, "mode": "exclusive"},
    )
    if not check("returns 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"):
        return summarise()

    q = r.json()
    print(f"{DIM}  {q['distance_m']} m, {q['duration_s']} s, "
          f"exclusive {q['fare_xaf']} XAF, corridor {q['corridor_fare_xaf']} XAF, "
          f"via {q['routing_source']}{RESET}")

    check("carries a quote_id", bool(q.get("quote_id")))
    check("carries a route polyline", bool(q.get("route_polyline")))
    check("carries an expiry", bool(q.get("expires_at")))
    check("carries a fare breakdown", "breakdown" in q)
    check("reports the routing source", q.get("routing_source") in
          ("osrm", "haversine_fallback"),
          "the client needs this to say whether the estimate is approximate")

    fare = q["fare_xaf"]
    corridor = q["corridor_fare_xaf"]
    check("exclusive fare is payable in coins", fare % 50 == 0, f"{fare} XAF")
    check("corridor fare is payable in coins", corridor % 50 == 0, f"{corridor} XAF")
    check("corridor is cheaper than exclusive", corridor < fare,
          f"corridor {corridor} vs exclusive {fare}")
    check("fare is above the minimum", fare >= 500, f"{fare} XAF")
    check("fare is sane for a short urban trip", 500 <= fare <= 6000, f"{fare} XAF")
    print()

    print("a longer trip costs more")
    r2 = client.post(
        f"{base}/rides/quote", headers=auth,
        json={"pickup": WARDA, "dropoff": MVAN, "seats": 1, "mode": "exclusive"},
    )
    if check("returns 200", r2.status_code == 200, f"got {r2.status_code}"):
        q2 = r2.json()
        print(f"{DIM}  {q2['distance_m']} m -> {q2['fare_xaf']} XAF{RESET}")
        check("further is dearer", q2["fare_xaf"] > fare,
              f"{q2['fare_xaf']} vs {fare}")
        check("still payable in coins", q2["fare_xaf"] % 50 == 0)
    print()

    print("pricing is deterministic")
    r3 = client.post(
        f"{base}/rides/quote", headers=auth,
        json={"pickup": WARDA, "dropoff": CENTRAL, "seats": 1, "mode": "exclusive"},
    )
    check("the same trip prices identically", r3.json()["fare_xaf"] == fare,
          f"{r3.json().get('fare_xaf')} vs {fare}")
    check("but the quote_id differs", r3.json()["quote_id"] != q["quote_id"],
          "each quote needs its own jti or single-use enforcement breaks")
    print()

    print("service area is enforced")
    r4 = client.post(
        f"{base}/rides/quote", headers=auth,
        json={
            "pickup": WARDA,
            # Paris. Well outside the served region.
            "dropoff": {"lat": 48.8566, "lng": 2.3522, "label": "Paris"},
            "seats": 1, "mode": "exclusive",
        },
    )
    check("a dropoff outside the service area is refused", r4.status_code == 422,
          f"got {r4.status_code}: {r4.text[:160]}")
    if r4.status_code == 422:
        check("code is OUTSIDE_SERVICE_AREA",
              r4.json()["error"]["code"] == "OUTSIDE_SERVICE_AREA")

    r5 = client.post(
        f"{base}/rides/quote", headers=auth,
        json={
            "pickup": {"lat": 48.8566, "lng": 2.3522, "label": "Paris"},
            "dropoff": CENTRAL, "seats": 1, "mode": "exclusive",
        },
    )
    check("a pickup outside the service area is refused too", r5.status_code == 422,
          f"got {r5.status_code}")
    print()

    print("quoting requires authentication")
    r6 = client.post(
        f"{base}/rides/quote",
        json={"pickup": WARDA, "dropoff": CENTRAL, "seats": 1, "mode": "exclusive"},
    )
    check("anonymous quoting is refused", r6.status_code == 401, f"got {r6.status_code}")

    return summarise()


def summarise() -> int:
    print("\n-----------------------------------------")
    print(f"passed: {_passed}   failed: {_failed}")
    if _failed:
        print(f"{RED}quote smoke FAILED{RESET}")
        return 1
    print(f"{GREEN}quote smoke passed{RESET}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"{RED}error: {exc}{RESET}", file=sys.stderr)
        raise SystemExit(2) from exc
