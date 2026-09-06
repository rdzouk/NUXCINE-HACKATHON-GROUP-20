#!/usr/bin/env python3
"""Export openapi.json.

Committed to the repo and handed to mobile. Two things this does beyond
calling app.openapi():

1. Injects the WebSocket frame models. FastAPI does not describe WebSocket
   routes in OpenAPI, so without this the socket vocabulary in
   app/schemas/ws.py would be invisible to a generated client, and Phase 4
   would be free to invent a different one.

2. Runs with --check in CI mode, which fails if the committed file has drifted
   from the code. A stale contract file is worse than none: mobile trusts it.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.main import app  # noqa: E402
from app.schemas import ws as ws_schemas  # noqa: E402

OUTPUT = REPO_ROOT / "openapi.json"

WS_MODELS = [
    ws_schemas.AuthFrame,
    ws_schemas.LocationFrame,
    ws_schemas.PongFrame,
    ws_schemas.ReadyFrame,
    ws_schemas.RideUpdateFrame,
    ws_schemas.DriverLocationFrame,
    ws_schemas.MessageFrame,
    ws_schemas.PingFrame,
    ws_schemas.ErrorFrame,
]

WS_DOC = """
WebSocket endpoints are not describable in OpenAPI, so they are documented here.

    WS /api/v1/ws/driver      driver JWT
                              inbound:  LocationFrame, PongFrame
                              outbound: ReadyFrame, RideOffer, RideUpdateFrame,
                                        PingFrame, ErrorFrame

    WS /api/v1/ws/passenger   passenger JWT
                              outbound: ReadyFrame, RideUpdateFrame,
                                        DriverLocationFrame, MessageFrame,
                                        PingFrame, ErrorFrame

    WS /api/v1/ws/share/{token}   no auth, token-scoped
                              outbound: share_update, PingFrame, ErrorFrame

Authenticate with an Authorization header on connect, or with a first frame of
type `auth`. Never with a query string: query strings are recorded in access
logs, proxy logs and browser history.

Server pings every 20 s and drops a connection that misses two. Inbound
location frames are capped at one per 2 s per connection.
"""


def build_spec() -> dict:
    spec = app.openapi()

    schemas = spec.setdefault("components", {}).setdefault("schemas", {})
    for model in WS_MODELS:
        model_schema = model.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )
        # Nested models come back under $defs; hoist them so the refs resolve.
        for name, definition in model_schema.pop("$defs", {}).items():
            schemas.setdefault(name, definition)
        schemas[model.__name__] = model_schema

    spec["info"]["description"] = spec["info"].get("description", "") + "\n" + WS_DOC
    return spec


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the committed file is out of date. Does not write.",
    )
    args = parser.parse_args()

    rendered = json.dumps(build_spec(), indent=2, ensure_ascii=False) + "\n"

    if args.check:
        if not OUTPUT.exists():
            print("openapi.json is missing", file=sys.stderr)
            return 1
        if OUTPUT.read_text(encoding="utf-8") != rendered:
            print(
                "openapi.json is out of date. Run scripts/export_openapi.py.",
                file=sys.stderr,
            )
            return 1
        print("openapi.json is current")
        return 0

    OUTPUT.write_text(rendered, encoding="utf-8", newline="\n")
    paths = len(build_spec()["paths"])
    print(f"wrote {OUTPUT.relative_to(REPO_ROOT)} ({paths} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
