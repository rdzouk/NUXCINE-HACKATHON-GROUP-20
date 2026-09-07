"""Rides, offers, events and traces.

Three constraints here are the phase's actual security work, and none of them
can be moved into application code without losing what makes them work.

**One live ride per passenger** is a partial unique index. A handler check
cannot do this: two concurrent POSTs both read "no live ride", both pass, and
both insert. Only the database can serialise that.

**`ride_events` is append-only**, enforced by a trigger that raises on UPDATE
and DELETE. Not by role grants, because the application connects as the table
owner and an owner can work around grants. The trigger fires regardless.

**Idempotency is a unique constraint** on `(passenger_id, idempotency_key)`, so
a retried request collides in the database rather than relying on the handler
winning a race with itself. Mobile networks here drop and retry; without this,
one tap creates two rides (I8).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIVE_STATUSES = (
    "requested",
    "matching",
    "accepted",
    "arriving",
    "arrived",
    "in_progress",
)


def upgrade() -> None:
    op.execute("CREATE TYPE ride_mode AS ENUM ('exclusive', 'corridor')")
    op.execute(
        "CREATE TYPE ride_status AS ENUM ('requested', 'matching', 'accepted', "
        "'arriving', 'arrived', 'in_progress', 'completed', "
        "'cancelled_passenger', 'cancelled_driver', 'expired')"
    )
    op.execute(
        "CREATE TYPE actor_type AS ENUM ('passenger', 'driver', 'system', 'admin')"
    )
    op.execute(
        "CREATE TYPE offer_state AS ENUM ('open', 'accepted', 'declined', "
        "'expired', 'superseded')"
    )

    ride_mode = postgresql.ENUM(name="ride_mode", create_type=False)
    ride_status = postgresql.ENUM(name="ride_status", create_type=False)
    actor_type = postgresql.ENUM(name="actor_type", create_type=False)
    offer_state = postgresql.ENUM(name="offer_state", create_type=False)

    op.create_table(
        "rides",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "passenger_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # Null until accepted, exactly like vehicle_id. §5 annotated only
        # driver_id; both are unknowable at creation.
        sa.Column(
            "driver_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("drivers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "vehicle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vehicles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("mode", ride_mode, nullable=False),
        sa.Column("status", ride_status, nullable=False),
        sa.Column("seats", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("pickup_label", sa.Text(), nullable=False),
        sa.Column("dropoff_label", sa.Text(), nullable=False),
        sa.Column("route_polyline", sa.Text(), nullable=True),
        sa.Column("quoted_fare_xaf", sa.Integer(), nullable=False),
        sa.Column("final_fare_xaf", sa.Integer(), nullable=True),
        sa.Column("quoted_distance_m", sa.Integer(), nullable=False),
        sa.Column("quoted_duration_s", sa.Integer(), nullable=False),
        sa.Column("actual_distance_m", sa.Integer(), nullable=True),
        sa.Column(
            "accessibility_required",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        # Plaintext and hash both. The passenger reads the PIN aloud and must
        # be able to see it after an app restart; the driver's input is
        # compared against the hash. The plaintext is never serialised for the
        # driver or an admin.
        sa.Column("pin", sa.Text(), nullable=False),
        sa.Column("pin_hash", sa.Text(), nullable=False),
        sa.Column(
            "pin_attempts", sa.SmallInteger(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("cancelled_by", actor_type, nullable=True),
        sa.Column("cancel_fee_xaf", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # I8. A retried POST collides here rather than creating a second ride.
        sa.UniqueConstraint(
            "passenger_id", "idempotency_key", name="uq_rides_passenger_idempotency"
        ),
        sa.CheckConstraint("seats BETWEEN 1 AND 8", name="ck_rides_seats"),
        sa.CheckConstraint("quoted_fare_xaf >= 0", name="ck_rides_quoted_fare_nonneg"),
    )

    op.execute("ALTER TABLE rides ADD COLUMN pickup_geom geography(Point, 4326) NOT NULL")
    op.execute("ALTER TABLE rides ADD COLUMN dropoff_geom geography(Point, 4326) NOT NULL")
    op.execute("ALTER TABLE rides ADD COLUMN route_geom geography(LineString, 4326)")

    op.create_index("ix_rides_passenger_created", "rides", ["passenger_id", "created_at"])
    op.create_index("ix_rides_driver_created", "rides", ["driver_id", "created_at"])
    op.create_index("ix_rides_status", "rides", ["status"])
    # Corridor containment queries in Phase 6 run against this.
    op.execute("CREATE INDEX ix_rides_route_geom ON rides USING gist (route_geom)")
    op.execute("CREATE INDEX ix_rides_pickup_geom ON rides USING gist (pickup_geom)")

    live = ", ".join(f"'{s}'" for s in LIVE_STATUSES)

    # One live ride per passenger. The database is the only place this can be
    # enforced: two concurrent creations both pass a handler check.
    op.execute(
        f"CREATE UNIQUE INDEX uq_rides_one_live_per_passenger "
        f"ON rides (passenger_id) WHERE status IN ({live})"
    )
    # And one live ride per driver, which is what stops a driver being claimed
    # by two passengers at once. §5 describes this as part of the accept
    # transaction; making it an index means even a buggy transaction cannot
    # violate it.
    op.execute(
        f"CREATE UNIQUE INDEX uq_rides_one_live_per_driver "
        f"ON rides (driver_id) WHERE driver_id IS NOT NULL AND status IN ({live})"
    )

    op.create_table(
        "ride_offers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "ride_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rides.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "driver_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("drivers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("wave", sa.SmallInteger(), nullable=False),
        sa.Column("state", offer_state, nullable=False, server_default="open"),
        sa.Column("distance_to_pickup_m", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # A driver who declined in wave 1 is not re-offered in wave 2.
        sa.UniqueConstraint("ride_id", "driver_id", name="uq_ride_offers_ride_driver"),
        sa.CheckConstraint("wave BETWEEN 1 AND 3", name="ck_ride_offers_wave"),
    )
    op.create_index("ix_ride_offers_driver_state", "ride_offers", ["driver_id", "state"])
    op.create_index("ix_ride_offers_ride_state", "ride_offers", ["ride_id", "state"])

    op.create_table(
        "ride_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "ride_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rides.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor_type", actor_type, nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_ride_events_ride_seq", "ride_events", ["ride_id", "seq"])
    op.create_index("ix_ride_events_occurred", "ride_events", ["occurred_at"])

    # I7, enforced rather than asserted.
    #
    # A trigger, not a role grant: the application connects as the table owner
    # and an owner can work around grants. This fires for everyone. An audit
    # log that can be edited is not evidence, and this table is what safety
    # claims, fare disputes and breach notification all rest on.
    op.execute(
        """
        CREATE FUNCTION ride_events_append_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION
                'ride_events is append-only: % is not permitted', TG_OP
                USING ERRCODE = 'restrict_violation';
        END $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER ride_events_no_update_delete
        BEFORE UPDATE OR DELETE ON ride_events
        FOR EACH ROW EXECUTE FUNCTION ride_events_append_only();
        """
    )

    op.create_table(
        "ride_traces",
        sa.Column(
            "ride_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rides.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("seq", sa.Integer(), primary_key=True),
        sa.Column("speed_mps", sa.Float(), nullable=True),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        # Kept, not deleted. A point that failed the plausibility filter is the
        # record of an attempt to forge a fare.
        sa.Column(
            "rejected", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("reject_reason", sa.Text(), nullable=True),
    )
    op.execute("ALTER TABLE ride_traces ADD COLUMN geom geography(Point, 4326) NOT NULL")
    op.create_index(
        "ix_ride_traces_ride_recorded", "ride_traces", ["ride_id", "recorded_at"]
    )
    op.execute("CREATE INDEX ix_ride_traces_geom ON ride_traces USING gist (geom)")


def downgrade() -> None:
    op.drop_table("ride_traces")
    op.execute("DROP TRIGGER IF EXISTS ride_events_no_update_delete ON ride_events")
    op.execute("DROP FUNCTION IF EXISTS ride_events_append_only()")
    op.drop_table("ride_events")
    op.drop_table("ride_offers")
    op.drop_table("rides")
    op.execute("DROP TYPE IF EXISTS offer_state")
    op.execute("DROP TYPE IF EXISTS actor_type")
    op.execute("DROP TYPE IF EXISTS ride_status")
    op.execute("DROP TYPE IF EXISTS ride_mode")
