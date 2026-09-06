"""Assembles the full §6 surface under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
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
