"""Redis client.

Used in Phase 1 for OTP throttling and the hand-written token buckets, in
Phase 2 for burning quote jtis. Phase 0 only needs it to be reachable.
"""

from __future__ import annotations

import redis.asyncio as aioredis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.config import settings

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """The shared Redis client.

    Timeouts and retries are tuned rather than left at defaults, because the
    OTP path fails *closed* when Redis is unreachable: a blip there is an auth
    outage, not a degraded experience.

    An earlier 2-second socket timeout with no retry turned a single slow read
    on a loaded host into a 503 on login. The fix is not to fail open, which
    would make a Redis outage an uncapped SMS spend. It is to distinguish a
    blip from an outage: retry twice with backoff, and only then give up.

    Worst case here is roughly connect + three reads, which stays inside the
    15-second global request timeout, so a genuine outage still fails closed
    promptly rather than holding workers open.
    """
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=3,
            retry=Retry(ExponentialBackoff(base=0.05, cap=0.5), retries=2),
            retry_on_error=[RedisConnectionError, RedisTimeoutError],
            health_check_interval=30,
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None


async def probe() -> tuple[bool, str]:
    client = get_redis()
    pong = await client.ping()
    if not pong:
        raise RuntimeError("redis did not respond to PING")
    info = await client.info("server")
    return True, f"redis {info.get('redis_version', 'unknown')}"
