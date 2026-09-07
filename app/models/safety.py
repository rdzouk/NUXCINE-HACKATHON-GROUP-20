"""Trust and safety tables.

Four tables, and each one exists because a claim in the pitch has to be backed
by something a jury can be shown.

**`ride_share_tokens`** is the highest safety value per hour of work in the
whole build. A token is stored as a hash, expires, and is revocable, so a link
forwarded onward stops working rather than becoming permanent access to
somebody's location.

**`ledger_entries`** is a *debt* ledger, not a wallet. That is a deliberate
market choice: wallet pre-load kills conversion in a cash economy, and a debt
row needs no money movement to demonstrate. Corrections are new `adjustment`
rows; nothing here is ever mutated.

**`incident_reports`** seals an immutable snapshot at the moment of the report.
Reading the ride afterwards would show its *current* state, which is exactly
what an incident needs not to depend on.

**`canned_messages`** replaces phone contact entirely (I3). A closed template
set cannot carry harassment or an off-app phone number, translates without a
pipeline, and costs almost nothing on a bad network.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidPkMixin

ledger_kind_enum = PgEnum(
    "fare_charge",
    "fare_payout",
    "cancel_fee",
    "cancel_compensation",
    "pass_purchase",
    "pass_redemption",
    "adjustment",
    name="ledger_kind",
    create_type=False,
)

incident_category_enum = PgEnum(
    "safety",
    "harassment",
    "fare_dispute",
    "no_show",
    "vehicle_condition",
    "other",
    name="incident_category",
    create_type=False,
)

incident_status_enum = PgEnum(
    "open", "reviewing", "resolved", name="incident_status", create_type=False
)


class RideShareToken(UuidPkMixin, TimestampMixin, Base):
    """A family-and-friends live-tracking link.

    The token itself is never stored, only its SHA-256. A stolen database
    backup must not be a set of working tracking links into people's journeys.
    SHA-256 rather than argon2 because the token is server-generated entropy
    signed by itsdangerous: there is nothing to brute-force, and the lookup
    happens on every poll of the public view.
    """

    __tablename__ = "ride_share_tokens"

    ride_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("rides.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Who minted it, so a passenger can see and revoke their own links.
    created_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    view_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    __table_args__ = (
        Index("ix_ride_share_tokens_ride", "ride_id"),
        Index("ix_ride_share_tokens_expires", "expires_at"),
    )


class LedgerEntry(UuidPkMixin, TimestampMixin, Base):
    """Money owed, in both directions. Append only.

    `amount_xaf` is signed: negative is owed *by* the user, positive is owed
    *to* them. A cancellation fee and the driver's compensation for it are two
    rows, not one field, because they settle independently and because the
    compensation is conditional on the driver actually having moved.

    Nothing here is ever updated except `settled_at`. A correction is a new
    `adjustment` row, so the history of what was charged and why survives.
    """

    __tablename__ = "ledger_entries"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    ride_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("rides.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(ledger_kind_enum, nullable=False)
    amount_xaf: Mapped[int] = mapped_column(Integer, nullable=False)
    # Null means outstanding. Booking is refused while a user has any.
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_ledger_entries_user_settled", "user_id", "settled_at"),
        Index("ix_ledger_entries_ride", "ride_id"),
        # One fee per ride per kind. Without this a retried cancellation could
        # charge somebody twice for the same act.
        Index(
            "uq_ledger_one_per_ride_kind",
            "ride_id",
            "kind",
            "user_id",
            unique=True,
            postgresql_where=text("ride_id IS NOT NULL"),
        ),
    )


class IncidentReport(UuidPkMixin, TimestampMixin, Base):
    """An SOS or a filed report, with the evidence sealed at that moment.

    `snapshot` is written once and never updated. Reading the ride later would
    show its current state; an incident needs the state at the time it was
    raised, including the trace summary and who the counterparty was, because
    both may have changed by the time anybody reviews it.
    """

    __tablename__ = "incident_reports"

    ride_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("rides.id", ondelete="CASCADE"), nullable=False
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reported_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    category: Mapped[str] = mapped_column(incident_category_enum, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        incident_status_enum, nullable=False, server_default="open"
    )
    # An SOS is not a report. It is raised in the moment, needs no description,
    # and gets its own alerting path.
    is_sos: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_incident_reports_ride", "ride_id"),
        Index("ix_incident_reports_status", "status"),
        Index("ix_incident_reports_sos", "is_sos"),
    )


class CannedMessage(UuidPkMixin, TimestampMixin, Base):
    """One party saying one of a fixed set of things to the other.

    Deliberately no free-text column. Adding one would reintroduce every
    problem I3 exists to remove: harassment, off-app phone numbers, and a
    translation pipeline nobody has time to build.
    """

    __tablename__ = "canned_messages"

    ride_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("rides.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    template_key: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_canned_messages_ride_created", "ride_id", "created_at"),
        CheckConstraint("length(template_key) <= 40", name="ck_canned_template_len"),
    )
