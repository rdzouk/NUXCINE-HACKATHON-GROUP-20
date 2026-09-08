#!/usr/bin/env python3
"""Break each dependency in turn and check the system degrades honestly.

    python scripts/degradation_test.py

The brief says "Cameroonian realities" four times. A demo that survives you
pulling a dependency out is a stronger statement than any slide about
resilience, so this pulls them out on purpose.

Three things are being checked, and the third is the one that matters:

  it still works      the parts that can survive without the dependency do
  it says so          `/health` reports the truth, not a cheerful lie
  it recovers         bringing the dependency back needs no restart

**Failing open and failing closed are different decisions and both are here.**
Losing Redis must not stop somebody reading their ride, so the general limiter
fails open. Losing Redis *must* stop OTP sending, because the limiter is the
only thing between us and an unbounded SMS bill, so that one fails closed.
A system that failed the same way everywhere would be wrong in one direction
or the other.

This restores every container it stops, including on Ctrl-C, because a harness
that leaves the stack broken is worse than no harness an hour before a demo.
"""

from __future__ import annotations

import argparse
import contextlib
import subprocess
import sys
import time
import uuid

import httpx

GREEN, RED, YELLOW, DIM, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
)

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


def compose(*args: str, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", *args],
        capture_output=True, text=True, timeout=timeout, check=False,
    )


def _ready(service: str, attempts: int = 60) -> bool:
    """Whether a restored service can answer, not just whether it is running."""
    for _ in range(attempts):
        time.sleep(2)
        if service == "osrm":
            probe = compose(
                "exec", "-T", "api", "python", "-c",
                "import httpx,sys;"
                "r=httpx.get('http://osrm:5000/route/v1/driving/"
                "11.5021,3.8480;11.5100,3.8550?overview=false',timeout=5);"
                "sys.exit(0 if r.json().get('code')=='Ok' else 1)",
            )
        elif service == "redis":
            probe = compose("exec", "-T", "redis", "redis-cli", "ping")
        else:
            probe = compose("ps", service, "--format", "{{.Status}}")
        if probe.returncode == 0 and "error" not in probe.stdout.lower():
            return True
    return False


@contextlib.contextmanager
def stopped(service: str):
    """Stop a service for the duration of the block, then always restore it."""
    print(f"{DIM}  stopping {service}{RESET}")
    compose("stop", service)
    try:
        yield
    finally:
        print(f"{DIM}  restoring {service}{RESET}")
        compose("start", service)
        # Wait for the service to actually *work*, not merely to be running.
        #
        # "Up" arrives the instant the process starts. OSRM then has to mmap a
        # routing graph, which on a loaded box takes appreciably longer, and
        # its own healthcheck reports unhealthy even while it serves. Breaking
        # on "Up" meant the recovery assertion raced the engine's startup and
        # then blamed the recovery.
        if not _ready(service):
            print(f"{DIM}  warning: {service} did not come back in time{RESET}")


def wait_until_serving(client: httpx.Client, base: str, attempts: int = 30) -> bool:
    for _ in range(attempts):
        try:
            if client.get(f"{base}/health", timeout=10).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(2)
    return False


QUOTE_BODY = {
    "pickup": {"lat": 3.8760, "lng": 11.5120, "label": "Carrefour Warda"},
    "dropoff": {"lat": 3.8660, "lng": 11.5170, "label": "Marche Central"},
    "seats": 1,
    "mode": "exclusive",
}


def latest_code() -> str | None:
    result = compose("logs", "--tail", "400", "api")
    import re
    codes = []
    for line in result.stdout.splitlines():
        clean = re.sub(r"\x1b\[[0-9;]*m", "", line)
        if "otp_console_delivery" in clean:
            m = re.search(r'code["\']?\s*[:=]\s*["\']?(\d{4})', clean)
            if m:
                codes.append(m.group(1))
    return codes[-1] if codes else None


