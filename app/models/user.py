"""Identity tables.

Three deliberate choices worth reading before changing anything here.

`otp_challenges.code_hash` stores an argon2 hash, never the code. The OTP
keyspace is four digits, so a leaked table of plaintext codes would be worse
than useless: an attacker with read access could log in as anyone mid-flight.
Argon2 is memory-hard, so even the hashes do not fall to a GPU sweep of ten
thousand candidates fast enough to matter inside a five-minute TTL.

`refresh_tokens.token_hash` is a SHA-256 of the token, not the token. A stolen
database backup must not be a set of working sessions. SHA-256 rather than
argon2 here because the token is 256 bits of server-generated entropy, so there
is nothing to brute-force and the lookup happens on every refresh.

`family_id` is what makes reuse detection possible. Every rotation issues a new
token in the same family; presenting a token that has already been rotated means
either theft or a clone, and the correct response is to kill the whole family
rather than guess which party is the attacker.
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
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPkMixin

# Native Postgres enums. create_type=False because the migration creates them;
# letting SQLAlchemy emit CREATE TYPE as a side effect of table creation makes
# migration order unpredictable.
user_role_enum = PgEnum(
    "passenger", "driver", "admin", name="user_role", create_type=False
)
user_status_enum = PgEnum(
    "active", "restricted", "suspended", name="user_status", create_type=False
)
kyc_status_enum = PgEnum(
    "pending", "verified", "rejected", "suspended", name="kyc_status", create_type=False
)


class User(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "users"

    phone_e164: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(user_role_enum, nullable=False, default="passenger")
    status: Mapped[str] = mapped_column(user_status_enum, nullable=False, default="active")
    locale: Mapped[str] = mapped_column(Text, nullable=False, server_default="fr")

    # Vehicle capability requirements, never medical or personal facts (I9).
    # Law 2024/017 prohibits processing health data; a wheelchair user is not
    # recorded as a wheelchair user, a trip is recorded as requiring a ramp.
    requires_ramp: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    requires_boot_space: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    requires_front_seat: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    requires_driver_assist: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    allows_guide_animal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # A communication preference, not a matching predicate. See the split
    # documented in docs/CONTRACT_DECISIONS.md section 6.
    prefers_text_contact: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    driver: Mapped[Driver | None] = relationship(
        back_populates="user", uselist=False, lazy="selectin"
    )


class OtpChallenge(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "otp_challenges"

    phone_e164: Mapped[str] = mapped_column(Text, nullable=False)
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    max_attempts: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("5")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_ip: Mapped[str | None] = mapped_column(INET)

    __table_args__ = (
        Index("ix_otp_challenges_phone_expires", "phone_e164", "expires_at"),
    )


class RefreshToken(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    family_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set when this token was rotated. A token with rotated_at set that is
    # presented again is the reuse signal that kills the family.
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_refresh_tokens_family", "family_id"),
        Index("ix_refresh_tokens_user", "user_id"),
    )


class Driver(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "drivers"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    kyc_status: Mapped[str] = mapped_column(
        kyc_status_enum, nullable=False, server_default="pending"
    )
    kyc_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    kyc_rejection_reason: Mapped[str | None] = mapped_column(Text)

    # A hash, never the CNI number. Enough to deduplicate registrations and to
    # ban a person rather than an account, without holding the identifier
    # itself. §4.2: the driver is the higher-risk party and is already
    # professionally licensed, so full KYC here costs nothing in inclusion.
    cni_ref_hash: Mapped[str | None] = mapped_column(String(64), unique=True)

    rating_avg: Mapped[float | None] = mapped_column(Numeric(3, 2))

    # is_online lives here, not on driver_presence, so that the §5 constraint
    # "a driver cannot be online unless verified" is expressible as a real
    # CHECK. Postgres cannot reference another table from a CHECK, so as §5
    # wrote it the constraint could not be created at all. Phase 2's
    # driver_presence holds the geometry, heading and freshness.
    is_online: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    seats_free: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    went_online_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="driver", lazy="selectin")
    vehicles: Mapped[list[Vehicle]] = relationship(
        back_populates="driver", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint(
            "kyc_status = 'verified' OR NOT is_online",
            name="ck_drivers_online_requires_verified_kyc",
        ),
        CheckConstraint("seats_free BETWEEN 0 AND 8", name="ck_drivers_seats_free"),
    )


class Vehicle(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "vehicles"

    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False
    )
    plate: Mapped[str] = mapped_column(Text, nullable=False)
    make: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(Text, nullable=False)
    seats: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    photo_url: Mapped[str | None] = mapped_column(Text)

    # Capability flags, matched against the requirements on users and rides.
    # front_seat_available exists because §5's users table had a
    # requires_front_seat with no vehicle counterpart to match it against.
    has_ramp: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    has_boot_space: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    front_seat_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    driver_assists: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    accepts_guide_animal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    driver: Mapped[Driver] = relationship(back_populates="vehicles")

    __table_args__ = (
        CheckConstraint("seats BETWEEN 1 AND 8", name="ck_vehicles_seats"),
        Index("ix_vehicles_driver", "driver_id"),
    )


class KycDocument(UuidPkMixin, TimestampMixin, Base):
    """Encrypted KYC documents.

    The document reference is stored as AES-GCM ciphertext, not plaintext, so
    that a database read does not yield a set of national identity numbers.
    Law 2024/017 makes a breach here a notifiable event with real financial
    exposure, and the encryption is what keeps that breach a nuisance rather
    than a disclosure.

    Files themselves are not stored in Phase 1; only the reference and its
    metadata. Object storage is a Phase 7 concern and is recorded as an
    accepted risk in THREAT_MODEL.md.
    """

    __tablename__ = "kyc_documents"

    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    reference_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_kyc_documents_driver_kind", "driver_id", "kind", unique=True),
    )
