#!/usr/bin/env python3
"""Generate a Bruno collection that walks the demo, in order.

    python scripts/export_bruno.py

Deliberately **not** a dump of all 33 endpoints from the OpenAPI schema. That
already exists as `openapi.json`, it opens in any viewer, and a flat list of
every route sorted alphabetically tells a juror nothing about how the system is
used. This is the §8 demo script as runnable requests, numbered in the order
somebody would actually fire them, so a juror can follow the story and poke at
it themselves.

Bruno rather than Postman: the collection is plain text in the repo, so it
diffs, reviews and survives without an account or a cloud sync.

Chained with variables. `auth.otp.verify` writes the access token into the
collection's runtime vars, the quote writes `quote_id`, ride creation writes
`ride_id` and the PIN. That is what makes it runnable end to end rather than a
set of requests that each need a token pasted in by hand.
"""

from __future__ import annotations

import argparse
import pathlib
import textwrap

COLLECTION = "vora-api"

# (order, folder, name, method, path, body, docs, post_response_script)
Request = tuple[int, str, str, str, str, str | None, str, str | None]

REQUESTS: list[Request] = [
    (
        1, "00 health", "health", "get", "/health", None,
        "Liveness plus the state of every dependency. Never rate limited: "
        "throttling the endpoint a monitor polls gets you paged for the "
        "throttle rather than the outage.",
        None,
    ),
    (
        2, "01 landmarks", "search warda", "get",
        "/api/v1/places/search?q=warda", None,
        "**Bet 1.** Ask anyone in Yaounde for an address and they name a "
        "carrefour. `match_type` says how the match was made: `exact_alias` "
        "means somebody typed what people actually say. Fuzzy matching runs "
        "in the Postgres index with trigrams and unaccent, never in Python.",
        None,
    ),
    (
        3, "01 landmarks", "search misspelled", "get",
        "/api/v1/places/search?q=warda%20carefour", None,
        "The same place, misspelled and with the words the other way round. "
        "This is the request that shows the gazetteer is doing real work.",
        None,
    ),
    (
        4, "02 auth", "request otp", "post", "/api/v1/auth/otp/request",
        '{\n  "phone": "+237600000001"\n}',
        "Three per phone per hour, ten per day, twenty per IP per hour, "
        "behind a global circuit breaker. The limiter fails **closed** here: "
        "sending SMS costs money, so an outage must not become an unbounded "
        "bill.\n\nIn development the code is printed to the API logs:\n\n"
        "    docker compose logs --tail 20 api | grep otp_console",
        'bru.setVar("challenge_id", res.body.challenge_id);',
    ),
    (
        5, "02 auth", "verify otp", "post", "/api/v1/auth/otp/verify",
        '{\n  "challenge_id": "{{challenge_id}}",\n  "code": "0000"\n}',
        "Replace `code` with the one from the logs. The code is hashed with "
        "argon2 at 32 MiB, not compared as a string: a four-digit secret is "
        "only safe if guessing it is expensive.\n\nWrites `access_token` for "
        "every request below.",
        'bru.setVar("access_token", res.body.access_token);\n'
        'bru.setVar("refresh_token", res.body.refresh_token);',
    ),
    (
        6, "02 auth", "me", "get", "/api/v1/me", None,
        "The caller's own profile. Accessibility here is stored as vehicle "
        "requirements, never as anything about the person (I9).",
        None,
    ),
    (
        7, "03 quote", "quote exclusive", "post", "/api/v1/rides/quote",
        '{\n  "pickup": {"lat": 3.8760, "lng": 11.5120, '
        '"label": "Carrefour Warda"},\n'
        '  "dropoff": {"lat": 3.8660, "lng": 11.5170, '
        '"label": "Marche Central"},\n'
        '  "seats": 1,\n  "mode": "exclusive"\n}',
        "The fare is computed on the server and returned **signed**. The "
        "response carries both the exclusive fare and the per-seat corridor "
        "fare so the client can show the choice.\n\nFares round to 50 XAF "
        "because people pay in coins here.",
        'bru.setVar("quote_id", res.body.quote_id);',
    ),
    (
        8, "04 ride", "create ride", "post", "/api/v1/rides",
        '{\n  "quote_id": "{{quote_id}}",\n  "seats": 1,\n'
        '  "accessibility_required": []\n}',
        "**I2.** The fare is re-derived from the signed quote, never read "
        "from this body. Nothing a client sends influences the price.\n\n"
        "**I8.** The `Idempotency-Key` header is required. Mobile networks "
        "here drop and retry; without it one tap creates two rides. Send the "
        "same key twice and you get 200 with the original ride, not a "
        "second one.\n\nThe quote is single use: presenting it again is 409.",
        'bru.setVar("ride_id", res.body.ride.id);\n'
        'bru.setVar("pin", res.body.ride.pin);',
    ),
    (
        9, "04 ride", "get ride", "get", "/api/v1/rides/{{ride_id}}", None,
        "**I1.** Try this with another user's ride id: it answers 404, never "
        "403. A 403 confirms the row exists, which is how an enumeration "
        "attack learns which ids are real.\n\n**I3.** No counterparty phone "
        "number appears in any payload, in either direction.",
        None,
    ),
    (
        10, "05 driver", "offers", "get", "/api/v1/driver/offers", None,
        "Needs a driver token whose KYC is verified. Offers arrive in "
        "widening waves; an offer for a ride somebody else already took is "
        "filtered in the query, not swept later.",
        None,
    ),
    (
        11, "06 safety", "share trip", "post",
        "/api/v1/rides/{{ride_id}}/share", None,
        "Mints a signed, expiring, revocable link. Open it in a private "
        "window: location is visible, identity and fare and phone are not.\n\n"
        "Position stays coarse, about 300 m, until the ride is `in_progress`, "
        "so a link shared while waiting does not reveal which doorway "
        "somebody is standing in.",
        'bru.setVar("share_token", res.body.token);',
    ),
    (
        12, "06 safety", "view shared trip", "get",
        "/api/v1/share/{{share_token}}", None,
        "No authentication. Invalid, expired and revoked tokens all answer "
        "**404 alike**: telling them apart would reveal which links were "
        "ever real.",
        None,
    ),
    (
        13, "07 corridor", "quote corridor", "post", "/api/v1/rides/quote",
        '{\n  "pickup": {"lat": 3.8760, "lng": 11.5120, '
        '"label": "Carrefour Warda"},\n'
        '  "dropoff": {"lat": 3.9010, "lng": 11.5540, '
        '"label": "Ngousso Chapelle"},\n'
        '  "seats": 1,\n  "mode": "corridor"\n}',
        "**Bet 2.** Each passenger pays for their own leg at 0.68 of the "
        "exclusive rate, measured along the route actually driven.\n\n"
        "Three passengers each pay less than exclusive hire while the driver "
        "collects more than one exclusive fare, because the vehicle is not "
        "being sold to one person. Verified end to end by "
        "`scripts/corridor_flow.py`.",
        'bru.setVar("corridor_quote_id", res.body.quote_id);',
    ),
    (
        14, "08 accessibility", "capabilities", "get",
        "/api/v1/vehicles/capabilities", None,
        "**I9.** Every capability describes the **vehicle**, never a person: "
        "\"Vehicule equipe d'une rampe\", not \"pour personnes "
        "handicapees\".\n\nLaw No. 2024/017 prohibits processing health "
        "data. \"This passenger uses a wheelchair\" is health data; \"this "
        "trip needs a ramp\" is a logistics requirement. A unit test asserts "
        "the wording, because that distinction is exactly what a "
        "well-meaning copy edit erases.",
        None,
    ),
]

