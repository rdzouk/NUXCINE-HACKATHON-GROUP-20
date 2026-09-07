"""FastAPI application factory.

Middleware order is load-bearing and is documented inline. Starlette applies
middleware in reverse registration order, so the last one added is the
outermost. Getting this wrong means a rejected oversized body never gets a
request ID, or a timeout response ships without security headers.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.cache import close_redis
from app.config import settings
from app.db import dispose_engine
from app.errors.handlers import register_exception_handlers
from app.logging import configure_logging, get_logger
from app.middleware import (
    BodySizeLimitMiddleware,
    GlobalRateLimitMiddleware,
    RequestIdMiddleware,
    RequestTimeoutMiddleware,
    SecurityHeadersMiddleware,
)

API_PREFIX = "/api/v1"

DESCRIPTION = """
VORA backend. Smart mobility for the Cameroonian urban context.

**Contract status:** frozen as of Phase 0. Response shapes do not change
without an announced decision.

Two things differ from a generic ride-hailing API and are worth reading before
integrating:

* **Landmark-first geocoding.** `/places/search` resolves carrefours, stations,
  markets and quartiers, and reports which layer of the cascade produced each
  hit via `match_type`.
* **Corridor rides.** `mode=corridor` prices a seat on a shared route rather
  than exclusive hire of a vehicle.

**Errors.** Every non-2xx response is the same envelope: `{ "error": { "code",
"message", "details", "request_id" } }`. Codes are stable. Authorization
failures on ride-scoped routes return `404 RIDE_NOT_FOUND`, never `403`.

**Privacy.** No endpoint returns a counterparty's phone number in any state.
No health, biometric or other prohibited data category is stored; accessibility
is modelled as vehicle capability requirements.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    log = get_logger("vora.lifespan")
    log.info(
        "startup",
        app_env=settings.app_env,
        debug=settings.debug,
        docs_enabled=not settings.is_production,
    )
    yield
    await dispose_engine()
    await close_redis()
    log.info("shutdown")


def create_app() -> FastAPI:
    configure_logging(settings.log_level, json_output=not settings.debug)

    app = FastAPI(
        title="VORA API",
        version="0.1.0",
        description=DESCRIPTION,
        lifespan=lifespan,
        # Interactive docs are a development convenience. In production they
        # are an inventory of the attack surface, served for free.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    # Registered inner to outer. The request ID is added last so it is the
    # outermost layer and every response, including error responses produced by
    # the layers below it, carries the header.
    app.add_middleware(RequestTimeoutMiddleware, timeout_s=settings.request_timeout_s)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    # Outside the body limit and the timeout, so a client being throttled is
    # refused before the server spends a worker slot reading their body or
    # starting a timer for work it is not going to do.
    app.add_middleware(GlobalRateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        # Explicit allow-list. Settings rejects "*" at boot.
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "Accept-Language"],
        expose_headers=["X-Request-ID", "Retry-After"],
        max_age=600,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=API_PREFIX)

    return app


app = create_app()
