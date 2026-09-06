"""Security response headers.

HSTS is emitted unconditionally because every real deployment path for this
service terminates TLS in front of the app (Cloudflare Tunnel edge, or Caddy
on a VPS). A plain-HTTP localhost run ignores the header, so there is no
scenario where sending it locks anyone out.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# The API returns JSON only, so it gets the tightest policy that exists.
JSON_CSP = (
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)

# Swagger UI and ReDoc pull their assets from jsDelivr. This policy exists so
# the docs page works in development; docs are disabled entirely in production.
HTML_CSP = (
    "default-src 'none'; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "img-src 'self' https://fastapi.tiangolo.com data:; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)

BASE_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for key, value in BASE_HEADERS.items():
            response.headers.setdefault(key, value)
        content_type = response.headers.get("content-type", "")
        csp = HTML_CSP if content_type.startswith("text/html") else JSON_CSP
        response.headers.setdefault("Content-Security-Policy", csp)
        return response
