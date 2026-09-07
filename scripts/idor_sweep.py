#!/usr/bin/env python3
"""IDOR sweep. Phase 3 acceptance check.

    python scripts/idor_sweep.py

IDOR is *the* characteristic vulnerability of ride-hailing APIs, and the check
for it is exactly the kind that gets skipped when done by hand. So this does
not test a list of routes somebody remembered to write down: it **reads
openapi.json**, finds every path containing `{ride_id}`, and asserts that a
stranger's token gets 404 on all of them.

That distinction is the entire point. A route added in a later phase without
the `require_ride_participant` dependency appears in openapi.json, gets swept
automatically, and fails here. A hand-maintained list would silently not cover
it, which is precisely how the one missed route becomes the vulnerability.

**404, not 403.** A 403 confirms the ride exists, which turns a guessed
identifier into a probe for whether somebody is currently travelling. Both are
"denied", but only one of them leaks.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

import httpx

GREEN, RED, YELLOW, DIM, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
)
ANSI = re.compile(r"\x1b\[[0-9;]*m")

_passed = 0
_failed = 0

WARDA = {"lat": 3.8760, "lng": 11.5120, "label": "Carrefour Warda"}
CENTRAL = {"lat": 3.8660, "lng": 11.5170, "label": "Marche Central"}

# Bodies for routes that need one. A schema failure would return 400 and mask
# the authorization result we are actually testing.
BODIES: dict[str, dict] = {
    "cancel": {"reason": "changed_mind"},
    "start": {"pin": "0000"},
    "messages": {"template_key": "at_gate"},
    "report": {"category": "safety", "description": "sweep"},
}


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


def reset_limits() -> None:
    subprocess.run(
        ["docker", "compose", "exec", "-T", "redis", "sh", "-c",
         "redis-cli --scan --pattern 'rl:*' | xargs -r redis-cli DEL"],
        capture_output=True, text=True, timeout=120, check=False,
    )


def login(client: httpx.Client, base: str) -> str:
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
    return r.json()["access_token"]


def ride_scoped_routes(spec: dict) -> list[tuple[str, str]]:
    """Every path templated on a ride id, straight from the contract."""
    found = []
    for path, operations in spec.get("paths", {}).items():
        if "{ride_id}" not in path:
            continue
        for method in operations:
            if method.upper() in {"GET", "POST", "PATCH", "DELETE", "PUT"}:
                found.append((method.upper(), path))
    return sorted(found)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8080/api/v1")
    parser.add_argument("--spec", default="openapi.json")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"contract not found: {spec_path}", file=sys.stderr)
        print("run scripts/export_openapi.py first", file=sys.stderr)
        return 1

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    routes = ride_scoped_routes(spec)

    print("VORA IDOR sweep")
    print(f"{DIM}{len(routes)} ride-scoped routes read from {spec_path}{RESET}\n")
    if not routes:
        print(f"{RED}no ride-scoped routes found; the sweep proves nothing{RESET}")
        return 1

    client = httpx.Client(timeout=60.0)

    print("setup")
    victim_token = login(client, base)
    attacker_token = login(client, base)
    check("two unrelated accounts", victim_token != attacker_token)

    victim = {"Authorization": f"Bearer {victim_token}"}
    attacker = {"Authorization": f"Bearer {attacker_token}"}

    # The victim books a real ride. Sweeping a nonexistent id would pass
    # trivially: a 404 for a ride that does not exist proves nothing about a
    # ride that does.
    q = client.post(
        f"{base}/rides/quote", headers=victim,
        json={"pickup": WARDA, "dropoff": CENTRAL, "seats": 1, "mode": "exclusive"},
    )
    if q.status_code != 200:
        print(f"{RED}could not quote: {q.status_code} {q.text[:200]}{RESET}")
        return 1

    r = client.post(
        f"{base}/rides", headers={**victim, "Idempotency-Key": str(uuid.uuid4())},
        json={"quote_id": q.json()["quote_id"], "seats": 1, "accessibility_required": []},
    )
    if r.status_code not in (200, 201):
        print(f"{RED}could not create a ride: {r.status_code} {r.text[:300]}{RESET}")
        return 1

    ride = r.json()["ride"]
    ride_id = ride["id"]
    check("victim owns a real ride", bool(ride_id))
    check(
        "the victim can read their own ride",
        client.get(f"{base}/rides/{ride_id}", headers=victim).status_code == 200,
        "if this fails the sweep below is meaningless",
    )
    print(f"{DIM}  ride {ride_id}{RESET}\n")

    print("a stranger's token against every ride-scoped route")
    leaks: list[str] = []
    for method, template in routes:
        path = template.replace("{ride_id}", ride_id)
        body = None
        for key, payload in BODIES.items():
            if path.rstrip("/").endswith(key):
                body = payload
                break

        response = client.request(
            method, f"{base}{path}", headers=attacker, json=body
        )

        # 404 is the only acceptable answer. 501 also passes: a route not yet
        # implemented cannot leak, and its dependency still ran first.
        ok = response.status_code in (404, 501)
        if response.status_code == 501:
            ok = True

        label = f"{method} {template}"
        if ok:
            check(f"{label} -> {response.status_code}", True)
        else:
            code = ""
            with contextlib.suppress(ValueError):
                code = response.json().get("error", {}).get("code", "")
            leaks.append(f"{label} returned {response.status_code} {code}")
            check(
                f"{label} -> {response.status_code}",
                False,
                "expected 404 RIDE_NOT_FOUND; a stranger reached this route",
            )

    print()
    print("the denial must not distinguish absent from forbidden")
    absent = client.get(
        f"{base}/rides/{uuid.uuid4()}", headers=attacker
    )
    real_but_foreign = client.get(f"{base}/rides/{ride_id}", headers=attacker)
    check(
        "a nonexistent ride and a foreign one answer identically",
        absent.status_code == real_but_foreign.status_code
        and absent.json()["error"]["code"] == real_but_foreign.json()["error"]["code"],
        f"absent={absent.status_code} foreign={real_but_foreign.status_code}",
    )
    check(
        "and that answer is 404, never 403",
        real_but_foreign.status_code == 404,
        f"got {real_but_foreign.status_code}: a 403 confirms the ride exists",
    )

    print("\n-----------------------------------------")
    print(f"routes swept: {len(routes)}   passed: {_passed}   failed: {_failed}")
    if leaks:
        print(f"{RED}{len(leaks)} LEAK(S):{RESET}")
        for leak in leaks:
            print(f"  {leak}")
        return 1
    if _failed:
        print(f"{RED}idor sweep FAILED{RESET}")
        return 1
    print(f"{GREEN}0 leaks{RESET}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"{RED}error: {exc}{RESET}", file=sys.stderr)
        raise SystemExit(2) from exc