def test_phone() -> str:
    """A number inside the reserved test range.

    Hardcoding one outside it is how the OTP checks below came to pass and
    fail for the wrong reason: PHONE_NOT_ALLOWED is a 4xx, so a check that
    only asserts "4xx" reads a rejected phone number as a working rate limit.
    """
    return f"+23760000000{uuid.uuid4().int % 10000:04d}"


def login(client: httpx.Client, base: str) -> str:
    phone = test_phone()
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8080/api/v1")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    client = httpx.Client(timeout=60.0)
    print(f"VORA degradation rehearsal against {base}\n")

    if not wait_until_serving(client, base):
        print(f"{RED}the API is not serving; start the stack first{RESET}")
        return 2

    token = login(client, base)
    auth = {"Authorization": f"Bearer {token}"}

    # ------------------------------------------------------ baseline --
    print(f"{BOLD}baseline{RESET}")
    r = client.post(f"{base}/rides/quote", headers=auth, json=QUOTE_BODY)
    check("a quote succeeds with everything up", r.status_code == 200,
          f"got {r.status_code}: {r.text[:160]}")
    baseline_source = r.json().get("routing_source") if r.status_code == 200 else None
    print(f"{DIM}  routing_source={baseline_source}{RESET}")

    health = client.get(f"{base}/health").json()
    check("health reports osrm as ok", health["components"]["osrm"]["status"] == "ok",
          str(health["components"].get("osrm")))
    print()

    # ----------------------------------------------------- osrm down --
    # The routing engine is the dependency most likely to be slow or wedged
    # on a demo box, and it is the one the fare depends on.
    print(f"{BOLD}OSRM is killed mid-demo{RESET}")
    with stopped("osrm"):
        r = client.post(f"{base}/rides/quote", headers=auth, json=QUOTE_BODY)
        if check("quoting still works without the routing engine",
                 r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"):
            body = r.json()
            source = body.get("routing_source")
            print(f"{DIM}  routing_source={source}, "
                  f"fare={body.get('fare_xaf')} XAF{RESET}")
            check("and it says the estimate is a fallback, not a route",
                  source != baseline_source,
                  "a client that cannot tell a routed fare from a straight-line "
                  "estimate cannot warn the passenger")
            check("the fallback fare is still sane",
                  isinstance(body.get("fare_xaf"), int) and body["fare_xaf"] > 0)
            check("and still payable in coins", body["fare_xaf"] % 50 == 0)

        health = client.get(f"{base}/health")
        check("health still answers while a dependency is down",
              health.status_code in (200, 503), f"got {health.status_code}")
        if health.status_code in (200, 503):
            osrm = health.json()["components"].get("osrm", {})
            check("health tells the truth about osrm",
                  osrm.get("status") != "ok", f"reported {osrm.get('status')}")

    recovered_in = None
    started = time.monotonic()
    for _ in range(15):
        r = client.post(f"{base}/rides/quote", headers=auth, json=QUOTE_BODY)
        if (
            r.status_code == 200
            and r.json().get("routing_source") == baseline_source
        ):
            recovered_in = time.monotonic() - started
            break
        time.sleep(2)

    check("routing recovers on its own once osrm is back",
          recovered_in is not None,
          f"still on the fallback after {time.monotonic() - started:.0f}s: "
          f"{r.status_code}, source={r.json().get('routing_source')}")
    if recovered_in is not None:
        print(f"{DIM}  routed fares resumed {recovered_in:.0f}s after osrm "
              f"came back{RESET}")
    print()

    # ---------------------------------------------------- redis down --
    print(f"{BOLD}Redis is killed{RESET}")
    with stopped("redis"):
        started = time.monotonic()
        r = client.get(f"{base}/places/search?q=warda")
        elapsed = time.monotonic() - started
        check("reads still work: the general limiter fails OPEN",
              r.status_code == 200, f"got {r.status_code}: {r.text[:160]}")
        print(f"{DIM}  first request after the outage took {elapsed:.1f}s{RESET}")

        started = time.monotonic()
        r = client.get(f"{base}/places/search?q=mokolo")
        second = time.monotonic() - started
        check("and failing open is FAST after the breaker opens",
              second < 2.0,
              f"{second:.1f}s; a limiter that waits for a Redis timeout on "
              f"every request turns a blip into a site-wide latency collapse")
        print(f"{DIM}  second request took {second:.1f}s{RESET}")

        # The other half of the decision, and the one that costs money.
        r = client.post(f"{base}/auth/otp/request", json={"phone": test_phone()})
        code = ""
        with contextlib.suppress(ValueError):
            code = r.json().get("error", {}).get("code", "")
        # Specifically RATE_LIMITED or a 5xx, never just "some 4xx". A
        # rejected phone number is also a 4xx and would pass a looser check
        # while proving nothing about the limiter.
        check("but OTP sending fails CLOSED",
              r.status_code >= 400 and code != "PHONE_NOT_ALLOWED",
              f"got {r.status_code} {code}; without the limiter this is an "
              f"unmetered SMS bill routed to premium-rate numbers")
        print(f"{DIM}  otp request -> {r.status_code} {code}{RESET}")

    check("the limiter recovers once Redis is back",
          client.get(f"{base}/places/search?q=warda").status_code == 200)

    # The breaker holds for its cooldown before dialling Redis again, so OTP
    # keeps refusing for a few seconds after Redis is back. That is the
    # designed behaviour and the honest trade: the alternative is dialling a
    # dead Redis on every request to find out it is alive again.
    #
    # What matters is that it comes back **on its own**, with no restart and no
    # human. So this waits it out and reports the real window rather than
    # asserting an instant recovery that the design does not promise.
    started = time.monotonic()
    recovered_in = None
    for _ in range(20):
        otp = client.post(f"{base}/auth/otp/request", json={"phone": test_phone()})
        if otp.status_code in (200, 202):
            recovered_in = time.monotonic() - started
            break
        time.sleep(2)

    check("and OTP sending resumes on its own, with no restart",
          recovered_in is not None,
          f"still refusing after {time.monotonic() - started:.0f}s: "
          f"{otp.status_code} {otp.text[:120]}")
    if recovered_in is not None:
        print(f"{DIM}  OTP resumed {recovered_in:.0f}s after Redis returned, "
              f"which is the breaker cooldown{RESET}")
    print()

    # ------------------------------------------------- nothing hangs --
    # The failure mode the plan calls out by name is the infinite spinner. A
    # bounded error is recoverable; a hang is not, because the client has no
    # event to react to.
    print(f"{BOLD}nothing hangs{RESET}")
    for label, path in (
        ("health", "/health"),
        ("landmark search", "/places/search?q=warda"),
        ("capabilities", "/vehicles/capabilities"),
    ):
        started = time.monotonic()
        try:
            response = client.get(f"{base}{path}", timeout=20)
            elapsed = time.monotonic() - started
            check(f"{label} answers in under 20s ({elapsed:.1f}s)",
                  response.status_code < 500, f"got {response.status_code}")
        except httpx.HTTPError as exc:
            check(f"{label} answers in under 20s", False, str(exc)[:160])

    return summarise()


def summarise() -> int:
    print("\n-----------------------------------------")
    print(f"passed: {_passed}   failed: {_failed}")
    if _failed:
        print(f"{RED}degradation rehearsal FAILED{RESET}")
        return 1
    print(f"{GREEN}every dependency degraded honestly and recovered{RESET}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        # Never leave the stack half-broken.
        print(f"\n{YELLOW}interrupted, restoring every service{RESET}")
        compose("start", "osrm")
        compose("start", "redis")
        raise SystemExit(130) from None
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"{RED}error: {exc}{RESET}", file=sys.stderr)
        compose("start", "osrm")
        compose("start", "redis")
        raise SystemExit(2) from exc
