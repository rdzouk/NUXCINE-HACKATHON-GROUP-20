"""Trust and safety: share tokens, ledger, incidents, canned messages.

Two constraints here carry policy rather than mere tidiness.

`uq_ledger_one_per_ride_kind` stops a retried cancellation charging somebody
twice for the same act. Idempotency at the HTTP layer covers the common case;
this covers the case where two requests race past it.

`incident_reports.snapshot` is NOT NULL because an incident without its sealed
evidence is worse than no incident: it looks like a record and answers nothing.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE ledger_kind AS ENUM ('fare_charge', 'fare_payout', "
        "'cancel_fee', 'cancel_compensation', 'pass_purchase', "
        "'pass_redemption', 'adjustment')"
    )
    op.execute(
        "CREATE TYPE incident_category AS ENUM ('safety', 'harassment', "
        "'fare_dispute', 'no_show', 'vehicle_condition', 'other')"
    )
    op.execute(
        "CREATE TYPE incident_status AS ENUM ('open', 'reviewing', 'resolved')"
    )

    ledger_kind = postgresql.ENUM(name="ledger_kind", create_type=False)
    incident_category = postgresql.ENUM(name="incident_category", create_type=False)
    incident_status = postgresql.ENUM(name="incident_status", create_type=False)

    op.create_table(
        "ride_share_tokens",
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
        # The hash, never the token. A stolen backup must not be a set of
        # working tracking links into people's journeys.
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
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
        sa.UniqueConstraint("token_hash", name="uq_ride_share_tokens_hash"),
    )
    op.create_index("ix_ride_share_tokens_ride", "ride_share_tokens", ["ride_id"])
    op.create_index("ix_ride_share_tokens_expires", "ride_share_tokens", ["expires_at"])

    op.create_table(
        "ledger_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "ride_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rides.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kind", ledger_kind, nullable=False),
        # Signed. Negative is owed by the user, positive is owed to them.
        sa.Column("amount_xaf", sa.Integer(), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
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
    )
    op.create_index(
        "ix_ledger_entries_user_settled", "ledger_entries", ["user_id", "settled_at"]
    )
    op.create_index("ix_ledger_entries_ride", "ledger_entries", ["ride_id"])
    # One entry per (ride, kind, user). A retried cancellation must not charge
    # the same person twice for the same act.
    op.execute(
        "CREATE UNIQUE INDEX uq_ledger_one_per_ride_kind "
        "ON ledger_entries (ride_id, kind, user_id) WHERE ride_id IS NOT NULL"
    )

    op.create_table(
        "incident_reports",
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
            "reporter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "reported_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("category", incident_category, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # NOT NULL: an incident without sealed evidence looks like a record and
        # answers nothing.
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("status", incident_status, nullable=False, server_default="open"),
        sa.Column(
            "is_sos", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index("ix_incident_reports_ride", "incident_reports", ["ride_id"])
    op.create_index("ix_incident_reports_status", "incident_reports", ["status"])
    op.create_index("ix_incident_reports_sos", "incident_reports", ["is_sos"])

    # The snapshot is sealed at the moment of the report. Allowing an UPDATE
    # would let the evidence be edited after the fact, which is precisely what
    # it exists to prevent.
    op.execute(
        """
        CREATE FUNCTION incident_snapshot_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.snapshot IS DISTINCT FROM OLD.snapshot THEN
                RAISE EXCEPTION
                    'incident_reports.snapshot is sealed and cannot be changed'
                    USING ERRCODE = 'restrict_violation';
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER incident_snapshot_sealed
        BEFORE UPDATE ON incident_reports
        FOR EACH ROW EXECUTE FUNCTION incident_snapshot_immutable();
        """
    )

    op.create_table(
        "canned_messages",
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
            "sender_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # A key, never free text. See app/models/safety.py.
        sa.Column("template_key", sa.Text(), nullable=False),
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
        sa.CheckConstraint("length(template_key) <= 40", name="ck_canned_template_len"),
    )
    op.create_index(
        "ix_canned_messages_ride_created", "canned_messages", ["ride_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("canned_messages")
    op.execute("DROP TRIGGER IF EXISTS incident_snapshot_sealed ON incident_reports")
    op.execute("DROP FUNCTION IF EXISTS incident_snapshot_immutable()")
    op.drop_table("incident_reports")
    op.drop_table("ledger_entries")
    op.drop_table("ride_share_tokens")
    op.execute("DROP TYPE IF EXISTS incident_status")
    op.execute("DROP TYPE IF EXISTS incident_category")
    op.execute("DROP TYPE IF EXISTS ledger_kind")
