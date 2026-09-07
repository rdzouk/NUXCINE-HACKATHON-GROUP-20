"""Corridor legs, and a correction to the one-live-ride rule.

Two things here.

**`corridor_legs`** records each passenger's own segment of a shared ride, so a
four-seat vehicle carrying three passengers has an auditable answer to "what
did each of them travel, and what did each of them pay".

**The one-live-ride-per-passenger index is corrected.** As written in Phase 3 it
counts every live ride a passenger owns, which is right for exclusive hire and
wrong for corridor: the joining passenger's leg is a `rides` row of its own, and
the index would refuse it if that passenger somehow held two. More importantly
the *driver* index has to change, because a corridor driver is by definition on
several live rides at once. That was flagged at Phase 0 (contract decision 7)
and is settled here rather than being discovered during the demo.

Note that `route_geom` was declared in Phase 3 but never populated: nothing
needed a line until now. Corridor containment is `ST_DWithin` against it, so
Phase 6 starts writing it on ride creation.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIVE = (
    "requested",
    "matching",
    "accepted",
    "arriving",
    "arrived",
    "in_progress",
)


def upgrade() -> None:
    op.create_table(
        "corridor_legs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # The ride that owns the vehicle and the route.
        sa.Column(
            "parent_ride_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rides.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # This passenger's own ride. For the first passenger the two are the
        # same row: they are not a guest on somebody else's journey, they
        # started it.
        sa.Column(
            "ride_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rides.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("boarding_order", sa.SmallInteger(), nullable=False),
        sa.Column("seats", sa.SmallInteger(), nullable=False),
        # A leg is written when the driver is asked, not when they answer, so
        # that a pending join holds its place in the boarding order and cannot
        # be double-offered. It becomes real only on consent.
        #
        # Kept here rather than on ride_offers because everything about a
        # corridor join belongs in one place: an offer row knows nothing about
        # legs, fares or boarding order, and teaching it would spread the mode
        # across two tables for no gain.
        sa.Column(
            "state",
            sa.Text(),
            nullable=False,
            server_default="offered",
        ),
        sa.Column("leg_distance_m", sa.Integer(), nullable=False),
        sa.Column("leg_fare_xaf", sa.Integer(), nullable=False),
        # What joining cost the passengers already aboard. Recorded so the cap
        # can be shown to have been respected, not merely asserted.
        sa.Column("added_distance_m", sa.Integer(), nullable=True),
        sa.Column("added_duration_s", sa.Integer(), nullable=True),
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
        sa.UniqueConstraint("ride_id", name="uq_corridor_legs_ride"),
        sa.CheckConstraint("seats BETWEEN 1 AND 8", name="ck_corridor_legs_seats"),
        sa.CheckConstraint(
            "boarding_order BETWEEN 1 AND 3", name="ck_corridor_legs_order"
        ),
        sa.CheckConstraint(
            "state IN ('offered', 'confirmed')", name="ck_corridor_legs_state"
        ),
    )
    op.create_index(
        "ix_corridor_legs_parent", "corridor_legs", ["parent_ride_id", "boarding_order"]
    )
    # Seat accounting reads confirmed legs on the hot path of every join.
    op.create_index(
        "ix_corridor_legs_state",
        "corridor_legs",
        ["parent_ride_id", "state"],
    )

    live = ", ".join(f"'{s}'" for s in LIVE)

    # A corridor driver carries several live rides at once, which is the entire
    # point of the mode. The one-live-ride-per-driver rule therefore applies to
    # exclusive hire only; for corridor, capacity is enforced by seats_free.
    op.execute("DROP INDEX IF EXISTS uq_rides_one_live_per_driver")
    op.execute(
        f"CREATE UNIQUE INDEX uq_rides_one_live_exclusive_per_driver "
        f"ON rides (driver_id) "
        f"WHERE driver_id IS NOT NULL AND mode = 'exclusive' "
        f"AND status IN ({live})"
    )

    # The passenger rule is unchanged: one live ride each, corridor or not.
    # Somebody riding in two cars at once is a bug in every mode.


def downgrade() -> None:
    live = ", ".join(f"'{s}'" for s in LIVE)
    op.execute("DROP INDEX IF EXISTS uq_rides_one_live_exclusive_per_driver")
    op.execute(
        f"CREATE UNIQUE INDEX uq_rides_one_live_per_driver "
        f"ON rides (driver_id) WHERE driver_id IS NOT NULL AND status IN ({live})"
    )
    op.drop_table("corridor_legs")
