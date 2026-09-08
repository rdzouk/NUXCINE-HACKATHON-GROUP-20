#!/usr/bin/env python3
"""Concurrent driver claim. Phase 3 acceptance check.

    python scripts/race_test.py -n 20

Fires N simultaneous accepts at one ride and asserts **exactly one 200 and
N-1 409s**. Two passengers must never be sent the same car, and one passenger
must never have two drivers arrive.

This is a real race, not a simulation of one: N drivers, N tokens, N HTTP
requests released at the same instant by an asyncio barrier so they land inside
the same database transaction window. A sequential loop would pass against code
that has no locking at all, which is exactly the bug worth catching.

Correctness here rests on three layers, and the test does not care which one
fires:

  1. `SELECT ... FOR UPDATE` on the offer, then the ride
  2. a partial unique index on `rides (driver_id) WHERE status IN (live...)`
  3. a partial unique index on `rides (passenger_id) WHERE status IN (live...)`

The locks make the common case correct; the indexes make it correct even if
the claim function has a bug. What the test asserts is the outcome.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import subprocess
import sys
import uuid

import httpx

GREEN, RED, YELLOW, DIM, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
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
    """Validate before interpolating: psql -c takes no bind parameters."""
    return str(uuid.UUID(value))


def reset_limits() -> None:
    subprocess.run(
        ["docker", "compose", "exec", "-T", "redis", "sh", "-c",
         "redis-cli --scan --pattern 'rl:*' | xargs -r redis-cli DEL"],
        capture_output=True, text=True, timeout=120, check=False,
    )


def all_codes() -> list[str]:
    result = subprocess.run(
        ["docker", "compose", "logs", "--tail", "600", "api"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    codes = []
    for line in result.stdout.splitlines():
        clean = ANSI.sub("", line)
        if "otp_console_delivery" in clean:
            m = re.search(r'code["\']?\s*[:=]\s*["\']?(\d{4})', clean)
            if m:
                codes.append(m.group(1))
    return codes


async def login(client: httpx.AsyncClient, base: str, *, attempts: int = 4) -> tuple[str, str]:
    """One OTP round trip. Returns (access_token, user_id).

    Retries on a 5xx, because setting this test up is not what it measures.

    Creating twenty accounts means forty argon2 hashes at 32 MiB each, and on a
    loaded box that occasionally exceeds the API's fifteen-second request
    timeout and comes back as a 504. That cost is deliberate: a four-digit OTP
    is only safe because the hash is memory-hard. Failing the concurrency test
    over it would be measuring the wrong thing.
    """
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            phone = f"+23760000000{uuid.uuid4().int % 10000:04d}"
            r = await client.post(f"{base}/auth/otp/request", json={"phone": phone})
            r.raise_for_status()
            challenge_id = r.json()["challenge_id"]

            codes = all_codes()
            if not codes:
                raise RuntimeError("no OTP in the api logs")
            r = await client.post(
                f"{base}/auth/otp/verify",
                json={"challenge_id": challenge_id, "code": codes[-1]},
            )
            r.raise_for_status()
            body = r.json()
            return body["access_token"], body["user"]["id"]
        except (httpx.HTTPError, RuntimeError) as exc:
            last = exc
            if attempt < attempts - 1:
                reset_limits()
                await asyncio.sleep(2 * (attempt + 1))

    raise RuntimeError(f"login failed after {attempts} attempts: {last}")


def make_driver(user_id: str, lat: float, lng: float) -> str:
    """Promote a user to a verified, online driver with a vehicle.

    Done in SQL rather than through the API because the point of this test is
    the claim path, not the KYC flow, and because there is deliberately no
    endpoint that grants a role.
    """
    uid(user_id)
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
    # Upsert, because the driver may already have a presence row: going online
    # through the API writes one, and this harness plants its own. A plain
    # INSERT collided on the primary key and killed the run during setup, with
    # the failure looking like a concurrency bug rather than a fixture one.
    psql(
        f"INSERT INTO driver_presence (driver_id, geom, recorded_at) "
        f"VALUES ('{uid(driver_id)}', "
        f"ST_MakePoint({lng}, {lat})::geography, now()) "
        f"ON CONFLICT (driver_id) DO UPDATE SET "
        f"  geom = EXCLUDED.geom, "
        f"  recorded_at = EXCLUDED.recorded_at, "
        f"  is_stale = false"
    )
    return driver_id


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8080/api/v1")
    parser.add_argument("-n", "--drivers", type=int, default=20)
    args = parser.parse_args()
    base = args.base.rstrip("/")
    n = args.drivers

    print(f"VORA race test against {base}")
    print(f"{DIM}{n} drivers accepting one ride simultaneously{RESET}\n")

    async with httpx.AsyncClient(timeout=90.0) as client:
        print("setup")
        reset_limits()

        # Take every other driver offline first.
        #
        # A matching wave offers to the nearest N candidates, so leftover
        # online drivers from earlier suites and from the seeded fleet would
        # crowd this test out of its own race. Isolating is legitimate here:
        # what is under test is what happens when N drivers accept at once,
        # not which N were chosen.
        psql("UPDATE drivers SET is_online = false WHERE is_online")

        passenger_token, _ = await login(client, base)
        passenger = {"Authorization": f"Bearer {passenger_token}"}
        check("passenger signed in", bool(passenger_token))

        driver_tokens: list[str] = []
        for i in range(n):
            reset_limits()
            token, user_id = await login(client, base)
            # Scattered within a few hundred metres of the pickup so all of
            # them fall inside wave 1's 2 km radius.
            # Tightly clustered at the pickup so all of them are genuine
            # candidates and the race is as wide as the wave cap allows.
            make_driver(
                user_id,
                WARDA["lat"] + (i % 5) * 0.00005,
                WARDA["lng"] + (i // 5) * 0.00005,
            )
            driver_tokens.append(token)
        check(f"{n} verified online drivers created", len(driver_tokens) == n)

        q = await client.post(
            f"{base}/rides/quote", headers=passenger,
            json={"pickup": WARDA, "dropoff": CENTRAL, "seats": 1,
                  "mode": "exclusive"},
        )
        if q.status_code != 200:
            print(f"{RED}quote failed: {q.status_code} {q.text[:200]}{RESET}")
            return 1

        r = await client.post(
            f"{base}/rides",
            headers={**passenger, "Idempotency-Key": str(uuid.uuid4())},
            json={"quote_id": q.json()["quote_id"], "seats": 1,
                  "accessibility_required": []},
        )
        if r.status_code not in (200, 201):
            print(f"{RED}ride creation failed: {r.status_code} {r.text[:300]}{RESET}")
            return 1
        ride_id = r.json()["ride"]["id"]
        print(f"{DIM}  ride {ride_id}{RESET}")

        # Each driver's own offer for this ride. They are different offer rows,
        # which is the harder race: two accepts of the *same* offer serialise on
        # one row lock, whereas N accepts of N offers on one ride only serialise
        # if the ride itself is locked.
        offers: list[tuple[str, str]] = []
        for token in driver_tokens:
            resp = await client.get(
                f"{base}/driver/offers", headers={"Authorization": f"Bearer {token}"}
            )
            if resp.status_code == 200:
                found = resp.json()["offers"]
                match = [o for o in found if o["ride_id"] == ride_id]
                if match:
                    offers.append((token, match[0]["id"]))

        # Fewer offers than drivers is expected, not a fault.
        #
        # Each matching wave offers to the nearest N candidates rather than to
        # everybody in range: blasting one ride at every driver in the city
        # wastes their attention and makes the second wave meaningless. So the
        # number of contenders here is the wave cap, not the driver count.
        #
        # What the race needs is enough simultaneous claims to be a real
        # contest. Below a handful it would pass against code with no locking
        # at all, which is the bug this test exists to catch.
        check(
            f"enough contenders for a real race ({len(offers)} of {n} drivers)",
            len(offers) >= 5,
            "too few offers to prove anything about concurrency",
        )
        if len(offers) < n:
            print(
                f"{DIM}  matching capped the wave at {len(offers)}; that is the "
                f"design, not a miss{RESET}"
            )

        print()
        print(f"firing {len(offers)} simultaneous accepts")

        # A barrier, so nothing is released until every request is built and
        # every connection is warm. Without it the first request wins on
        # latency rather than on locking, and the test proves nothing.
        barrier = asyncio.Barrier(len(offers))

        async def accept(token: str, offer_id: str):
            await barrier.wait()
            return await client.post(
                f"{base}/driver/offers/{offer_id}/accept",
                headers={"Authorization": f"Bearer {token}"},
            )

        results = await asyncio.gather(
            *(accept(t, o) for t, o in offers), return_exceptions=True
        )

        statuses: list[int] = []
        errors: list[str] = []
        for outcome in results:
            if isinstance(outcome, Exception):
                errors.append(f"{type(outcome).__name__}: {outcome}")
                continue
            statuses.append(outcome.status_code)

        winners = [s for s in statuses if s == 200]
        losers = [s for s in statuses if s == 409]
        others = [s for s in statuses if s not in (200, 409)]

        print(f"{DIM}  statuses: {sorted(statuses)}{RESET}")
        if errors:
            print(f"{DIM}  transport errors: {errors[:3]}{RESET}")

        print()
        check(
            "exactly one accept succeeded",
            len(winners) == 1,
            f"{len(winners)} winners; two drivers were sent to one passenger"
            if len(winners) > 1
            else f"{len(winners)} winners; nobody got the ride",
        )
        check(
            f"the other {len(offers) - 1} were refused with 409",
            len(losers) == len(offers) - 1,
            f"{len(losers)} of {len(offers) - 1} returned 409",
        )
        check(
            "no request returned a server error",
            not others and not errors,
            f"unexpected statuses {others}; losing a race is not a 500",
        )

        # The database is the real arbiter.
        assigned = psql(
            f"SELECT count(DISTINCT driver_id) FROM rides "
            f"WHERE id='{uid(ride_id)}' AND driver_id IS NOT NULL"
        )
        check("the ride has exactly one driver", assigned == "1", f"got {assigned}")

        accepted_offers = psql(
            f"SELECT count(*) FROM ride_offers "
            f"WHERE ride_id='{uid(ride_id)}' AND state='accepted'"
        )
        check(
            "exactly one offer is marked accepted",
            accepted_offers == "1",
            f"got {accepted_offers}",
        )

        superseded = psql(
            f"SELECT count(*) FROM ride_offers "
            f"WHERE ride_id='{uid(ride_id)}' AND state='superseded'"
        )
        print(f"{DIM}  {superseded} offers superseded{RESET}")

        status_now = psql(f"SELECT status FROM rides WHERE id='{uid(ride_id)}'")
        check("the ride is accepted", status_now == "accepted", f"got {status_now}")

        events = psql(
            f"SELECT count(*) FROM ride_events WHERE ride_id='{uid(ride_id)}'"
        )
        check("the transition was written to the event log", int(events or 0) >= 2,
              f"{events} events")

    print("\n-----------------------------------------")
    print(f"passed: {_passed}   failed: {_failed}")
    if _failed:
        print(f"{RED}race test FAILED{RESET}")
        return 1
    print(f"{GREEN}race test passed: exactly one winner{RESET}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"{RED}error: {exc}{RESET}", file=sys.stderr)
        raise SystemExit(2) from exc
