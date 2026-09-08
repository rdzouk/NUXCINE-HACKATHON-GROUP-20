"""Ride needs, and the driver undertakings that go with them.

**What a passenger states is what they need, never why.** The options are
legroom, climate, windows, a spoken itinerary, a guided tour. Every one is a
thing the driver does; none is a condition anybody has. A passenger who is
tall, or who gets carsick, or who is simply new to the city selects the same
options as anyone else and the system cannot tell them apart, which is the
whole point: there is no diagnosis in the database to leak, and no category to
profile anybody by.

That framing is not a preference. Law No. 2024/017 prohibits processing health
data, so "requires extra legroom" is lawful where "has a mobility impairment"
is not, and the driver does exactly the same thing either way.

**The spoken itinerary runs on the driver's phone, not the passenger's.** A
blind passenger cannot watch a route on a screen, and a driver who takes a
shortcut is indistinguishable from a driver going the wrong way unless
somebody says so out loud. So the driver's app announces each turn and each
deviation, in the car, where the passenger can hear it. It is offered to
everybody, because a passenger new to Yaounde has the same problem for a
different reason.

**Guided tour** is the same mechanism pointed at a different purpose: the
driver narrates what the car is passing. It exists because it is genuinely
useful to a visitor and because it gives a driver a reason to be good at it.

`driver_undertakings` records that a driver has agreed, in writing, to carry
these out politely and at no extra charge. Without it these are requests a
driver may quietly ignore or surcharge, which would make the feature worse
than not having it: a passenger would rely on something that does not reliably
happen.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Stated as needs, in the passenger's own terms. Stored as text on the ride so
# a new need can be added without a migration, and validated at the API
# boundary against the enum rather than by a database constraint that would
# need changing every time the list grows.
NEEDS = (
    "extra_legroom",
    "climate_adjusted",
    "windows_closed",
    "spoken_itinerary",
    "guided_tour",
    "quiet_ride",
    "other",
)


def upgrade() -> None:
    # Per ride, because a need can change trip to trip: somebody travelling
    # with luggage today needs boot space today. The profile supplies the
    # default; the ride carries what was actually asked for.
    op.add_column(
        "rides",
        sa.Column(
            "ride_needs",
            sa.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )

    # Free text for "other", capped hard. It reaches the driver, so it is a
    # channel between two people and has to be short enough to read at a
    # glance and too short to hold a phone number or an address.
    op.add_column(
        "rides",
        sa.Column("ride_needs_note", sa.String(length=140), nullable=True),
    )

    # The passenger's standing defaults.
    op.add_column(
        "users",
        sa.Column(
            "default_ride_needs",
            sa.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )

    # A driver may only be offered a ride carrying these needs once they have
    # agreed to them. Nullable because agreement is a moment in time, and the
    # timestamp is the record of it.
    op.add_column(
        "drivers",
        sa.Column("undertakings_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "drivers",
        sa.Column("undertakings_version", sa.String(length=16), nullable=True),
    )

    # Matching filters on this per request.
    op.create_index(
        "ix_drivers_undertakings",
        "drivers",
        ["undertakings_accepted_at"],
        postgresql_where=sa.text("undertakings_accepted_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_drivers_undertakings", table_name="drivers")
    op.drop_column("drivers", "undertakings_version")
    op.drop_column("drivers", "undertakings_accepted_at")
    op.drop_column("users", "default_ride_needs")
    op.drop_column("rides", "ride_needs_note")
    op.drop_column("rides", "ride_needs")
