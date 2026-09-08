#!/usr/bin/env python3
"""Prove the documented admin demo account can actually reach the dashboard.

    python3 scripts/check_admin_login.py

The README hands a juror three phone numbers. A number that is written down but
does not log in is worse than no number at all, so this walks the admin one all
the way through: OTP request, OTP read, verify, then the two admin endpoints
the dashboard actually calls.

Uses only the standard library so it runs without the virtualenv.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080/api/v1"
PHONE = "+237600000007000"


def call(method: str, path: str, body=None, token: str | None = None):
    url = f"{BASE}{path}"

    # The base URL comes from argv, so the scheme is checked rather than
    # assumed. urllib will happily open file: and ftp:, and this script sends
    # a bearer token, which is not something to hand to an arbitrary scheme.
    if not url.startswith(("http://", "https://")):
        raise SystemExit(f"base URL must be http or https, got {BASE!r}")

    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)  # noqa: S310 - scheme checked above
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:  # noqa: S310 - scheme checked above
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        # The error envelope is the interesting part. Swallowing it and showing
        # a bare status code turns a five-second diagnosis into a long one.
        raw = exc.read().decode(errors="replace")
        print(f"\n{method} {path} -> {exc.code}\n{raw}", file=sys.stderr)
        raise SystemExit(1) from None


def main() -> int:
    status, payload = call("POST", "/auth/otp/request", {"phone": PHONE})
    challenge_id = payload["challenge_id"]
    print(f"1. otp requested                {status}")

    quoted = urllib.parse.quote(PHONE, safe="")
    status, payload = call("GET", f"/dev/otp/{quoted}")
    code = payload["code"]
    print(f"2. otp read from dev endpoint   {code}")

    status, payload = call(
        "POST", "/auth/otp/verify", {"challenge_id": challenge_id, "code": code}
    )
    token = payload["access_token"]
    role = (payload.get("user") or {}).get("role")
    print(f"3. verified                     role={role}")

    status, drivers = call("GET", "/admin/drivers?kyc_status=verified", token=token)
    print(f"4. GET /admin/drivers verified  {status}, {len(drivers)} rows")

    status, pending = call("GET", "/admin/drivers?kyc_status=pending", token=token)
    print(f"5. GET /admin/drivers pending   {status}, {len(pending)} rows")

    if role != "admin":
        print("\nFAIL: the account is not an admin", file=sys.stderr)
        return 1

    print("\nadmin demo account works")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
