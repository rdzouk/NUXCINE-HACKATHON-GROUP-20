"""Redis token buckets.

Written by hand rather than using slowapi, because the OTP endpoint needs three
*independent* layers evaluated on one request: per phone, per IP, and a global
circuit breaker. slowapi expresses one key per limiter and cannot compose them
into a single decision with a single most-restrictive answer.

Why this matters more than it looks. An unrated OTP endpoint is an SMS-pumping
machine: an attacker requests thousands of codes to premium-rate numbers they
control, the operator bills us, and they take a share of the revenue. This is
actively exploited against real products, not a theoretical concern, and it
empties a prepaid SMS balance in minutes.

Each layer stops a different attack, which is why one is not enough:

  per phone    one victim being spammed with codes, or one number farmed
  per IP       one host walking many numbers
  global       a distributed run from many hosts against many numbers, where
               every per-phone and per-IP bucket looks perfectly innocent

The algorithm is a token bucket implemented as a Lua script so that read,
refill, test and write happen atomically inside Redis. Doing it as separate
GET/SET round trips is a time-of-check-to-time-of-use race: N concurrent
requests all read the same count and all conclude they are within budget.

Fail-closed on Redis errors for the OTP path: if the limiter cannot be
consulted, sending is refused. The alternative is that a Redis outage becomes
an uncapped SMS spend.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from redis.exceptions import RedisError

from app.cache import get_redis
from app.logging import get_logger

logger = get_logger("vora.ratelimit")

# Atomic refill-and-consume. KEYS[1] is the bucket.
# ARGV: capacity, refill_per_second, now, requested tokens.
# Returns {allowed, tokens_remaining, retry_after_seconds}.
_TOKEN_BUCKET_LUA = """
local key      = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate     = tonumber(ARGV[2])
local now      = tonumber(ARGV[3])
local want     = tonumber(ARGV[4])

local state  = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(state[1])
local ts     = tonumber(state[2])

if tokens == nil then
  tokens = capacity
  ts = now
end

-- Refill for elapsed time, capped at capacity.
local elapsed = math.max(0, now - ts)
tokens = math.min(capacity, tokens + (elapsed * rate))

local allowed = 0
local retry_after = 0

if tokens >= want then
  allowed = 1
  tokens = tokens - want
else
  -- Seconds until enough tokens have accrued for this request.
  retry_after = math.ceil((want - tokens) / rate)
end

redis.call('HSET', key, 'tokens', tokens, 'ts', now)
-- Expire a full refill after last use so idle keys do not accumulate.
redis.call('EXPIRE', key, math.ceil(capacity / rate) + 60)

return {allowed, math.floor(tokens), retry_after}
"""


@dataclass(frozen=True)
class Limit:
    """One bucket. `capacity` requests, refilled over `per_seconds`."""

    name: str
    capacity: int
    per_seconds: int

    @property
    def refill_rate(self) -> float:
        return self.capacity / self.per_seconds


@dataclass(frozen=True)
class LimitDecision:
    allowed: bool
    limit_name: str | None = None
    retry_after_s: int = 0
    remaining: int | None = None


# §Phase 1: per-phone 3/hour and 10/day, per-IP 20/hour, plus a global breaker.
OTP_PER_PHONE_HOURLY = Limit("otp_phone_hourly", capacity=3, per_seconds=3600)
OTP_PER_PHONE_DAILY = Limit("otp_phone_daily", capacity=10, per_seconds=86400)
OTP_PER_IP_HOURLY = Limit("otp_ip_hourly", capacity=20, per_seconds=3600)

# The circuit breaker. Sized well above legitimate demo and pilot traffic, so
# tripping it means something is wrong rather than that we are popular. When it
# trips, OTP sending halts for everyone: refusing service beats an unbounded
# bill, and a human decides when to resume.
OTP_GLOBAL_BREAKER = Limit("otp_global", capacity=200, per_seconds=3600)

# Verification attempts are limited separately from sending. Without this, the
# per-challenge attempt counter is the only thing standing between an attacker
# and the 10k keyspace, and they can simply request a new challenge each time.
OTP_VERIFY_PER_IP = Limit("otp_verify_ip", capacity=30, per_seconds=3600)


class RateLimiter:
    def __init__(self) -> None:
        self._script = None

    async def _load(self):
        if self._script is None:
            self._script = get_redis().register_script(_TOKEN_BUCKET_LUA)
        return self._script

    async def consume(
        self, limit: Limit, identifier: str, *, tokens: int = 1
    ) -> LimitDecision:
        script = await self._load()
        key = f"rl:{limit.name}:{identifier}"
        try:
            allowed, remaining, retry_after = await script(
                keys=[key],
                args=[limit.capacity, limit.refill_rate, time.time(), tokens],
            )
        except RedisError:
            logger.exception("rate_limiter_unavailable", limit=limit.name)
            raise
        return LimitDecision(
            allowed=bool(allowed),
            limit_name=None if allowed else limit.name,
            retry_after_s=int(retry_after),
            remaining=int(remaining),
        )

    async def check_all(
        self, checks: list[tuple[Limit, str]]
    ) -> LimitDecision:
        """Evaluate every layer and return the first refusal.

        Deliberately consumes from each bucket in order and stops at the first
        rejection, so a request that is refused by the per-phone limit does not
        also burn global capacity. The cost is that a request refused by a
        later layer has already consumed from earlier ones, which is the
        conservative direction to be wrong in.
        """
        for limit, identifier in checks:
            decision = await self.consume(limit, identifier)
            if not decision.allowed:
                return decision
        return LimitDecision(allowed=True)


limiter = RateLimiter()


# /places/search is unauthenticated-adjacent and database-heavy: several index
# scans plus trigram similarity per call. Generous enough for real typing (a
# search fires per keystroke pause) and low enough to stop a scraper.
PLACES_SEARCH_PER_IP = Limit("places_search_ip", capacity=120, per_seconds=60)

# Quoting hits the routing engine, so it is capped separately and lower.
QUOTE_PER_USER = Limit("quote_user", capacity=30, per_seconds=60)
