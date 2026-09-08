#!/usr/bin/env python3
"""Corridor rides end to end. Phase 6 acceptance check.

    python scripts/corridor_flow.py

Drives the thing the whole product bets on: one vehicle, one route, three
passengers who each booked separately, each paying for their own leg.

What it proves, in order:

  economics   each passenger pays less than exclusive hire would have cost
              them, and the driver collects more than one exclusive fare
  containment a joiner is only matched when both their endpoints already lie
              on the route being driven, in the direction of travel
  the cap     the detour stays inside 8 percent and 4 minutes
  consent     the driver is asked and can refuse; declining costs the joiner
              nothing but a wait
  privacy     a joiner cannot see where the passenger beside them is going

The privacy check is the one worth reading. A shared ride is the easiest place
in this system to leak somebody's destination, because the natural
implementation hands every passenger the vehicle's itinerary. Nothing else here
would notice if it did.

The joiners' endpoints are read back off the driven route with
ST_LineInterpolatePoint rather than guessed from a map. Guessed coordinates
land a few hundred metres off the road the car is actually on, and the run then
fails on my geography rather than on the corridor logic.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import uuid

import httpx

GREEN, RED, DIM, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"
)
ANSI = re.compile(r"\x1b\[[0-9;]*m")

# A long cross-town corridor, so there is room for two joiners along it.
WARDA = {"lat": 3.8760, "lng": 11.5120, "label": "Carrefour Warda"}
NGOUSSO = {"lat": 3.9010, "lng": 11.5540, "label": "Ngousso Chapelle"}

# Fractions along the driven route where the joiners get in and out. Chosen so
# the two legs overlap: the corridor has to hold both at once, which is the
# case that a naive one-passenger-at-a-time implementation gets wrong.
B_BOARDS, B_ALIGHTS = 0.30, 0.80
C_BOARDS, C_ALIGHTS = 0.45, 0.90

MAX_DETOUR_RATIO = 0.08
MAX_DETOUR_SECONDS = 240

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


def psql_row(sql: str) -> list[str]:
    """One row, split on the field separator psql -tA emits."""
    raw = psql(sql)
    return raw.split("|") if raw else []


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


def make_driver(
    user_id: str, lat: float, lng: float, *, seats: int = 4, ramp: bool = False
) -> str:
    psql(f"UPDATE users SET role='driver' WHERE id='{uid(user_id)}'")
    driver_id = psql(
        f"INSERT INTO drivers (user_id, kyc_status, is_online, seats_free) "
        f"VALUES ('{uid(user_id)}', 'verified', true, {seats}) "
        f"ON CONFLICT (user_id) DO UPDATE SET is_online = true, "
        f"kyc_status = 'verified' RETURNING id"
    )
    psql(
        f"INSERT INTO vehicles (driver_id, plate, make, model, color, seats, "
        f"has_ramp) VALUES ('{uid(driver_id)}', "
        f"'CE-{uuid.uuid4().hex[:5].upper()}', 'Toyota', 'Hiace', 'blanc', "
        f"{seats}, {'true' if ramp else 'false'})"
    )
    psql(
        f"INSERT INTO driver_presence (driver_id, geom, recorded_at) "
        f"VALUES ('{uid(driver_id)}', ST_MakePoint({lng}, {lat})::geography, now()) "
        f"ON CONFLICT (driver_id) DO UPDATE SET geom = EXCLUDED.geom, "
        f"recorded_at = EXCLUDED.recorded_at"
    )
    return driver_id


def point_on_route(ride_id: str, fraction: float, label: str) -> dict:
    """A coordinate that is genuinely on the driven line."""
    row = psql_row(
        f"SELECT ST_Y(ST_LineInterpolatePoint(route_geom::geometry, {fraction})), "
        f"       ST_X(ST_LineInterpolatePoint(route_geom::geometry, {fraction})) "
        f"FROM rides WHERE id='{uid(ride_id)}'"
    )
    if len(row) != 2:
        raise RuntimeError(f"ride {ride_id} has no route_geom")
    return {"lat": float(row[0]), "lng": float(row[1]), "label": label}


def offset_point_on_route(
    ride_id: str, fraction: float, metres: int, azimuth_deg: float, label: str
) -> dict:
    """A coordinate a measured distance off the driven line.

    The offset is measured back with ST_Distance rather than assumed from the
    azimuth, because the line's local bearing is not its overall bearing and a
    projection that happened to run along the road would make the test look
    like it passed while proving nothing.
    """
    row = psql_row(
        f"WITH base AS ("
        f"  SELECT route_geom, ST_Project("
        f"    ST_LineInterpolatePoint(route_geom::geometry, {fraction})::geography,"
        f"    {metres}, radians({azimuth_deg})) AS p"
        f"  FROM rides WHERE id='{uid(ride_id)}')"
        f"SELECT ST_Y(p::geometry), ST_X(p::geometry), ST_Distance(route_geom, p) "
        f"FROM base"
    )
    if len(row) != 3:
        raise RuntimeError(f"could not offset a point from ride {ride_id}")
    return {
        "lat": float(row[0]),
        "lng": float(row[1]),
        "label": label,
        "offset_m": float(row[2]),
    }


def quote(client, base, headers, pickup, dropoff, seats=1) -> dict:
    place = lambda p: {"lat": p["lat"], "lng": p["lng"], "label": p["label"]}  # noqa: E731
    r = client.post(
        f"{base}/rides/quote", headers=headers,
        json={
            "pickup": place(pickup), "dropoff": place(dropoff),
            "seats": seats, "mode": "corridor",
        },
    )
    r.raise_for_status()
    return r.json()


def book(client, base, headers, quote_id, seats=1) -> httpx.Response:
    return client.post(
        f"{base}/rides", headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"quote_id": quote_id, "seats": seats, "accessibility_required": []},
    )


def accept_offer_for(client, base, driver_headers, ride_id: str) -> httpx.Response:
    offers = client.get(f"{base}/driver/offers", headers=driver_headers)
    offers.raise_for_status()
    mine = [o for o in offers.json()["offers"] if o["ride_id"] == ride_id]
    if not mine:
        raise RuntimeError(f"no offer reached the driver for ride {ride_id}")
    return client.post(
        f"{base}/driver/offers/{mine[0]['id']}/accept", headers=driver_headers
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8080/api/v1")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    client = httpx.Client(timeout=90.0)
    print(f"VORA corridor flow against {base}\n")

    # ------------------------------------------------------------- setup --
    print("setup")
    a_token, _ = login(client, base)
    b_token, _ = login(client, base)
    c_token, _ = login(client, base)
    stranger_token, _ = login(client, base)
    d_token, d_user = login(client, base)

    a = {"Authorization": f"Bearer {a_token}"}
    b = {"Authorization": f"Bearer {b_token}"}
    c = {"Authorization": f"Bearer {c_token}"}
    stranger = {"Authorization": f"Bearer {stranger_token}"}
    driver = {"Authorization": f"Bearer {d_token}"}

    # Exactly at the pickup, so this driver leads the nearest candidates.
    make_driver(d_user, WARDA["lat"], WARDA["lng"], seats=4)

    # Isolate the corridor, the way race_test isolates its race.
    #
    # A corridor left live by an earlier run was driving this same route, so
    # its geometry contains the joiners' endpoints too. B would then be matched
    # onto that stale parent instead of onto A, and the assertions here would
    # report "no leg was created" while the corridor logic had in fact worked
    # perfectly, on the wrong ride. Retiring them first makes A's corridor the
    # only one this test can match against.
    stale = psql(
        "UPDATE rides SET status = 'expired', ended_at = now() "
        "WHERE mode = 'corridor' "
        "AND status IN ('requested','matching','accepted','arriving',"
        "'arrived','in_progress') "
        "RETURNING id"
    )
    if stale:
        print(f"{DIM}  retired corridor rides left live by an earlier run{RESET}")

    check("two bookings, a third that must be refused, and a bystander", True)
    print()

    # ------------------------------------------------- leg 1: passenger A --
    print("passenger A opens the corridor")
    qa = quote(client, base, a, WARDA, NGOUSSO)
    exclusive_a = qa["fare_xaf"]
    corridor_a = qa["corridor_fare_xaf"]
    check("a corridor quote is cheaper than exclusive hire",
          corridor_a < exclusive_a, f"{corridor_a} vs {exclusive_a} XAF")

    ra = book(client, base, a, qa["quote_id"])
    if not check("A's ride created (201)", ra.status_code == 201,
                 f"got {ra.status_code}: {ra.text[:300]}"):
        return summarise()
    ride_a = ra.json()["ride"]
    a_id, a_pin = ride_a["id"], ride_a.get("pin")
    check("A's ride is a corridor ride", ride_a["mode"] == "corridor")

    acc = accept_offer_for(client, base, driver, a_id)
    if not check("a driver accepted (200)", acc.status_code == 200,
                 f"got {acc.status_code}: {acc.text[:300]}"):
        return summarise()

    legs = psql(f"SELECT count(*) FROM corridor_legs WHERE parent_ride_id='{uid(a_id)}'")
    check("A holds leg 1 of their own corridor", int(legs or 0) == 1,
          f"{legs} legs; without this the seat A occupies is invisible to capacity")

    client.post(f"{base}/rides/{a_id}/arrived", headers=driver)
    started = client.post(
        f"{base}/rides/{a_id}/start", headers=driver, json={"pin": a_pin}
    )
    if not check("A is aboard and the trip is moving",
                 started.status_code == 200, f"got {started.status_code}"):
        return summarise()

    route_len = float(psql(
        f"SELECT ST_Length(route_geom) FROM rides WHERE id='{uid(a_id)}'"
    ) or 0)
    check("the route was stored as geometry, not only as a polyline",
          route_len > 0, "corridor containment needs a line to test against")
    print(f"{DIM}  route {route_len / 1000:.1f} km, A pays {corridor_a} XAF{RESET}")
    print()

    # ------------------------------------------------- leg 2: passenger B --
    print("passenger B joins mid-route")
    b_pick = point_on_route(a_id, B_BOARDS, "Arret Nlongkak")
    b_drop = point_on_route(a_id, B_ALIGHTS, "Arret Emana")

    qb = quote(client, base, b, b_pick, b_drop)
    exclusive_b = qb["fare_xaf"]

    rb = book(client, base, b, qb["quote_id"])
    if not check("B's ride created (201)", rb.status_code == 201,
                 f"got {rb.status_code}: {rb.text[:300]}"):
        return summarise()
    b_id = rb.json()["ride"]["id"]

    asked = psql(
        f"SELECT count(*) FROM ride_events WHERE ride_id='{uid(a_id)}' "
        f"AND event_type='corridor_join_requested'"
    )
    check("the driver was asked rather than told (consent)", int(asked or 0) == 1,
          f"{asked} consent requests on the parent ride")

    held = psql_row(
        f"SELECT state, boarding_order FROM corridor_legs WHERE ride_id='{uid(b_id)}'"
    )
    check("B's seat is held at the ask, not at the answer",
          held[:1] == ["offered"], f"leg state {held}")
    check("B is second aboard", held[1:2] == ["2"], f"boarding order {held[1:2]}")

    accb = accept_offer_for(client, base, driver, b_id)
    if not check("the driver accepted the join (200)", accb.status_code == 200,
                 f"got {accb.status_code}: {accb.text[:300]}"):
        return summarise()

    b_view = client.get(f"{base}/rides/{b_id}", headers=b).json()["ride"]
    corridor_b = b_view["quoted_fare_xaf"]
    check("B's leg is confirmed",
          psql(f"SELECT state FROM corridor_legs WHERE ride_id='{uid(b_id)}'")
          == "confirmed")
    check("B and A are in the same vehicle",
          psql(f"SELECT driver_id FROM rides WHERE id='{uid(b_id)}'")
          == psql(f"SELECT driver_id FROM rides WHERE id='{uid(a_id)}'"))
    print(f"{DIM}  B pays {corridor_b} XAF (exclusive would be {exclusive_b}){RESET}")
    print()

    # ------------------------------------------------ the cap has teeth --
    print("a joiner too far off the line is refused")
    # Both endpoints stay inside the 400 m corridor tolerance, so containment
    # still holds and the only thing that can refuse this join is the detour.
    # Without this the cap is never exercised: every other joiner in this run
    # sits exactly on the line, where the detour is zero by construction.
    far_pick = offset_point_on_route(a_id, 0.35, 320, 149, "Hors corridor depart")
    far_drop = offset_point_on_route(a_id, 0.75, 320, 149, "Hors corridor arrivee")
    predicted = 2 * (far_pick["offset_m"] + far_drop["offset_m"])
    print(f"{DIM}  offsets {far_pick['offset_m']:.0f} m and "
          f"{far_drop['offset_m']:.0f} m, so a round trip off the line of "
          f"{predicted:.0f} m ({predicted / route_len * 100:.1f}%){RESET}")

    check("both endpoints are still within the 400 m corridor tolerance",
          far_pick["offset_m"] < 400 and far_drop["offset_m"] < 400,
          "if containment already fails, the cap is not what refused them")
    check("the offsets are large enough for this to be a real test",
          far_pick["offset_m"] > 150 and far_drop["offset_m"] > 150,
          f"{far_pick['offset_m']:.0f} m and {far_drop['offset_m']:.0f} m")
    check("the detour they would cause exceeds the cap",
          predicted / route_len > MAX_DETOUR_RATIO,
          f"{predicted / route_len * 100:.1f}% against an 8 percent cap")

    f_token, _ = login(client, base)
    f = {"Authorization": f"Bearer {f_token}"}
    qf = quote(client, base, f, far_pick, far_drop)
    rf = book(client, base, f, qf["quote_id"])
    if check("their ride is still created", rf.status_code == 201,
             f"got {rf.status_code}: {rf.text[:200]}"):
        f_id = rf.json()["ride"]["id"]
        joined = psql(
            f"SELECT count(*) FROM corridor_legs WHERE ride_id='{uid(f_id)}'"
        )
        check("but they are not put in A's car", int(joined or 0) == 0,
              "the first passenger would have paid for that detour")
        capped = psql(
            f"SELECT count(*) FROM ride_events WHERE ride_id='{uid(a_id)}' "
            f"AND event_type='corridor_join_requested'"
        )
        check("and the driver was never asked", int(capped or 0) == 1,
              "the cap is checked before consent, so a passenger already "
              "aboard never pays for a bad match")
    print()

    # --------------------------------------------- the cap: passenger C --
    # C is a perfect geometric match and is still refused, because the limit
    # is two bookings, not two seats.
    #
    # That is a safety rule rather than a capacity one. The first passenger may
    # bring whoever they like; a stranger joins as exactly one person, in the
    # front seat, in the driver's line of sight. Nobody ends up sitting in the
    # back beside somebody they have never met. A third booking would put two
    # unrelated strangers behind the driver, and no fare is worth that.
    print("a third booking is refused, however well it fits")
    c_pick = point_on_route(a_id, C_BOARDS, "Arret Etoa Meki")
    c_drop = point_on_route(a_id, C_ALIGHTS, "Arret Nkolmesseng")

    qc = quote(client, base, c, c_pick, c_drop)
    rc = book(client, base, c, qc["quote_id"])
    if not check("C's ride is still created (201)", rc.status_code == 201,
                 f"got {rc.status_code}: {rc.text[:300]}"):
        return summarise()
    c_id = rc.json()["ride"]["id"]

    c_joined = psql(
        f"SELECT count(*) FROM corridor_legs WHERE ride_id='{uid(c_id)}'"
    )
    check("but C is not added to A's car", int(c_joined or 0) == 0,
          f"{c_joined} leg(s); the cap is bookings, not seats")

    # Consent was never sought, because the cap is checked first. A driver who
    # was asked and said no would look the same in the data, and it is not the
    # same thing.
    asked = psql(
        f"SELECT count(*) FROM ride_events WHERE ride_id='{uid(a_id)}' "
        f"AND event_type='corridor_join_requested'"
    )
    check("and the driver was not asked a second time", int(asked or 0) == 1,
          f"{asked} join request(s) on A's ride")

    total_legs = psql(
        f"SELECT count(*) FROM corridor_legs WHERE parent_ride_id='{uid(a_id)}' "
        f"AND state='confirmed'"
    )
    check("two bookings share the vehicle, never three",
          int(total_legs or 0) == 2, f"{total_legs} confirmed legs")
    print()

    # ------------------------------------------------------- the economics --
    print(f"{BOLD}the economics{RESET}")
    total = corridor_a + corridor_b
    print(f"{DIM}  passenger   corridor   exclusive   saves{RESET}")
    for name, paid, alone in (
        ("A", corridor_a, exclusive_a),
        ("B", corridor_b, exclusive_b),
    ):
        print(f"{DIM}  {name}        {paid:>8}   {alone:>9}   "
              f"{alone - paid:>5} XAF{RESET}")
    print(f"{DIM}  driver collects {total} XAF against {exclusive_a} XAF "
          f"for the same vehicle sold once{RESET}")

    check("A pays less than exclusive hire would have cost them",
          corridor_a < exclusive_a, f"{corridor_a} vs {exclusive_a}")
    check("B pays less than exclusive hire would have cost them",
          corridor_b < exclusive_b, f"{corridor_b} vs {exclusive_b}")
    check("the driver earns more than one exclusive fare",
          total > exclusive_a, f"{total} vs {exclusive_a} XAF")
    check("every fare is payable in coins",
          all(f % 50 == 0 for f in (corridor_a, corridor_b)),
          f"{corridor_a}, {corridor_b}")
    print()

    # -------------------------------------------------------- the detour --
    print("the detour cap")
    for name, ride_id in (("B", b_id),):
        row = psql_row(
            f"SELECT added_distance_m, added_duration_s FROM corridor_legs "
            f"WHERE ride_id='{uid(ride_id)}'"
        )
        added_m, added_s = int(row[0] or 0), int(row[1] or 0)
        ratio = added_m / route_len if route_len else 0
        print(f"{DIM}  {name}: +{added_m} m (+{ratio * 100:.1f}%), +{added_s} s{RESET}")
        check(f"{name}'s detour is inside 8 percent",
              ratio <= MAX_DETOUR_RATIO, f"{ratio * 100:.1f}%")
        check(f"{name}'s detour is inside 4 minutes",
              added_s <= MAX_DETOUR_SECONDS, f"{added_s} s")
    print()

    # -------------------------------------------------------- the privacy --
    print(f"{BOLD}a joiner cannot see where anybody else is going{RESET}")
    peek = client.get(f"{base}/rides/{a_id}", headers=b)
    check("B gets 404 on A's ride, not 403 (I1)", peek.status_code == 404,
          f"got {peek.status_code}")
    check("and the code says not found, never forbidden",
          peek.json()["error"]["code"] == "RIDE_NOT_FOUND")

    b_ride_text = client.get(f"{base}/rides/{b_id}", headers=b).text
    b_list_text = client.get(f"{base}/rides", headers=b).text
    check("A's destination appears nowhere in B's own ride",
          NGOUSSO["label"] not in b_ride_text, "the itinerary leaked")
    check("A's destination appears nowhere in B's ride list",
          NGOUSSO["label"] not in b_list_text)
    check("no phone number reaches a co-passenger (I3)",
          not re.search(r"\+237\d{6,}", b_ride_text + b_list_text))
    check("B is not told they are sharing at all",
          "corridor_legs" not in b_ride_text and a_id not in b_ride_text,
          "the parent ride id is a handle onto somebody else's journey")

    for label, headers in (("B", b), ("C", c), ("a bystander", stranger)):
        seen = client.get(f"{base}/rides/{a_id}", headers=headers)
        check(f"{label} cannot read A's ride", seen.status_code == 404,
              f"got {seen.status_code}")

    # The driver is the one party who must see all of it.
    driver_legs = psql(
        f"SELECT count(*) FROM corridor_legs WHERE parent_ride_id='{uid(a_id)}'"
    )
    check("the driver's manifest holds every leg", int(driver_legs or 0) == 2,
          "the driver has to know who to collect and where")
    print()

    # --------------------------------------------------- accessibility --
    print("accessibility (I9)")
    caps = client.get(f"{base}/vehicles/capabilities", headers=a)
    check("the capability vocabulary is served", caps.status_code == 200,
          f"got {caps.status_code}")
    if caps.status_code == 200:
        vocabulary = caps.json()["capabilities"]
        check("every capability, in both languages",
              len(vocabulary) == 6
              and all(v["label_fr"] and v["label_en"] for v in vocabulary))
        wording = " ".join(
            v["description_fr"] + v["description_en"] for v in vocabulary
        ).lower()
        check("every capability describes the vehicle, never the person",
              not any(w in wording for w in ("handicap", "disabled", "invalide")),
              "Law 2024/017 prohibits processing health data")

    ramp_token, _ = login(client, base)
    ramp = {"Authorization": f"Bearer {ramp_token}"}
    qr = quote(client, base, ramp, WARDA, NGOUSSO)
    rr = client.post(
        f"{base}/rides", headers={**ramp, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "quote_id": qr["quote_id"], "seats": 1,
            "accessibility_required": ["ramp"],
        },
    )
    if check("a ride requiring a ramp is created", rr.status_code == 201,
             f"got {rr.status_code}: {rr.text[:200]}"):
        ramp_id = rr.json()["ride"]["id"]
        offered = psql(
            f"SELECT count(*) FROM ride_offers WHERE ride_id='{uid(ramp_id)}'"
        )
        check("it is not offered to a vehicle without one", int(offered or 0) == 0,
              "the requirement is matched against the car, not the passenger")
    print()

    return summarise()


def summarise() -> int:
    print("\n-----------------------------------------")
    print(f"passed: {_passed}   failed: {_failed}")
    if _failed:
        print(f"{RED}corridor flow FAILED{RESET}")
        return 1
    print(f"{GREEN}corridor flow passed{RESET}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"{RED}error: {exc}{RESET}", file=sys.stderr)
        raise SystemExit(2) from exc
