"""GPS plausibility filter.

The trace is the source of truth for the fare (I2), which makes it the single
most attractive thing in the system to forge. A driver running a patched client
can claim any sequence of points they like, and every one of them turns into
money. So each point is checked before it counts.

**Rejected points are stored, not dropped.** A discarded point is a forgery
attempt nobody can prove happened. A row with `rejected = true` and a reason is
evidence: it survives into `ride_events` and into an incident snapshot, and it
is what turns "the fare looks wrong" into "here is where they teleported".

The thresholds are deliberately loose. This filter is not trying to catch a
clever attacker who moves plausibly; it is trying to make the *cheap* attacks
useless while never rejecting a real journey. A false rejection costs a real
driver real money, so every bound below is set well outside anything a car in
Yaounde traffic can do.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.services.routing import haversine_m

# 150 km/h. Well above anything achievable on these roads, so a point that
# implies more than this was not driven to.
MAX_SPEED_MPS = 150 / 3.6

# A phone reporting worse than this is not telling us where it is. Common
# indoors and in dense urban canyons, which is why it is flagged rather than
# treated as an attack.
MAX_ACCURACY_M = 100.0

# Below this, GPS jitter alone moves a stationary phone. Two points inside it
# are not evidence of movement, and the implied speed between them is noise.
MIN_MOVEMENT_M = 5.0

# A single jump larger than this is a teleport regardless of the time gap: no
# continuous journey produces one, and it is the signature of a replayed or
# hand-edited trace.
MAX_JUMP_M = 5_000.0

# Clocks drift, and a client whose clock is a little ahead is not an attacker.
# Anything beyond this is either a broken device or a deliberate reorder.
CLOCK_SKEW_TOLERANCE = timedelta(seconds=5)


class RejectReason(StrEnum):
    IMPOSSIBLE_SPEED = "impossible_speed"
    POOR_ACCURACY = "poor_accuracy"
    NON_MONOTONIC = "non_monotonic_timestamp"
    TELEPORT = "teleport_jump"
    FUTURE_TIMESTAMP = "future_timestamp"
    OUT_OF_RANGE = "coordinates_out_of_range"


@dataclass(frozen=True)
class Point:
    lat: float
    lng: float
    recorded_at: datetime
    accuracy_m: float | None = None
    speed_mps: float | None = None


@dataclass(frozen=True)
class Verdict:
    accepted: bool
    reason: RejectReason | None = None
    implied_speed_mps: float | None = None
    distance_m: float | None = None

    @property
    def rejected(self) -> bool:
        return not self.accepted


def check(point: Point, previous: Point | None, *, now: datetime) -> Verdict:
    """Judge one point against its predecessor.

    Order matters. The cheapest and most certain checks run first, so a
    malformed point never reaches the arithmetic, and the reason recorded is
    the most specific one that applies rather than whichever fired first by
    accident.
    """
    # Not a coordinate at all. Schema validation catches this at the HTTP
    # boundary, but a WebSocket frame is a different door into the same table.
    if not (-90 <= point.lat <= 90) or not (-180 <= point.lng <= 180):
        return Verdict(False, RejectReason.OUT_OF_RANGE)

    # A timestamp in the future is either a broken clock or an attempt to
    # reorder the trace so a later teleport looks like an earlier one.
    if point.recorded_at > now + CLOCK_SKEW_TOLERANCE:
        return Verdict(False, RejectReason.FUTURE_TIMESTAMP)

    if point.accuracy_m is not None and point.accuracy_m > MAX_ACCURACY_M:
        return Verdict(False, RejectReason.POOR_ACCURACY)

    if previous is None:
        # Nothing to compare against. The first point of a trace is accepted on
        # its own merits, which is why the checks above are not relative.
        return Verdict(True)

    if point.recorded_at <= previous.recorded_at:
        # Equal timestamps count as non-monotonic: two points at the same
        # instant imply infinite speed, and allowing them lets an attacker
        # stack distance without any elapsed time to pay for it.
        return Verdict(False, RejectReason.NON_MONOTONIC)

    distance = haversine_m(previous.lat, previous.lng, point.lat, point.lng)

    if distance > MAX_JUMP_M:
        return Verdict(False, RejectReason.TELEPORT, distance_m=distance)

    elapsed = (point.recorded_at - previous.recorded_at).total_seconds()
    implied = distance / elapsed if elapsed > 0 else float("inf")

    # Below the jitter floor, the implied speed is meaningless: a stationary
    # phone drifting three metres over half a second reports 6 m/s.
    if distance >= MIN_MOVEMENT_M and implied > MAX_SPEED_MPS:
        return Verdict(
            False,
            RejectReason.IMPOSSIBLE_SPEED,
            implied_speed_mps=implied,
            distance_m=distance,
        )

    return Verdict(True, implied_speed_mps=implied, distance_m=distance)
