"""Extra legroom as a vehicle capability, and a quiet-ride preference.

**Both of these are deliberately not what they were first asked for, and the
difference is the point.**

The request was to let a passenger record a disability so the driver could
adjust the car. That would be a health record, and Law No. 2024/017 prohibits
processing health data outright. It is also the exact thing I9 exists to
prevent, and it would be the first thing an informed reader looked for.

`extra_legroom` gets the same outcome with none of that. A passenger says the
vehicle needs room; the driver sees "needs extra legroom" and slides the seat
back. The driver does the identical thing. What is never stored is why, so
there is no diagnosis in the database, nothing to leak, and nothing to profile
anybody by. A passenger who is simply tall gets the same benefit, which is the
tell that the model is the right one: a requirement attached to the journey
serves everyone, a flag attached to the person serves nobody well.

`prefers_quiet_ride` is a preference about the journey, not about the person.
It says nothing about why somebody wants a quiet trip, and the reasons are
nobody's business: a migraine, an interview to prepare for, exhaustion, or
simply not wanting to talk. The driver is asked to keep conversation to
essentials, and essentials are never suppressed, because a driver still has to
confirm the pickup and say when they have arrived.

Neither field narrows the vehicle pool the way a capability does, except
legroom, which genuinely is a property of the car.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A property of the car, matched exactly like the other capabilities.
    op.add_column(
        "vehicles",
        sa.Column(
            "has_extra_legroom",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # A requirement carried by the journey, defaulted from the profile.
    op.add_column(
        "users",
        sa.Column(
            "requires_extra_legroom",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "prefers_quiet_ride",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # Seeded fleets are small, so a partial index would not pay for itself.
    # This one exists because the matcher filters on it per request.
    op.create_index(
        "ix_vehicles_extra_legroom",
        "vehicles",
        ["has_extra_legroom"],
        postgresql_where=sa.text("has_extra_legroom"),
    )


def downgrade() -> None:
    op.drop_index("ix_vehicles_extra_legroom", table_name="vehicles")
    op.drop_column("users", "prefers_quiet_ride")
    op.drop_column("users", "requires_extra_legroom")
    op.drop_column("vehicles", "has_extra_legroom")
