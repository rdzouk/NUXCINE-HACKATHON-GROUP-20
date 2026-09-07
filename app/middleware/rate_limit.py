"""A rate limit on every endpoint, not just the ones somebody remembered.

Phase 1 limited OTP, Phase 2 places and quotes, Phase 5 the share view. That
leaves ride creation, every state transition, the driver's offer list,
messages, SOS and KYC uploads with no ceiling at all. Adding a decorator to
each of those is how you end up with a ceiling on twenty-nine endpoints and a
hole in the thirtieth, because the protection lives in a place a new handler
does not automatically inherit.

This is a floor under the whole surface. The specific limits stay: they are
much tighter and they exist for reasons this one cannot express, such as three
OTPs per phone per hour. Nothing here replaces them.

**Keyed by user, falling back to IP.** The token is decoded locally with no
database hit, purely to read `sub`. Keying only by IP would put an entire
office or a whole mobile carrier's NAT pool into one bucket, which in Cameroon
is a large fraction of the users; keying only by user leaves unauthenticated
traffic unbounded.

**Fails open, deliberately, and this is the one place that is right.** The OTP
limiter fails closed because sending an SMS costs money and an outage there is
an unbounded bill. This one governs ordinary reads and writes, so failing
closed on a Redis blip would take the entire API down to prevent nothing. The
tighter limits that guard the expensive paths keep their own fail-closed
behaviour.

`/health` is exempt. Throttling the endpoint a monitor polls is how you get
paged for the throttle rather than the outage.

**Failing open has to be fast, or it is not failing open.** A limiter that
waits for a Redis connection to time out before allowing the request adds that
timeout to *every* request, which turns a Redis blip into a site-wide latency
collapse: worse than the abuse the limiter exists to prevent.

The breaker that prevents this lives in `RateLimiter` itself, not here. It was
here first, and the Phase 7 degradation rehearsal showed why that was the wrong
place: `/places/search` consults its own per-endpoint limiter as well, which
dialled Redis independently and still cost 6.4 seconds a request during an
outage. One breaker underneath every limit is the only version that holds.
"""

from __future__ import annotations

from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.errors.codes import DEFAULT_STATUS, ErrorCode
from app.i18n import message_for, negotiate_language
from app.logging import get_logger, request_id_ctx
from app.services.rate_limit import Limit, limiter

logger = get_logger("vora.rate_limit.global")

# Sized well above what any real client does and well below what a script does.
# A passenger booking a ride makes perhaps thirty requests in a minute with the
# map open; nothing legitimate approaches this.
GLOBAL_PER_IDENTITY = Limit("global_identity", capacity=240, per_seconds=60)

# Paths that must never be throttled.
EXEMPT_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc")


def _identity(request: Request) -> str:
    """Who to charge this request to.

    The bearer token is decoded rather than verified against the database. A
    forged token yields an identity that is not a real user, which is fine:
    the point is to bucket traffic, and anything that fails verification is
    refused by the endpoint a moment later anyway.
    """
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        from app.errors.envelope import VoraError
        from app.security.tokens import decode_access_token

        try:
            claims = decode_access_token(auth.split(" ", 1)[1].strip())
            subject = claims.get("sub")
            if subject:
                return f"u:{subject}"
        except (VoraError, ValueError, KeyError):
            # Not a usable token. Fall through to the address it came from.
            pass

    client = request.client
    return f"ip:{client.host if client else 'unknown'}"


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES):
            return await call_next(request)

        try:
            decision = await limiter.consume(GLOBAL_PER_IDENTITY, _identity(request))
        except RedisError:
            # See the module docstring. Governing ordinary traffic is not worth
            # taking the API down for. The limiter's own breaker is what keeps
            # this path fast during a sustained outage.
            logger.warning("global_rate_limiter_unavailable_failing_open")
            return await call_next(request)

        if decision.allowed:
            return await call_next(request)

        code = ErrorCode.RATE_LIMITED
        retry_after = max(decision.retry_after_s, 1)
        logger.warning("global_rate_limited", path=path, method=request.method)

        lang = negotiate_language(request.headers.get("accept-language"))
        return JSONResponse(
            status_code=DEFAULT_STATUS[code],
            content={
                "error": {
                    "code": code.value,
                    "message": message_for(code, lang),
                    "details": {"retry_after_s": retry_after},
                    "request_id": request_id_ctx.get(),
                }
            },
            headers={"Retry-After": str(retry_after)},
        )
