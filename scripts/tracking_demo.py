#!/usr/bin/env python3
"""Set up a live tracking demo, and verify it end to end.

    python scripts/tracking_demo.py

Creates a passenger and a driver, books a ride, accepts it, starts the
simulator, and watches the passenger socket to confirm the driver actually
moves. Prints a passenger token to paste into `tools/tracking_dashboard.html`.

This is both the Phase 4 acceptance check and the thing you run five minutes
before a demo. Watching the socket rather than only firing the simulator is the
point: a simulator that writes to the database but never reaches a passenger
would look identical from the outside, and would fail on stage.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
import uuid

import httpx
import websockets

GREEN, RED, DIM, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"
)
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


async def watch_passenger(ws_base: str, token: str, seconds: int) -> list[dict]:
    """Listen on the passenger socket and collect driver_location frames."""
    frames: list[dict] = []
    try:
        async with websockets.connect(f"{ws_base}/ws/passenger") as ws:
            await ws.send(json.dumps({"type": "auth", "token": token}))
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if ready.get("type") != "ready":
                raise RuntimeError(f"expected ready, got {ready}")

            deadline = asyncio.get_running_loop().time() + seconds
            while asyncio.get_running_loop().time() < deadline:
                remaining = deadline - asyncio.get_running_loop().time()
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                except TimeoutError:
                    break
                msg = json.loads(raw)
                if msg.get("type") == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
                elif msg.get("type") == "driver_location":
                    loc = msg["location"]
                    frames.append(loc)
                    print(
                        f"{DIM}    {loc['lat']:.5f}, {loc['lng']:.5f}"
                        f"  eta {msg.get('eta_s')}s{RESET}"
                    )
    except (OSError, websockets.WebSocketException) as exc:
        print(f"{RED}  socket error: {exc}{RESET}")
    return frames


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8080/api/v1")
    parser.add_argument("--ws", default="ws://localhost:8080/api/v1")
    parser.add_argument("--watch", type=int, default=25, help="Seconds to observe.")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    client = httpx.Client(timeout=90.0)
    print(f"VORA tracking demo against {base}\n")

    print("setup")
    p_token, _ = login(client, base)
    d_token, d_user = login(client, base)
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
    if not check("quoted", q.status_code == 200, f"got {q.status_code}"):
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

    acc = client.post(f"{base}/driver/offers/{mine[0]['id']}/accept", headers=driver)
    if not check("driver accepted", acc.status_code == 200, f"got {acc.status_code}"):
        return summarise()
    print()

    print("starting the simulator")
    sim = client.post(
        f"{base}/dev/simulate-driver",
        json={"ride_id": ride_id, "speed_kmh": 28},
    )
    if not check("simulator accepted", sim.status_code == 202,
                 f"got {sim.status_code}: {sim.text[:200]}"):
        return summarise()
    body = sim.json()
    print(f"{DIM}  {body['points']} route points, about "
          f"{body['estimated_duration_s']}s at {body['speed_kmh']} km/h{RESET}")
    print()

    print(f"watching the passenger socket for {args.watch}s")
    frames = asyncio.run(watch_passenger(args.ws, p_token, args.watch))

    print()
    check("the passenger received location frames", len(frames) >= 3,
          f"only {len(frames)} frames; the driver is not visibly moving")

    if len(frames) >= 2:
        moved = any(
            abs(frames[i]["lat"] - frames[0]["lat"]) > 1e-5
            or abs(frames[i]["lng"] - frames[0]["lng"]) > 1e-5
            for i in range(1, len(frames))
        )
        check("the marker actually moves", moved,
              "every frame reported the same position")
        check("each frame carries a timestamp", all(
            f.get("updated_at") for f in frames),
            "without it the client cannot show a stale-fix warning")

    stored = int(psql(
        f"SELECT count(*) FROM ride_traces WHERE ride_id='{uid(ride_id)}' "
        f"AND NOT rejected"
    ) or 0)
    check("the trace was persisted", stored >= 3, f"{stored} accepted points")

    rejected = int(psql(
        f"SELECT count(*) FROM ride_traces WHERE ride_id='{uid(ride_id)}' "
        f"AND rejected"
    ) or 0)
    check("the simulator produces plausible points", rejected == 0,
          f"{rejected} simulated points were rejected by the filter")

    print()
    print(f"{BOLD}Dashboard{RESET}")
    print("  open tools/tracking_dashboard.html and paste this passenger token:")
    print()
    print(f"  {p_token}")
    print()
    print(f"{DIM}  ride {ride_id}{RESET}")
    print(f"{DIM}  restart the simulator any time with:{RESET}")
    print(f"{DIM}    curl -X POST {base}/dev/simulate-driver \\{RESET}")
    print(f"{DIM}      -H 'Content-Type: application/json' \\{RESET}")
    print(f"{DIM}      -d '{{\"ride_id\":\"{ride_id}\",\"speed_kmh\":28}}'{RESET}")

    return summarise()


def summarise() -> int:
    print("\n-----------------------------------------")
    print(f"passed: {_passed}   failed: {_failed}")
    if _failed:
        print(f"{RED}tracking demo FAILED{RESET}")
        return 1
    print(f"{GREEN}tracking demo passed: the driver moves on the passenger socket{RESET}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, RuntimeError, OSError) as exc:
        print(f"{RED}error: {exc}{RESET}", file=sys.stderr)
        raise SystemExit(2) from exc
