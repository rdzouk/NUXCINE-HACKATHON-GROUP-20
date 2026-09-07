"""Trip share links.

A passenger sends a link to a relative; the relative watches the car move
without an account. Highest safety value per hour of work in the build, and the
thing most likely to be used in earnest rather than only demonstrated.

**itsdangerous, not a JWT.** These are one-off signed blobs with a single
purpose and a short life. A JWT would bring claims, algorithms and a validation
surface we do not need, and it would be indistinguishable from an access token
to anybody reading logs. `URLSafeTimedSerializer` gives exactly signing plus
age, and the token is opaque and revocable because the database holds its hash.

**Two independent expiries, deliberately.** The signature carries a max age, so
a token is refused even if the row is gone. The row carries `expires_at` and
`revoked_at`, so a link can be killed before its signature lapses. Either alone
leaves a gap: signature-only cannot be revoked, row-only trusts an attacker not
to forge.

**Coarse until moving.** Before the trip starts, the location served is rounded
to roughly a few hundred metres. A link shared while waiting should not reveal
exactly which doorway somebody is standing in, and the precision that matters
to a worried relative is "the car is on Avenue Kennedy", not a street number.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors.codes import ErrorCode
from app.errors.envelope import VoraError
from app.logging import get_logger
from app.models.ride import Ride
from app.models.safety import RideShareToken
from app.models.user import Driver, User, Vehicle
from app.schemas.ride import RideStatus
from app.schemas.share import (
    ShareLocation,
    SharePrecision,
    ShareVehicle,
    ShareView,
)

logger = get_logger("vora.sharing")

SHARE_SALT = "vora-ride-share"

# Long enough to cover a trip and a worried relative watching after it, short
# enough that a forwarded link does not become permanent access.
SHARE_TTL_S = 4 * 3600

# Roughly 300 m at this latitude. Enough to say which quartier and which road,
# not enough to say which doorway.
COARSE_DECIMALS = 3

# Statuses in which there is anything to watch.
VIEWABLE = frozenset(
    {
        RideStatus.ACCEPTED,
        RideStatus.ARRIVING,
        RideStatus.ARRIVED,
        RideStatus.IN_PROGRESS,
        RideStatus.COMPLETED,
    }
)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        settings.share_token_secret.get_secret_value(), salt=SHARE_SALT
    )


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class ShareLink:
    token: str
    url: str
    expires_at: datetime


async def mint_share_link(
    session: AsyncSession, *, ride: Ride, created_by: uuid.UUID
) -> ShareLink:
    """Create a share link for a ride.

    Revokes any existing live link for the same ride first. A passenger who
    shares twice means "this is the link now", and leaving the previous one
    working would quietly widen who can watch.
    """
    now = datetime.now(UTC)

    await session.execute(
        text(
            "UPDATE ride_share_tokens SET revoked_at = now() "
            "WHERE ride_id = :ride_id AND revoked_at IS NULL"
        ),
        {"ride_id": ride.id},
    )

    # Server entropy inside the signed payload, so two links minted in the same
    # second for the same ride are still different tokens.
    nonce = secrets.token_urlsafe(16)
    token = _serializer().dumps({"ride_id": str(ride.id), "n": nonce})
    expires_at = now + timedelta(seconds=SHARE_TTL_S)

    session.add(
        RideShareToken(
            ride_id=ride.id,
            token_hash=_hash(token),
            expires_at=expires_at,
            created_by=created_by,
        )
    )
    await session.flush()

    base = settings.public_base_url.rstrip("/")
    logger.info("share_link_minted", ride_id=str(ride.id), expires_at=str(expires_at))

    return ShareLink(
        token=token, url=f"{base}/api/v1/share/{token}", expires_at=expires_at
    )


async def revoke_all(session: AsyncSession, *, ride_id: uuid.UUID) -> int:
    result = await session.execute(
        text(
            "UPDATE ride_share_tokens SET revoked_at = now() "
            "WHERE ride_id = :ride_id AND revoked_at IS NULL"
        ),
        {"ride_id": ride_id},
    )
    logger.info("share_links_revoked", ride_id=str(ride_id), count=result.rowcount)
    return result.rowcount


async def resolve_token(session: AsyncSession, token: str) -> Ride:
    """Verify a share token and return its ride.

    Every failure answers 404, never 403 or 410. Distinguishing "expired" from
    "revoked" from "never existed" tells whoever is probing which links were
    ever real, and a share link is precisely the kind of URL that gets
    forwarded, scraped and guessed at.
    """
    try:
        payload = _serializer().loads(token, max_age=SHARE_TTL_S)
    except SignatureExpired as exc:
        raise VoraError(ErrorCode.SHARE_TOKEN_EXPIRED) from exc
    except (BadSignature, ValueError) as exc:
        raise VoraError(ErrorCode.SHARE_TOKEN_INVALID) from exc

    try:
        ride_id = uuid.UUID(payload["ride_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise VoraError(ErrorCode.SHARE_TOKEN_INVALID) from exc

    # The signature proves we minted it. The row proves it has not been killed.
    row = (
        await session.execute(
            select(RideShareToken).where(RideShareToken.token_hash == _hash(token))
        )
    ).scalar_one_or_none()

    if row is None or row.revoked_at is not None:
        raise VoraError(ErrorCode.SHARE_TOKEN_INVALID)

    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        raise VoraError(ErrorCode.SHARE_TOKEN_EXPIRED)

    ride = await session.get(Ride, ride_id)
    if ride is None or RideStatus(ride.status) not in VIEWABLE:
        raise VoraError(ErrorCode.SHARE_TOKEN_INVALID)

    row.view_count += 1
    row.last_viewed_at = datetime.now(UTC)

    return ride


def coarsen(lat: float, lng: float) -> tuple[float, float]:
    """Round a position to roughly a few hundred metres."""
    return round(lat, COARSE_DECIMALS), round(lng, COARSE_DECIMALS)


def precision_for(status: RideStatus) -> SharePrecision:
    """Precise only once the trip is moving.

    Before that the passenger is standing still somewhere, and a forwarded link
    would reveal exactly where they are waiting. Once the car is in motion the
    precise position is what makes the feature useful, and the passenger is no
    longer a stationary target.
    """
    return (
        SharePrecision.PRECISE
        if status is RideStatus.IN_PROGRESS
        else SharePrecision.COARSE
    )


async def current_location(
    session: AsyncSession, ride: Ride
) -> tuple[float, float, datetime] | None:
    """The latest accepted trace point, or None.

    Accepted only: a share viewer must never be shown a position the system
    itself rejected as implausible.
    """
    row = (
        await session.execute(
            text(
                "SELECT ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng, "
                "recorded_at FROM ride_traces "
                "WHERE ride_id = :ride_id AND NOT rejected "
                "ORDER BY seq DESC LIMIT 1"
            ),
            {"ride_id": ride.id},
        )
    ).first()

    if row is None:
        return None
    return row.lat, row.lng, row.recorded_at


async def build_share_view(session: AsyncSession, ride: Ride) -> ShareView:
    """Everything a share viewer is allowed to see, and nothing else.

    One function, called by both the HTTP route and the socket. They served
    the same thing assembled twice before, which is the arrangement where a
    field added carefully to one is forgotten in the other and a share link
    quietly starts leaking something six weeks later.

    Absent by construction, because `ShareView` has nowhere to put them:
    passenger identity, fare, PIN, phone, trace history, the driver's full
    name.
    """
    status = RideStatus(ride.status)

    driver_first_name = "Chauffeur"
    vehicle_summary = ShareVehicle(make="", model="", color="", plate="")

    if ride.driver_id is not None:
        driver = await session.get(Driver, ride.driver_id)
        if driver is not None:
            driver_user = await session.get(User, driver.user_id)
            if driver_user and driver_user.display_name:
                # First name only, exactly as the passenger sees it. A share
                # viewer is not entitled to more than the passenger.
                driver_first_name = driver_user.display_name.strip().split()[0]

    if ride.vehicle_id is not None:
        vehicle = await session.get(Vehicle, ride.vehicle_id)
        if vehicle is not None:
            # The plate is the point: it is what lets somebody identify the car
            # if they need to. It is also already visible to anyone standing on
            # the street beside it.
            vehicle_summary = ShareVehicle(
                make=vehicle.make,
                model=vehicle.model,
                color=vehicle.color,
                plate=vehicle.plate,
            )

    location = None
    fix = await current_location(session, ride)
    if fix is not None:
        lat, lng, recorded_at = fix
        precision = precision_for(status)
        if precision is SharePrecision.COARSE:
            lat, lng = coarsen(lat, lng)
        location = ShareLocation(
            lat=lat, lng=lng, precision=precision, updated_at=recorded_at
        )

    expires_at = await session.scalar(
        text(
            "SELECT max(expires_at) FROM ride_share_tokens "
            "WHERE ride_id = :ride_id AND revoked_at IS NULL"
        ),
        {"ride_id": ride.id},
    )

    return ShareView(
        ride_status=status,
        driver_first_name=driver_first_name,
        vehicle=vehicle_summary,
        current_location=location,
        eta_s=None,
        dropoff_label=ride.dropoff_label,
        expires_at=expires_at,
    )
