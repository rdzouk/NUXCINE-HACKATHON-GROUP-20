#!/usr/bin/env python3
"""Phase 1 acceptance check.

Drives the full identity lifecycle against a deployed API over HTTP, then
attacks it. The attacks are the point: a signup flow that works is table
stakes, and what Phase 1 actually claims is that the flow resists brute force,
token theft and SMS pumping.

    python scripts/auth_smoke.py --base https://<host>/api/v1

Reading the OTP code: the console SmsSender logs it rather than sending an SMS,
so the code is pulled from the api container's logs. Pass --code-source docker
(the default) locally, or --code manually if you are running against a host
whose logs you cannot read from here.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
import uuid

import httpx

GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"
RESET = "\033[0m"

_passed = 0
_failed = 0


def ok(label: str) -> None:
    global _passed
    _passed += 1
    print(f"{GREEN}  PASS{RESET}  {label}")


def fail(label: str, detail: str = "") -> None:
    global _failed
    _failed += 1
    print(f"{RED}  FAIL{RESET}  {label}")
    if detail:
        print(f"{DIM}        {detail}{RESET}")


def check(label: str, condition: bool, detail: str = "") -> bool:
    if condition:
        ok(label)
    else:
        fail(label, detail)
    return condition


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def read_latest_code() -> str | None:
    """Pull the most recent OTP out of the api container logs.

    The console sender logs `otp_console_delivery` with the code. This is a
    development affordance and is exactly why ConsoleSmsSender refuses to run
    when APP_ENV is production.

    Two things this has to handle. In development the renderer emits ANSI
    colour, so `code=1234` is actually `ESC[36mcode ESC[0m= ESC[35m1234`, and a
    naive `code=(\\d{4})` never matches. In production-style JSON output the
    same field is `"code": "1234"`. Both forms are stripped and matched.

    The caller must read the code immediately after the request that produced
    it: this returns the newest code in the log, and any intervening OTP
    request would be the one returned instead.
    """
    try:
        result = subprocess.run(
            ["docker", "compose", "logs", "--tail", "400", "api"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None

    codes: list[str] = []
    for line in result.stdout.splitlines():
        clean = ANSI.sub("", line)
        if "otp_console_delivery" not in clean:
            continue
        match = re.search(r'code["\']?\s*[:=]\s*["\']?(\d{4})', clean)
        if match:
            codes.append(match.group(1))
    return codes[-1] if codes else None


def reset_rate_limits() -> bool:
    """Drop every token bucket, so a burst test measures a full allowance.

    A test affordance, not an endpoint. There is deliberately no HTTP route
    that clears rate limits: that route would be the first thing an attacker
    called before an SMS-pumping run. This reaches Redis directly and only
    works where the container is reachable.
    """
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "redis",
                "sh",
                "-c",
                "redis-cli --scan --pattern 'rl:*' | xargs -r redis-cli DEL",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return False
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8080/api/v1")
    parser.add_argument(
        "--phone",
        default=None,
        help="Test number. Defaults to a random +23760000000X test number.",
    )
    parser.add_argument("--code", default=None, help="Skip log reading; use this OTP.")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    # Each run uses a distinct test number so that the per-phone hourly bucket
    # from a previous run does not make this one look like a failure.
    phone = args.phone or f"+23760000000{uuid.uuid4().int % 10}"

    print(f"VORA auth smoke against {base}")
    print(f"{DIM}test number: {phone}{RESET}\n")

    client = httpx.Client(timeout=30.0, follow_redirects=False)

    # ---------------------------------------------------------------- OTP ---
    print("otp request")
    r = client.post(f"{base}/auth/otp/request", json={"phone": phone})
    if not check("returns 202", r.status_code == 202, f"got {r.status_code}: {r.text[:200]}"):
        return summarise()
    body = r.json()
    check("carries challenge_id", "challenge_id" in body)
    check("carries expires_at", "expires_at" in body)
    check("carries resend_after_s", "resend_after_s" in body)
    challenge_id = body.get("challenge_id")

    # Read the code now, before any other OTP request runs. The log gives the
    # newest code, so an intervening request would hand us the wrong one.
    code = args.code or read_latest_code()

    # Registration state must not be observable. An unknown number and a known
    # one have to answer identically, or this endpoint enumerates customers.
    unknown = "+237600000009"
    r_unknown = client.post(f"{base}/auth/otp/request", json={"phone": unknown})
    check(
        "unregistered number gets the same status",
        r_unknown.status_code == 202,
        f"got {r_unknown.status_code}",
    )
    if r_unknown.status_code == 202:
        check(
            "unregistered number gets the same body shape",
            set(r_unknown.json()) == set(body),
        )

    r_bad = client.post(f"{base}/auth/otp/request", json={"phone": "+15551234567"})
    check(
        "non-Cameroonian number is refused",
        r_bad.status_code == 422,
        f"got {r_bad.status_code}",
    )
    print()

    # ------------------------------------------------------------- verify ---
    print("otp verify")
    if not code:
        fail("could not read the OTP", "pass --code, or run where docker logs are readable")
        return summarise()
    print(f"{DIM}  code: {code}{RESET}")

    r = client.post(
        f"{base}/auth/otp/verify",
        json={"challenge_id": challenge_id, "code": "0000" if code != "0000" else "1111"},
    )
    check(
        "wrong code is rejected",
        r.status_code == 401,
        f"got {r.status_code}: {r.text[:160]}",
    )
    if r.status_code == 401:
        check(
            "wrong code reports attempts remaining",
            "attempts_remaining" in r.json().get("error", {}).get("details", {}),
        )

    r = client.post(
        f"{base}/auth/otp/verify", json={"challenge_id": challenge_id, "code": code}
    )
    if not check(
        "correct code opens a session",
        r.status_code == 200,
        f"got {r.status_code}: {r.text[:200]}",
    ):
        return summarise()

    session = r.json()
    check("returns an access token", bool(session.get("access_token")))
    check("returns a refresh token", bool(session.get("refresh_token")))
    check("returns the user object", "user" in session)
    user = session.get("user", {})
    check("user carries a role", user.get("role") == "passenger")
    check("user carries an accessibility profile", "accessibility" in user)
    check(
        "user carries outstanding_xaf",
        "outstanding_xaf" in user,
        "needed so the client knows booking will be refused",
    )

    # A consumed challenge must not be replayable.
    r_replay = client.post(
        f"{base}/auth/otp/verify", json={"challenge_id": challenge_id, "code": code}
    )
    check(
        "consumed challenge cannot be replayed",
        r_replay.status_code in (401, 404),
        f"got {r_replay.status_code}",
    )
    print()

    access = session["access_token"]
    refresh = session["refresh_token"]
    auth = {"Authorization": f"Bearer {access}"}

    # ---------------------------------------------------------------- me ----
    print("authenticated access")
    r = client.get(f"{base}/me", headers=auth)
    check("GET /me with a token returns 200", r.status_code == 200, f"got {r.status_code}")

    r = client.get(f"{base}/me")
    check("GET /me without a token returns 401", r.status_code == 401)

    r = client.get(f"{base}/me", headers={"Authorization": "Bearer forged.token.here"})
    check("forged token returns 401", r.status_code == 401)

    r = client.patch(
        f"{base}/me",
        headers=auth,
        json={"display_name": "Test Passenger", "accessibility": {"requires_ramp": True}},
    )
    if check("PATCH /me returns 200", r.status_code == 200, f"got {r.status_code}"):
        check(
            "accessibility is stored as a vehicle requirement",
            r.json()["user"]["accessibility"]["requires_ramp"] is True,
        )
    print()

    # ------------------------------------------------------ driver gating ---
    print("driver kyc gate")
    r = client.post(
        f"{base}/driver/online",
        headers=auth,
        json={"lat": 3.848, "lng": 11.502, "seats_free": 3},
    )
    check(
        "a passenger cannot go online",
        r.status_code == 403,
        f"got {r.status_code}: {r.text[:160]}",
    )
    if r.status_code == 403:
        check("refusal is FORBIDDEN_ROLE", r.json()["error"]["code"] == "FORBIDDEN_ROLE")

    r = client.get(f"{base}/admin/drivers", headers=auth)
    check(
        "a passenger cannot reach the admin queue",
        r.status_code == 403,
        f"got {r.status_code}",
    )
    print()

    # ------------------------------------------------------------ refresh ---
    print("refresh rotation and reuse detection")
    r = client.post(f"{base}/auth/refresh", json={"refresh_token": refresh})
    if not check(
        "refresh returns a new pair", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
    ):
        return summarise()
    rotated = r.json()
    new_refresh = rotated["refresh_token"]
    check("the refresh token actually changed", new_refresh != refresh)
    check("a new access token is issued", rotated["access_token"] != access)

    # The Phase 1 headline. Replaying a rotated token must kill the family.
    r = client.post(f"{base}/auth/refresh", json={"refresh_token": refresh})
    reuse_detected = check(
        "replaying a rotated token is refused",
        r.status_code == 401,
        f"got {r.status_code}: {r.text[:160]}",
    )
    if reuse_detected:
        check(
            "refusal is REFRESH_TOKEN_REUSED",
            r.json()["error"]["code"] == "REFRESH_TOKEN_REUSED",
            f"got {r.json().get('error', {}).get('code')}",
        )

    # And the family revocation must have fired, so the *new* token is dead too.
    r = client.post(f"{base}/auth/refresh", json={"refresh_token": new_refresh})
    check(
        "reuse revoked the whole family, not just the replayed token",
        r.status_code == 401,
        f"got {r.status_code}: the successor token still works, family was not revoked",
    )
    print()

    # -------------------------------------------------------- rate limits ---
    print("otp rate limiting")

    # Clear the buckets first. Everything above this point has already spent
    # from the per-IP hourly allowance, and a previous run of this script spent
    # more, so without a reset the burst below measures leftover budget rather
    # than the limiter. A run against a host whose Redis is not reachable from
    # here skips the reset and says so, rather than reporting a false failure.
    if reset_rate_limits():
        print(f"{DIM}  buckets reset{RESET}")
    else:
        print(
            f"{DIM}  could not reset buckets; counts below include earlier "
            f"requests{RESET}"
        )

    # A fresh number each run. The test range allows a four-digit suffix, so
    # reusing one number would hit its own hourly cap on the second run.
    burst_phone = f"+23760000000{uuid.uuid4().int % 10000:04d}"
    statuses: list[int] = []
    retry_after_seen = False
    for _ in range(10):
        rr = client.post(f"{base}/auth/otp/request", json={"phone": burst_phone})
        statuses.append(rr.status_code)
        if rr.status_code == 429 and "retry-after" in {k.lower() for k in rr.headers}:
            retry_after_seen = True
        time.sleep(0.1)

    accepted = sum(1 for s in statuses if s == 202)
    limited = sum(1 for s in statuses if s == 429)
    print(f"{DIM}  statuses: {statuses}{RESET}")
    check(
        "the per-phone hourly cap of 3 is enforced",
        accepted == 3,
        f"{accepted} requests were accepted, expected exactly 3",
    )
    check("the rest are rate limited", limited == 7, f"{limited} were limited, expected 7")
    check("429 carries a Retry-After header", retry_after_seen)

    return summarise()


def summarise() -> int:
    print("\n-----------------------------------------")
    print(f"passed: {_passed}   failed: {_failed}")
    if _failed:
        print(f"{RED}auth smoke FAILED{RESET}")
        return 1
    print(f"{GREEN}auth smoke passed{RESET}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except httpx.HTTPError as exc:
        print(f"{RED}transport error: {exc}{RESET}", file=sys.stderr)
        raise SystemExit(2) from exc
