"""The rate limit that covers endpoints nobody remembered to decorate.

Phase 7. The per-endpoint limiters are tested where they live; this is about
the floor under everything else, and specifically about the three ways a
global limiter goes wrong: it throttles health checks, it buckets every user
behind one NAT together, or it fails closed and takes the API down when Redis
hiccups.
"""

from __future__ import annotations

import time

import pytest
from redis.exceptions import RedisError

from app.middleware import rate_limit as mw
from app.services import rate_limit as rl


class FakeRequest:
    """Only the two things `_identity` reads."""

    def __init__(self, auth: str | None = None, host: str | None = "10.0.0.1"):
        self.headers = {"authorization": auth} if auth else {}
        self.client = type("C", (), {"host": host})() if host else None
        self.url = type("U", (), {"path": "/api/v1/rides"})()
        self.method = "GET"


def test_health_is_exempt():
    """Throttling the endpoint a monitor polls gets you paged for the throttle
    rather than for the outage."""
    assert any("/health".startswith(p) for p in mw.EXEMPT_PREFIXES)


def test_docs_are_exempt_but_the_api_is_not():
    assert "/openapi.json" in mw.EXEMPT_PREFIXES
    assert not any("/api/v1/rides".startswith(p) for p in mw.EXEMPT_PREFIXES)


def test_anonymous_traffic_is_keyed_by_address():
    assert mw._identity(FakeRequest()) == "ip:10.0.0.1"


def test_a_client_with_no_address_still_gets_a_bucket():
    """Otherwise the key is None and the limiter throws on the request path."""
    assert mw._identity(FakeRequest(host=None)) == "ip:unknown"


def test_a_garbage_token_falls_back_to_the_address():
    """A forged token must not be a way to dodge the limit by being unparseable."""
    assert mw._identity(FakeRequest(auth="Bearer not-a-jwt")) == "ip:10.0.0.1"


def test_a_valid_token_is_keyed_by_user_not_address():
    """Two passengers behind one carrier NAT must not share a bucket.

    In Cameroon that NAT pool is a large fraction of the users, so IP-only
    keying would have one person's booking spree throttle a stranger.
    """
    import uuid

    from app.security.tokens import create_access_token

    user_id = uuid.uuid4()
    # Returns (token, ttl), not a bare token.
    token, _ = create_access_token(user_id=user_id, role="passenger")
    identity = mw._identity(FakeRequest(auth=f"Bearer {token}"))

    assert identity == f"u:{user_id}"
    assert identity != "ip:10.0.0.1"


def test_the_limit_is_generous_enough_for_a_real_client():
    """A passenger with the map open makes perhaps thirty requests a minute.
    A limit that catches them is a bug report, not a defence."""
    assert mw.GLOBAL_PER_IDENTITY.capacity >= 120
    assert mw.GLOBAL_PER_IDENTITY.per_seconds == 60


def test_the_breaker_lives_under_every_limit_not_just_this_one():
    """The Phase 7 degradation rehearsal is why this test exists.

    The breaker was in the middleware first. `/places/search` consults its own
    per-endpoint limiter as well, which dialled Redis independently, so a
    Redis outage still cost 6.4 seconds a request. A breaker that only covers
    one call site is not a breaker.
    """
    assert rl.BREAKER_COOLDOWN_S > 0
    assert not hasattr(mw, "BREAKER_COOLDOWN_S"), (
        "the middleware must not carry its own breaker again"
    )


@pytest.mark.asyncio
async def test_a_redis_outage_is_dialled_once_then_short_circuited():
    """Every caller after the first failure is refused without a socket call."""
    limiter = rl.RateLimiter()
    dialled = {"n": 0}

    async def exploding_load():
        dialled["n"] += 1
        raise RedisError("redis is down")

    limiter._load = exploding_load

    for _ in range(5):
        with pytest.raises(RedisError):
            await limiter.consume(rl.PLACES_SEARCH_PER_IP, "1.2.3.4")

    # Dialled once, refused five times.
    assert dialled["n"] == 1
    assert limiter.breaker_open


@pytest.mark.asyncio
async def test_an_open_breaker_still_raises_rather_than_allowing():
    """The half of this that protects money.

    Returning "allowed" while the breaker is open would silently convert every
    fail-closed limit into a fail-open one, and the OTP limiter is the only
    thing between us and an unbounded SMS bill.
    """
    limiter = rl.RateLimiter()
    limiter._skip_until = time.monotonic() + 60

    with pytest.raises(RedisError):
        await limiter.consume(rl.OTP_PER_PHONE_HOURLY, "+237600000001")


@pytest.mark.asyncio
async def test_the_middleware_lets_traffic_through_when_the_limiter_raises(
    monkeypatch,
):
    """Ordinary traffic is not worth taking the API down for."""

    async def exploding_consume(limit, identifier, **kwargs):
        raise RedisError("redis is down")

    monkeypatch.setattr(mw.limiter, "consume", exploding_consume)

    middleware = mw.GlobalRateLimitMiddleware(app=None)
    served = {"n": 0}

    async def call_next(request):
        served["n"] += 1
        return "served"

    for _ in range(5):
        assert await middleware.dispatch(FakeRequest(), call_next) == "served"

    assert served["n"] == 5