HEADER_AUTH = "  Authorization: Bearer {{access_token}}"


def bru_for(request: Request, seq: int) -> str:
    _order, _folder, name, method, path, body, docs, script = request

    parts = [
        "meta {",
        f"  name: {name}",
        "  type: http",
        f"  seq: {seq}",
        "}",
        "",
        f"{method} {{",
        f"  url: {{{{baseUrl}}}}{path}",
        f"  body: {'json' if body else 'none'}",
        "  auth: none",
        "}",
        "",
    ]

    headers = []
    # /health and the public share view take no credentials, and the OTP pair
    # is what mints them in the first place.
    if not path.startswith(("/health", "/api/v1/share/", "/api/v1/auth/otp")):
        headers.append(HEADER_AUTH)
    if body:
        headers.append("  Content-Type: application/json")
    if path == "/api/v1/rides" and method == "post":
        headers.append("  Idempotency-Key: {{$guid}}")

    if headers:
        parts += ["headers {", *headers, "}", ""]

    if body:
        parts += ["body:json {", textwrap.indent(body, "  "), "}", ""]

    if script:
        parts += [
            "script:post-response {",
            textwrap.indent(script, "  "),
            "}",
            "",
        ]

    parts += ["docs {", textwrap.indent(docs, "  "), "}", ""]
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="bruno")
    args = parser.parse_args()

    root = pathlib.Path(args.out)
    root.mkdir(parents=True, exist_ok=True)

    (root / "bruno.json").write_text(
        '{\n'
        '  "version": "1",\n'
        f'  "name": "{COLLECTION}",\n'
        '  "type": "collection",\n'
        '  "ignore": ["node_modules", ".git"]\n'
        '}\n',
        newline="\n",
    )

    (root / "collection.bru").write_text(
        "auth {\n  mode: none\n}\n\n"
        "docs {\n"
        "  The VORA demo, as runnable requests in the order you would fire\n"
        "  them. Start at 02 auth, read the OTP out of the API logs, then\n"
        "  work down: everything below reuses the token automatically.\n"
        "\n"
        "      docker compose logs --tail 20 api | grep otp_console\n"
        "\n"
        "  Set the environment to `local` before running anything.\n"
        "}\n",
        newline="\n",
    )

    env_dir = root / "environments"
    env_dir.mkdir(exist_ok=True)
    for env_name, base in (
        ("local", "http://localhost:8080"),
        ("tunnel", "https://REPLACE-ME.trycloudflare.com"),
    ):
        (env_dir / f"{env_name}.bru").write_text(
            "vars {\n"
            f"  baseUrl: {base}\n"
            "}\n",
            newline="\n",
        )

    written = 0
    for request in sorted(REQUESTS):
        folder = root / request[1]
        folder.mkdir(exist_ok=True)

        # folder.bru gives Bruno the display order, otherwise it sorts the
        # folders alphabetically and the story falls apart.
        (folder / "folder.bru").write_text(
            "meta {\n"
            f"  name: {request[1]}\n"
            f"  seq: {request[0]}\n"
            "}\n",
            newline="\n",
        )

        filename = request[2].replace(" ", "-") + ".bru"
        (folder / filename).write_text(bru_for(request, request[0]), newline="\n")
        written += 1

    print(f"wrote {written} requests to {root}/")
    print("open it in Bruno, select the `local` environment, start at 02 auth")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
