#!/usr/bin/env python3
"""Driver KYC state machine check (Phase 1, deliverable 5).

Proves the gate that matters: an unverified driver cannot go online, and the
only thing that changes that is an admin decision taken against a complete set
of documents.

    python scripts/kyc_smoke.py --base http://localhost:8080/api/v1

Needs the stack running locally, because it promotes a fresh account to driver
and another to admin directly in Postgres. There is deliberately no API route
that grants a role: self-service role escalation is the sort of endpoint that
gets found.
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


def uid(value: str) -> str:
    """Validate a UUID before it is interpolated into SQL.

    `psql -c` takes no bind parameters, so this harness builds statements as
    strings. Every interpolated value is a server-generated UUID, and this
    parses it to prove that rather than assuming it. I6 says every query is
    parameterised; where the tool cannot, the input is constrained instead.
    """
    return str(uuid.UUID(value))


def psql(sql: str) -> str:
    """Run one statement and return its first result line.

    Only the first line: a statement with RETURNING also emits a command tag
    ("INSERT 0 1"), and returning both makes the value unusable as an id.
    """
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "vora",
         "-d", "vora", "-tAc", sql],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[0] if lines else ""


def latest_code() -> str | None:
    result = subprocess.run(
        ["docker", "compose", "logs", "--tail", "400", "api"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    codes = []
    for line in result.stdout.splitlines():
        clean = ANSI.sub("", line)
        if "otp_console_delivery" in clean:
            m = re.search(r'code["\']?\s*[:=]\s*["\']?(\d{4})', clean)
            if m:
                codes.append(m.group(1))
    return codes[-1] if codes else None


def login(client: httpx.Client, base: str, phone: str) -> tuple[str, str]:
    """Full OTP login. Returns (access_token, user_id)."""
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
    body = r.json()
    return body["access_token"], body["user"]["id"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8080/api/v1")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    client = httpx.Client(timeout=30.0)
    suffix = uuid.uuid4().int % 10000
    driver_phone = f"+23760000000{suffix:04d}"
    admin_phone = f"+23760000000{(suffix + 1) % 10000:04d}"

    print(f"VORA kyc smoke against {base}")
    print(f"{DIM}driver: {driver_phone}  admin: {admin_phone}{RESET}\n")

    # Buckets are cleared so the two logins below are not refused by the
    # per-IP hourly cap left over from a previous run.
    subprocess.run(
        ["docker", "compose", "exec", "-T", "redis", "sh", "-c",
         "redis-cli --scan --pattern 'rl:*' | xargs -r redis-cli DEL"],
        capture_output=True, text=True, timeout=30, check=False,
    )

    print("setup")
    driver_token, driver_user_id = login(client, base, driver_phone)
    admin_token, admin_user_id = login(client, base, admin_phone)
    check("two accounts created via OTP", bool(driver_token and admin_token))

    # Roles are granted out of band on purpose. No endpoint does this.
    psql(f"UPDATE users SET role='driver' WHERE id='{uid(driver_user_id)}'")
    psql(f"UPDATE users SET role='admin' WHERE id='{uid(admin_user_id)}'")
    driver_id = psql(
        f"INSERT INTO drivers (user_id) VALUES ('{uid(driver_user_id)}') RETURNING id"
    )
    check("driver record created in pending", bool(driver_id))

    dauth = {"Authorization": f"Bearer {driver_token}"}
    aauth = {"Authorization": f"Bearer {admin_token}"}
    print()

    print("gate: unverified driver cannot go online")
    r = client.post(
        f"{base}/driver/online", headers=dauth,
        json={"lat": 3.848, "lng": 11.502, "seats_free": 3},
    )
    check("returns 409", r.status_code == 409, f"got {r.status_code}: {r.text[:160]}")
    if r.status_code == 409:
        check("code is KYC_NOT_VERIFIED", r.json()["error"]["code"] == "KYC_NOT_VERIFIED")

    # The database refuses it too, independently of the handler.
    try:
        psql(f"UPDATE drivers SET is_online = true WHERE id='{uid(driver_id)}'")
        check("database CHECK constraint blocks it", False, "the UPDATE succeeded")
    except RuntimeError as exc:
        check(
            "database CHECK constraint blocks it independently",
            "ck_drivers_online_requires_verified_kyc" in str(exc),
            str(exc)[:160],
        )
    print()

    print("admin cannot verify an incomplete file")
    r = client.post(
        f"{base}/admin/drivers/{driver_id}/kyc", headers=aauth,
        json={"status": "verified"},
    )
    check("returns 409", r.status_code == 409, f"got {r.status_code}: {r.text[:200]}")
    if r.status_code == 409:
        check(
            "names the missing documents",
            bool(r.json()["error"]["details"].get("missing_documents")),
            str(r.json()["error"]["details"])[:160],
        )
    print()

    print("document submission")
    kinds = ["cni", "driving_licence", "vehicle_registration", "vehicle_photo",
             "driver_photo"]
    for kind in kinds:
        r = client.post(
            f"{base}/driver/kyc/documents", headers=dauth,
            json={"kind": kind, "reference": f"REF-{kind.upper()}-12345"},
        )
        if r.status_code != 201:
            check(f"submit {kind}", False, f"got {r.status_code}: {r.text[:160]}")
            break
    else:
        check("all five documents accepted", True)

    r = client.get(f"{base}/driver/kyc", headers=dauth)
    if check("GET /driver/kyc returns 200", r.status_code == 200):
        check("nothing is still missing", r.json()["missing"] == [])
        check("status is still pending", r.json()["kyc_status"] == "pending",
              "submitting documents must not self-approve")

    stored = psql(
        f"SELECT encode(reference_enc, 'hex') FROM kyc_documents "
        f"WHERE driver_id='{uid(driver_id)}' AND kind='cni'"
    )
    check(
        "the reference is encrypted at rest",
        "REF-CNI" not in bytes.fromhex(stored).decode("latin-1"),
        "plaintext found in the stored blob",
    )
    cni_hash = psql(f"SELECT cni_ref_hash FROM drivers WHERE id='{uid(driver_id)}'")
    check("the CNI is stored only as a keyed hash", len(cni_hash) == 64)
    print()

    print("admin decision")
    r = client.post(
        f"{base}/admin/drivers/{driver_id}/kyc", headers=aauth,
        json={"status": "rejected"},
    )
    check("rejection without a reason is refused", r.status_code == 400,
          f"got {r.status_code}")

    r = client.post(
        f"{base}/admin/drivers/{driver_id}/kyc", headers=aauth,
        json={"status": "verified"},
    )
    if check("verification succeeds", r.status_code == 200,
             f"got {r.status_code}: {r.text[:200]}"):
        check("status is verified", r.json()["kyc_status"] == "verified")

    r = client.post(f"{base}/admin/drivers/{driver_id}/kyc", headers=dauth,
                    json={"status": "verified"})
    check("a driver cannot approve themselves", r.status_code == 403,
          f"got {r.status_code}")
    print()

    print("verified driver can work")
    r = client.post(
        f"{base}/driver/online", headers=dauth,
        json={"lat": 3.848, "lng": 11.502, "seats_free": 3},
    )
    if check("going online succeeds", r.status_code == 200,
             f"got {r.status_code}: {r.text[:200]}"):
        check("presence reports online", r.json()["presence"]["is_online"] is True)
        check("seats_free is recorded", r.json()["presence"]["seats_free"] == 3)

    print()
    print("suspension takes effect immediately")
    r = client.post(
        f"{base}/admin/drivers/{driver_id}/kyc", headers=aauth,
        json={"status": "suspended", "reason": "test suspension"},
    )
    check("suspension succeeds", r.status_code == 200, f"got {r.status_code}")
    online = psql(f"SELECT is_online FROM drivers WHERE id='{uid(driver_id)}'")
    check("a suspended driver is forced offline", online == "f",
          f"is_online is {online!r}")

    r = client.post(
        f"{base}/driver/online", headers=dauth,
        json={"lat": 3.848, "lng": 11.502, "seats_free": 3},
    )
    check("and cannot go back online", r.status_code == 409, f"got {r.status_code}")

    print("\n-----------------------------------------")
    print(f"passed: {_passed}   failed: {_failed}")
    if _failed:
        print(f"{RED}kyc smoke FAILED{RESET}")
        return 1
    print(f"{GREEN}kyc smoke passed{RESET}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"{RED}error: {exc}{RESET}", file=sys.stderr)
        raise SystemExit(2) from exc
