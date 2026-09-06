"""Routing, behind an interface with a fallback that cannot fail.

The interface exists for one concrete reason: **the demo must not die because a
container fell over.** OSRM is self-hosted, which removes an API key, a quota
and a third-party outage from the live demo, and adds one failure mode we own.
So every call has a timeout, one retry, and a straight-line estimate behind it.

The fallback multiplies great-circle distance by 1.35. That constant is the
usual ratio of road distance to straight-line distance in a dense street
network; it is an approximation and is labelled as one. Every response carries
`routing_source`, so a client can tell the user the estimate is approximate
rather than silently showing a wrong number as if it were surveyed. Quietly
degrading is worse than degrading visibly.

`RoutingProvider` is not speculative abstraction. It is the seam a hosted
directions API drops into if self-hosting turns out to be wrong, and it is the
thing that makes the fallback testable without breaking the container.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.config import settings
from app.logging import get_logger

logger = get_logger("vora.routing")

# Road distance over great-circle distance in a dense network. An estimate.
HAVERSINE_ROAD_FACTOR = 1.35
# Average city speed in Yaounde, used only by the fallback to derive a duration.
FALLBACK_SPEED_KMH = 22.0

EARTH_RADIUS_M = 6_371_000.0

SOURCE_OSRM = "osrm"
SOURCE_FALLBACK = "haversine_fallback"


@dataclass(frozen=True)
class Route:
    distance_m: int
    duration_s: int
    polyline: str
    source: str

    @property
    def is_estimate(self) -> bool:
        return self.source == SOURCE_FALLBACK


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def encode_polyline(points: list[tuple[float, float]], precision: int = 5) -> str:
    """Encode (lat, lng) pairs as a Google-format polyline.

    Written out rather than pulled from a library because the fallback needs to
    emit a two-point line and nothing else, and the client already decodes this
    format for OSRM's output. One format on the wire, whatever the source.
    """
    factor = 10**precision
    out: list[str] = []
    prev_lat = prev_lng = 0

    for lat, lng in points:
        ilat, ilng = round(lat * factor), round(lng * factor)
        for delta in (ilat - prev_lat, ilng - prev_lng):
            value = ~(delta << 1) if delta < 0 else (delta << 1)
            while value >= 0x20:
                out.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            out.append(chr(value + 63))
        prev_lat, prev_lng = ilat, ilng

    return "".join(out)


class RoutingProvider(ABC):
    @abstractmethod
    async def route(
        self, pickup: tuple[float, float], dropoff: tuple[float, float]
    ) -> Route: ...

    @abstractmethod
    async def distance_matrix(
        self, origin: tuple[float, float], destinations: list[tuple[float, float]]
    ) -> list[float]: ...


class HaversineFallbackProvider(RoutingProvider):
    """Straight-line estimate. Always available, never accurate.

    Not a stub: this is what serves the demo if OSRM is down, so it returns a
    real polyline and a plausible duration rather than raising.
    """

    async def route(
        self, pickup: tuple[float, float], dropoff: tuple[float, float]
    ) -> Route:
        straight = haversine_m(*pickup, *dropoff)
        distance = straight * HAVERSINE_ROAD_FACTOR
        duration = (distance / 1000.0) / FALLBACK_SPEED_KMH * 3600.0
        return Route(
            distance_m=int(round(distance)),
            duration_s=int(round(duration)),
            polyline=encode_polyline([pickup, dropoff]),
            source=SOURCE_FALLBACK,
        )

    async def distance_matrix(
        self, origin: tuple[float, float], destinations: list[tuple[float, float]]
    ) -> list[float]:
        return [
            haversine_m(*origin, *d) * HAVERSINE_ROAD_FACTOR for d in destinations
        ]


class OsrmRoutingProvider(RoutingProvider):
    """Self-hosted OSRM, with the fallback behind it.

    Never raises for a routing failure. A quote that cannot be priced is a
    booking that cannot happen, and on a bad network that would be most of
    them. It degrades to the estimate and says so through `routing_source`.
    """

    def __init__(self, fallback: RoutingProvider | None = None) -> None:
        self._fallback = fallback or HaversineFallbackProvider()
        self._base = settings.osrm_base_url.rstrip("/")
        self._timeout = settings.osrm_timeout_s

    async def _get(self, url: str) -> dict | None:
        """One timed attempt plus one retry. Returns None if OSRM is unusable.

        Two attempts, not five. A passenger is watching a spinner, and the
        fallback is good enough to book against; spending ten seconds failing
        is worse than answering in two with an approximation.
        """
        for attempt in (1, 2):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    payload = response.json()
                if payload.get("code") == "Ok":
                    return payload
                logger.warning("osrm_non_ok", code=payload.get("code"), attempt=attempt)
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning(
                    "osrm_request_failed", attempt=attempt, error=type(exc).__name__
                )
        return None

    async def route(
        self, pickup: tuple[float, float], dropoff: tuple[float, float]
    ) -> Route:
        # OSRM takes lng,lat. Getting this backwards routes you to the Gulf of
        # Guinea, which is the classic version of this bug.
        coords = f"{pickup[1]},{pickup[0]};{dropoff[1]},{dropoff[0]}"
        url = f"{self._base}/route/v1/driving/{coords}?overview=full&geometries=polyline"

        payload = await self._get(url)
        if payload is None or not payload.get("routes"):
            logger.warning("osrm_unavailable_using_fallback")
            return await self._fallback.route(pickup, dropoff)

        best = payload["routes"][0]
        return Route(
            distance_m=int(round(best["distance"])),
            duration_s=int(round(best["duration"])),
            polyline=best.get("geometry", encode_polyline([pickup, dropoff])),
            source=SOURCE_OSRM,
        )

    async def distance_matrix(
        self, origin: tuple[float, float], destinations: list[tuple[float, float]]
    ) -> list[float]:
        if not destinations:
            return []

        points = ";".join(f"{lng},{lat}" for lat, lng in [origin, *destinations])
        url = f"{self._base}/table/v1/driving/{points}?sources=0&annotations=distance"

        payload = await self._get(url)
        if payload is None or not payload.get("distances"):
            return await self._fallback.distance_matrix(origin, destinations)

        row = payload["distances"][0][1:]
        # OSRM returns null for an unreachable pair. Fall back per entry rather
        # than discarding the whole matrix.
        return [
            float(value)
            if value is not None
            else haversine_m(*origin, *destinations[i]) * HAVERSINE_ROAD_FACTOR
            for i, value in enumerate(row)
        ]


_provider: RoutingProvider | None = None


def get_routing_provider() -> RoutingProvider:
    global _provider
    if _provider is None:
        _provider = OsrmRoutingProvider()
    return _provider


def set_routing_provider(provider: RoutingProvider) -> None:
    """Injection point for tests and for swapping in a hosted API."""
    global _provider
    _provider = provider
