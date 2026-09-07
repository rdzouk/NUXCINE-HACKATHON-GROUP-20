"""Ride, offer, event and trace tables. The spine of the system.

Four things here are load-bearing and should not be simplified away.

**`ride_events` is append-only, enforced by a trigger.** Not by convention and
not only by role grants, because the application connects as the table owner
and an owner can work around grants. The trigger fires for everyone. This table
is the evidence layer that safety claims, fare disputes and breach notification
under Law 2024/017 all rest on; a mutable audit log is not an audit log.

**`ride_traces` keeps rejected points.** A GPS point that fails the plausibility
filter is stored with `rejected = true` rather than discarded. Deleting it
destroys the evidence that somebody tried to forge a fare, which is exactly the
thing worth keeping.

**One live ride per passenger, enforced by a partial unique index.** Not by a
check in the handler, because two concurrent requests both pass a handler check
and the database is the only place that can serialise them.

**`ride_offers` exists** because §6 addresses `/driver/offers/{id}` and §5 had
no table behind it. Without it, decline is a no-op and wave 2 re-offers a ride
to the driver who just refused it.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidPkMixin

ride_mode_enum = PgEnum("exclusive", "corridor", name="ride_mode", create_type=False)

ride_status_enum = PgEnum(
    "requested",
    "matching",
    "accepted",
    "arriving",
    "arrived",
    "in_progress",
    "completed",
    "cancelled_passenger",
    "cancelled_driver",
    "expired",
    name="ride_status",
    create_type=False,
)

actor_type_enum = PgEnum(
    "passenger", "driver", "system", "admin", name="actor_type", create_type=False
)

offer_state_enum = PgEnum(
    "open",
    "accepted",
    "declined",
    "expired",
    "superseded",
    name="offer_state",
    create_type=False,
)

# The statuses that count as a ride still being live. Used by the partial
# unique index and by the driver-claim guard.
LIVE_STATUSES = (
    "requested",
    "matching",
    "accepted",
    "arriving",
    "arrived",
    "in_progress",
)


class Ride(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "rides"

    passenger_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    # Null until accepted, exactly like vehicle_id.
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("drivers.id", ondelete="SET NULL")
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL")
    )

    mode: Mapped[str] = mapped_column(ride_mode_enum, nullable=False)
    status: Mapped[str] = mapped_column(ride_status_enum, nullable=False)
    seats: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("1")
    )

    pickup_geom: Mapped[object] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    dropoff_geom: Mapped[object] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    # What the user actually said. "Carrefour Warda" is what the passenger and
    # driver will say to each other; a reverse geocode is not a substitute.
    pickup_label: Mapped[str] = mapped_column(Text, nullable=False)
    dropoff_label: Mapped[str] = mapped_column(Text, nullable=False)

    route_polyline: Mapped[str | None] = mapped_column(Text)
    route_geom: Mapped[object | None] = mapped_column(
        Geography(geometry_type="LINESTRING", srid=4326)
    )

    quoted_fare_xaf: Mapped[int] = mapped_column(Integer, nullable=False)
    final_fare_xaf: Mapped[int | None] = mapped_column(Integer)
    quoted_distance_m: Mapped[int] = mapped_column(Integer, nullable=False)
    quoted_duration_s: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_distance_m: Mapped[int | None] = mapped_column(Integer)

    accessibility_required: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )

    # The PIN is stored twice on purpose.
    #
    # `pin_hash` is what the driver's input is compared against. `pin` is the
    # plaintext, and it exists because the passenger has to read it aloud at
    # pickup and must be able to see it again after backgrounding the app,
    # losing signal or reinstalling. A PIN shown once in the 201 and never
    # again is a live failure waiting to happen.
    #
    # It is never serialised for the driver or an admin. See
    # app/services/serializers.py, where that is enforced in one place.
    pin: Mapped[str] = mapped_column(Text, nullable=False)
    pin_hash: Mapped[str] = mapped_column(Text, nullable=False)
    pin_attempts: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )

    idempotency_key: Mapped[str | None] = mapped_column(Text)

    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    cancel_reason: Mapped[str | None] = mapped_column(Text)
    cancelled_by: Mapped[str | None] = mapped_column(actor_type_enum)
    cancel_fee_xaf: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint(
            "passenger_id", "idempotency_key", name="uq_rides_passenger_idempotency"
        ),
        CheckConstraint("seats BETWEEN 1 AND 8", name="ck_rides_seats"),
        CheckConstraint("quoted_fare_xaf >= 0", name="ck_rides_quoted_fare_nonneg"),
        Index("ix_rides_passenger_created", "passenger_id", "created_at"),
        Index("ix_rides_driver_created", "driver_id", "created_at"),
        Index("ix_rides_status", "status"),
    )


class RideOffer(UuidPkMixin, TimestampMixin, Base):
    """One offer of one ride to one driver, in one matching wave.

    A first-class row rather than a synthesised id, so that declining means
    something and a later wave can exclude drivers who already refused.
    """

    __tablename__ = "ride_offers"

    ride_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("rides.id", ondelete="CASCADE"), nullable=False
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False
    )
    wave: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    state: Mapped[str] = mapped_column(
        offer_state_enum, nullable=False, server_default="open"
    )
    distance_to_pickup_m: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # One offer per ride per driver, ever. A driver who declined in wave 1
        # is not asked again in wave 2.
        UniqueConstraint("ride_id", "driver_id", name="uq_ride_offers_ride_driver"),
        Index("ix_ride_offers_driver_state", "driver_id", "state"),
        Index("ix_ride_offers_ride_state", "ride_id", "state"),
        CheckConstraint("wave BETWEEN 1 AND 3", name="ck_ride_offers_wave"),
    )


class RideEvent(Base):
    """Append only. No UPDATE, no DELETE, enforced by a trigger (I7).

    Every state transition writes a row here with the actor, the timestamp and
    the reason. Cheap from the start, impossible to retrofit at hour forty, and
    it is what makes "what actually happened on this ride" an answerable
    question during a dispute or a breach notification.
    """

    __tablename__ = "ride_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    ride_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("rides.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(BigInteger, autoincrement=True, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_type: Mapped[str] = mapped_column(actor_type_enum, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    from_status: Mapped[str | None] = mapped_column(Text)
    to_status: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        Index("ix_ride_events_ride_seq", "ride_id", "seq"),
        Index("ix_ride_events_occurred", "occurred_at"),
    )


class RideTrace(Base):
    """Server-held GPS trace. The source of truth for the fare (I2).

    Client-reported distance is never an input to a price, so this table is
    what a patched client would most want to forge. Points that fail the
    Phase 4 plausibility filter are kept with `rejected = true`: deleting them
    would destroy the record of the attempt.
    """

    __tablename__ = "ride_traces"

    ride_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("rides.id", ondelete="CASCADE"),
        primary_key=True,
    )
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    geom: Mapped[object] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    speed_mps: Mapped[float | None] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rejected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    reject_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_ride_traces_ride_recorded", "ride_id", "recorded_at"),
        Index("ix_ride_traces_geom", "geom", postgresql_using="gist"),
    )
