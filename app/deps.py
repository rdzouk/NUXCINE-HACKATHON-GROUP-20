"""Shared request dependencies.

Authorization lives here, in one place, and is applied by declaring a
dependency on a route. It is never re-implemented inside a handler. That rule
is what Phase 3's `require_ride_participant` will extend to object-level access
(I1): per-handler checks miss one, and the one they miss is the vulnerability.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.models.user import Driver, User
from app.security.tokens import decode_access_token

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def client_ip(request: Request) -> str:
    """The caller's IP, for rate limiting.

    Trusts X-Forwarded-For only because uvicorn runs with --proxy-headers behind
    exactly one hop we control (Caddy, itself behind the tunnel). Starlette has
    already reduced the header to a single client host by the time it reaches
    here, so this is not parsing an attacker-supplied list.

    If this service is ever exposed without that proxy in front, this value
    becomes attacker-controlled and the per-IP limiter becomes decorative. The
    global circuit breaker exists partly to survive exactly that mistake.
    """
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


ClientIp = Annotated[str, Depends(client_ip)]


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise VoraError(ErrorCode.UNAUTHENTICATED)
    return token.strip()


async def get_current_user(request: Request, session: SessionDep) -> User:
    """Resolve the caller from their access token.

    The user is loaded from the database on every request rather than trusted
    from the token body. A JWT is a snapshot: a user suspended thirty seconds
    ago still holds a token that says otherwise, and honouring it for the
    remaining fifteen minutes is exactly the window an abuser needs.
    """
    payload = decode_access_token(_bearer_token(request))

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise VoraError(ErrorCode.INVALID_TOKEN) from exc

    user = await session.get(User, user_id)
    if user is None:
        raise VoraError(ErrorCode.INVALID_TOKEN)

    if user.status == "suspended":
        raise VoraError(ErrorCode.ACCOUNT_SUSPENDED)

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: str) -> Callable[..., Awaitable[User]]:
    """Restrict a route to one or more roles.

    Returns 403 FORBIDDEN_ROLE, which is correct here and is *not* a
    contradiction of the 404-not-403 rule: that rule protects the existence of
    a specific object. Which endpoints exist is public in openapi.json, so
    hiding a role boundary buys nothing and only confuses the client.
    """

    async def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise VoraError(
                ErrorCode.FORBIDDEN_ROLE, details={"required_roles": list(roles)}
            )
        return user

    return dependency


async def get_current_driver(
    session: SessionDep,
    user: Annotated[User, Depends(require_role("driver"))],
) -> Driver:
    """The driver record for the caller.

    A user with role=driver but no driver row is a broken registration rather
    than an authorization failure, but it is reported as FORBIDDEN_ROLE anyway:
    the caller cannot act as a driver either way, and the distinction is only
    useful to someone probing the system.
    """
    driver = user.driver
    if driver is None:
        raise VoraError(ErrorCode.FORBIDDEN_ROLE, details={"required_roles": ["driver"]})
    return driver


CurrentDriver = Annotated[Driver, Depends(get_current_driver)]
AdminUser = Annotated[User, Depends(require_role("admin"))]
