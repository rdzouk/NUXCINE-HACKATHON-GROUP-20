"""GET /health.

Probes each dependency rather than returning a static 200. A health endpoint
that cannot fail tells you nothing, and during the Phase 7 degradation
rehearsal this is the thing that has to notice OSRM being killed.

Returns 200 while the API itself is serving, with per-component status in the
body. A hard 503 is reserved for the case where the database is unreachable,
because at that point nothing the API does can succeed.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Response

from app import cache, db
from app.config import settings
from app.schemas.common import HealthComponent, HealthResponse

router = APIRouter(tags=["meta"])

VERSION = "0.1.0"


class _NotConfigured(Exception):
    """A dependency that is intentionally absent, not one that has failed."""


async def _timed(name: str, coro) -> tuple[str, HealthComponent]:
    started = time.perf_counter()
    try:
        _, detail = await coro
    except _NotConfigured as exc:
        return name, HealthComponent(status="not_configured", detail=str(exc))
    except Exception as exc:
        return name, HealthComponent(
            status="down",
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            # Exception text here is operational, not user-facing, and the
            # endpoint is not a secret-bearing surface.
            detail=f"{type(exc).__name__}: {exc}"[:200],
        )
    return name, HealthComponent(
        status="ok",
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
        detail=detail,
    )


async def _probe_osrm() -> tuple[bool, str]:
    if not settings.osrm_enabled:
        # Distinct from "down". Routing is deliberately absent until Phase 2
        # prepares the extract, and a health check should say which it is.
        raise _NotConfigured("routing not enabled until Phase 2")
    async with httpx.AsyncClient(timeout=settings.osrm_timeout_s) as client:
        # Yaounde city centre to a point a few hundred metres away. Cheap, and
        # it proves the routing graph is loaded rather than just the port open.
        url = (
            f"{settings.osrm_base_url}/route/v1/driving/"
            "11.5021,3.8480;11.5100,3.8550?overview=false"
        )
        response = await client.get(url)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != "Ok":
            raise RuntimeError(f"osrm returned code={payload.get('code')}")
        return True, "routing graph loaded"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Dependency health",
    description=(
        "Probes each dependency. Component status is one of ok, degraded, down "
        "or not_configured. Returns 503 only when the database is unreachable, "
        "since at that point nothing the API does can succeed."
    ),
)
async def health(response: Response) -> HealthResponse:
    results = await asyncio.gather(
        _timed("database", db.probe()),
        _timed("redis", cache.probe()),
        _timed("osrm", _probe_osrm()),
    )
    components = dict(results)

    if components["database"].status == "down":
        overall = "down"
        response.status_code = 503
    elif any(c.status == "down" for c in components.values()):
        overall = "degraded"
    else:
        overall = "ok"

    return HealthResponse(
        status=overall,
        version=VERSION,
        app_env=settings.app_env,
        time=datetime.now(UTC),
        components=components,
    )
