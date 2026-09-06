"""Database engine and session dependency.

Phase 0 defines no tables. This module exists so that /health can prove the
database is reachable and correctly extended, and so Phase 1 has a session
dependency to build on rather than inventing one under time pressure.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            pool_size=10,
            max_overflow=5,
            pool_pre_ping=True,
            # Statement logging would put pickup coordinates and phone numbers
            # into stdout. Off in every environment, not just production.
            echo=False,
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def probe() -> tuple[bool, str]:
    """Health probe. Reports the PostGIS version, not just connectivity.

    A reachable Postgres without PostGIS would pass a naive SELECT 1 and then
    fail every geo query in the app, which is a worse failure than being down.
    """
    async with get_sessionmaker()() as session:
        result = await session.execute(text("SELECT PostGIS_Version()"))
        version = result.scalar_one()
        return True, f"postgis {version}"
