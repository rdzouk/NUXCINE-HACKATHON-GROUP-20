"""Assembles the full §6 surface under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    dev,
    driver,
    health,
    me,
    places,
    quotes,
    rides,
    share,
    ws,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(places.router)
api_router.include_router(quotes.router)
api_router.include_router(rides.router)
api_router.include_router(driver.router)
api_router.include_router(share.router)
api_router.include_router(admin.router)
api_router.include_router(ws.router)

# Development-only routes. Registered conditionally rather than gated inside
# each handler, so on a production deployment the paths do not exist at all and
# never reach openapi.json. `POST /dev/simulate-driver` fabricates GPS points
# for a ride; that must not be reachable anywhere real.
if dev.is_enabled():
    api_router.include_router(dev.router)
