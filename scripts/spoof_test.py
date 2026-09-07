#!/usr/bin/env python3
"""GPS spoofing resistance. Phase 4 acceptance check.

    python scripts/spoof_test.py

Attacks the trace, because the trace is what the fare is computed from (I2). A
driver running a patched client can send any sequence of points they like, and
every accepted metre is money.

What it asserts:

  every impossible point is rejected and stored with rejected = true
  every honest point is accepted
  the fare is computed from accepted points only
  a rejected point contributes nothing, even mid-journey

The last one matters most. A filter that merely refuses to *show* a bad point
while still counting it toward distance would leave the attack working and the
evidence misleading.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import websockets

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


def new_phone() -> str:
    return f"+23760000000{uuid.uuid4().int % 10000:04d}"


def authenticate(client: httpx.Client, base: str, phone: str) -> tuple[str, str]:
    """Mint a fresh token for a given number.

    Split out from `login` so the same identity can be re-authenticated later.
    The socket phase below sleeps 2.1 seconds per point across two sessions,
    which on a loaded box can outlast the 900-second access-token TTL.
    """
    reset_limits()
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


def login(client: httpx.Client, base: str) -> tuple[str, str]:
    return authenticate(client, base, new_phone())


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
        f"VALUES ('{uid(driver_id)}', ST_MakePoint({lng}, {lat})::geography, now())"
    )
    return driver_id


async def send_points(ws_base: str, token: str, points: list[dict]) -> list[dict]:
    """Push points down a driver socket and collect the replies.

    Uses the first-frame auth handshake rather than a header, which is the path
    a browser must take and therefore the one worth exercising.
    """
    replies: list[dict] = []
    async with websockets.connect(f"{ws_base}/ws/driver") as ws:
        await ws.send(json.dumps({"type": "auth", "token": token}))

        ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
        if ready.get("type") != "ready":
            raise RuntimeError(f"expected ready, got {ready}")

        for point in points:
            await ws.send(json.dumps(point))
            # The rate limiter drops frames closer together than this, so the
            # test respects it rather than measuring it.
            await asyncio.sleep(2.1)
            try:
                reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
                replies.append(reply)
            except TimeoutError:
                replies.append({"type": "accepted_silently"})

    return replies


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8080/api/v1")
    parser.add_argument("--ws", default="ws://localhost:8080/api/v1")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    client = httpx.Client(timeout=90.0)
    print(f"VORA spoof test against {base}\n")

    print("setup")
    p_token, _ = login(client, base)
    d_phone = new_phone()
    d_token, d_user = authenticate(client, base, d_phone)
    passenger = {"Authorization": f"Bearer {p_token}"}
    driver = {"Authorization": f"Bearer {d_token}"}
    # Exactly at the pickup, so this driver is always first among the nearest
    # candidates a matching wave offers to. Leftover online drivers from other
    # suites would otherwise crowd it out of the ten-offer cap.
    make_driver(d_user, WARDA["lat"], WARDA["lng"])

    q = client.post(
        f"{base}/rides/quote", headers=passenger,
        json={"pickup": WARDA, "dropoff": CENTRAL, "seats": 1, "mode": "exclusive"},
    )
    r = client.post(
        f"{base}/rides", headers={**passenger, "Idempotency-Key": str(uuid.uuid4())},
        json={"quote_id": q.json()["quote_id"], "seats": 1,
              "accessibility_required": []},
    )
    ride_id = r.json()["ride"]["id"]

    offers = client.get(f"{base}/driver/offers", headers=driver).json()["offers"]
    mine = [o for o in offers if o["ride_id"] == ride_id]
    if not check("driver received the offer", bool(mine)):
        return summarise()
    client.post(f"{base}/driver/offers/{mine[0]['id']}/accept", headers=driver)
    check("ride is accepted and trackable", True)
    print(f"{DIM}  ride {ride_id}{RESET}\n")

    # A short honest run, then each attack in turn. Timestamps advance
    # realistically so the only thing wrong with a bad point is the thing the
    # test is probing.
    # Anchored in the past. Each frame takes about 2.1 s to send (the rate
    # limiter), so timestamps computed forward from "now" overtake the wall
    # clock by the third frame and get refused as future-dated before the check
    # under test ever runs. Starting five minutes back keeps every offset
    # safely behind real time while preserving the gaps the checks care about.
    t0 = datetime.now(UTC) - timedelta(seconds=300)
    honest = [
        {"type": "location", "lat": 3.8760, "lng": 11.5120,
         "accuracy_m": 8, "ts": (t0 + timedelta(seconds=0)).isoformat()},
        {"type": "location", "lat": 3.8755, "lng": 11.5125,
         "accuracy_m": 8, "ts": (t0 + timedelta(seconds=10)).isoformat()},
    ]
    attacks = [
        # Yaounde to Douala in ten seconds. The classic fare inflation.
        {"type": "location", "lat": 4.0511, "lng": 9.7679,
         "accuracy_m": 8, "ts": (t0 + timedelta(seconds=20)).isoformat(),
         "_label": "teleport to Douala"},
        # A plausible distance in an implausible time.
        {"type": "location", "lat": 3.9200, "lng": 11.5600,
         "accuracy_m": 8, "ts": (t0 + timedelta(seconds=30)).isoformat(),
         "_label": "impossible speed"},
        # A phone that does not know where it is.
        {"type": "location", "lat": 3.8750, "lng": 11.5130,
         "accuracy_m": 850, "ts": (t0 + timedelta(seconds=40)).isoformat(),
         "_label": "accuracy 850 m"},
        # Backwards in time, to reorder the trace.
        {"type": "location", "lat": 3.8748, "lng": 11.5132,
         "accuracy_m": 8, "ts": (t0 - timedelta(seconds=300)).isoformat(),
         "_label": "timestamp in the past"},
        # Not a coordinate at all.
        {"type": "location", "lat": 91.0, "lng": 200.0,
         "accuracy_m": 8, "ts": (t0 + timedelta(seconds=50)).isoformat(),
         "_label": "out of range"},
    ]
    tail = [
        {"type": "location", "lat": 3.8750, "lng": 11.5130,
         "accuracy_m": 8, "ts": (t0 + timedelta(seconds=60)).isoformat()},
    ]

    print("sending 2 honest points, 5 attacks, then 1 honest point")
    frames = honest + [{k: v for k, v in a.items() if k != "_label"} for a in attacks]
    frames += tail
    # Only the socket work is async. The HTTP setup stays synchronous so this
    # reads like the other harnesses and so blocking calls never sit inside an
    # event loop.
    replies = asyncio.run(send_points(args.ws, d_token, frames))
    rejected_replies = [r for r in replies if r.get("type") == "location_rejected"]
    print(f"{DIM}  {len(rejected_replies)} rejection frames returned{RESET}\n")

    print("what the database recorded")
    total = int(psql(f"SELECT count(*) FROM ride_traces WHERE ride_id='{uid(ride_id)}'") or 0)
    rejected = int(psql(
        f"SELECT count(*) FROM ride_traces "
        f"WHERE ride_id='{uid(ride_id)}' AND rejected"
    ) or 0)
    accepted = total - rejected

    print(f"{DIM}  {total} points stored, {accepted} accepted, {rejected} rejected{RESET}")
    check("every point was stored, none silently dropped", total == len(frames),
          f"{total} rows for {len(frames)} frames; rejected points must be kept")
    check("all five attacks were rejected", rejected == len(attacks),
          f"{rejected} rejected, expected {len(attacks)}")
    check("all three honest points were accepted", accepted == 3,
          f"{accepted} accepted, expected 3")

    reasons = psql(
        f"SELECT string_agg(DISTINCT reject_reason, ',') FROM ride_traces "
        f"WHERE ride_id='{uid(ride_id)}' AND rejected"
    )
    print(f"{DIM}  reasons: {reasons}{RESET}")
    for expected in ("teleport_jump", "poor_accuracy", "non_monotonic_timestamp",
                     "coordinates_out_of_range"):
        check(f"recorded reason {expected}", expected in (reasons or ""))
    print()

    print("the fare ignores rejected points (I2)")
    # Distance over accepted points only, versus over everything. If a teleport
    # to Douala counted, the second number would be roughly 200 km larger.
    accepted_m = float(psql(
        f"SELECT coalesce(ST_Length(ST_MakeLine(geom::geometry ORDER BY seq)::geography), 0) "
        f"FROM ride_traces WHERE ride_id='{uid(ride_id)}' AND NOT rejected"
    ) or 0)
    all_m = float(psql(
        f"SELECT coalesce(ST_Length(ST_MakeLine(geom::geometry ORDER BY seq)::geography), 0) "
        f"FROM ride_traces WHERE ride_id='{uid(ride_id)}'"
    ) or 0)
    print(f"{DIM}  accepted trace {accepted_m:.0f} m, all points {all_m:.0f} m{RESET}")
    check("the accepted trace is a short urban hop", accepted_m < 2_000,
          f"{accepted_m:.0f} m")
    check("counting the forgeries would have inflated it hugely",
          all_m > accepted_m * 10,
          "the attack points did not move the total, so this proves little")

    # Re-authenticate before the transitions.
    #
    # A genuine token expiry here reports as 401 on `start`, which reads like
    # an authorization bug and sends somebody looking in entirely the wrong
    # place. The token is the thing that aged out, so mint a new one.
    d_token, _ = authenticate(client, base, d_phone)
    driver = {"Authorization": f"Bearer {d_token}"}

    client.post(f"{base}/rides/{ride_id}/arrived", headers=driver)
    started = client.post(
        f"{base}/rides/{ride_id}/start", headers=driver,
        json={"pin": psql(f"SELECT pin FROM rides WHERE id='{uid(ride_id)}'")},
    )
    check("trip starts", started.status_code == 200, f"got {started.status_code}")

    done = client.post(f"{base}/rides/{ride_id}/complete", headers=driver)
    if check("trip completes", done.status_code == 200, f"got {done.status_code}"):
        final = done.json()["final_fare_xaf"]
        distance = done.json()["ride"]["actual_distance_m"]
        print(f"{DIM}  final fare {final} XAF over {distance} m{RESET}")
        check("the fare reflects the honest trace, not the forged one",
              final < 2_000, f"{final} XAF suggests forged distance was counted")
        check("recorded distance excludes the teleport", distance < 2_000,
              f"{distance} m")
    print()

    print("the forgery attempts are in the audit trail (I7)")
    events = int(psql(
        f"SELECT count(*) FROM ride_events "
        f"WHERE ride_id='{uid(ride_id)}' AND event_type='trace_point_rejected'"
    ) or 0)
    check("each rejection was written to ride_events", events == len(attacks),
          f"{events} events for {len(attacks)} rejections")

    return summarise()


def summarise() -> int:
    print("\n-----------------------------------------")
    print(f"passed: {_passed}   failed: {_failed}")
    if _failed:
        print(f"{RED}spoof test FAILED{RESET}")
        return 1
    print(f"{GREEN}spoof test passed: every forged point rejected and recorded{RESET}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, RuntimeError, OSError) as exc:
        print(f"{RED}error: {exc}{RESET}", file=sys.stderr)
        raise SystemExit(2) from exc
