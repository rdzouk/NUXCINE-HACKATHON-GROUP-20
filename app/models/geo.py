"""Gazetteer and driver presence.

This is Bet 1's storage. Street addressing is functionally absent for most
trips in Yaounde, so the primary geocoding path is a curated landmark table,
not a street index.

Three columns do the matching work, and they are different tools for different
failure modes:

  `aliases`     the names people actually say. "Warda", "Carrefour Warda",
                "Rond-point Warda" are one place. A GIN index makes an exact
                alias hit the first and cheapest layer of the cascade.
  `search_vec`  a tsvector for word-level matching, so "marche mokolo" finds
                "Mokolo Market" regardless of word order.
  trigram       catches misspelling. "carefour warda" has no exact alias and no
                shared lexeme with "Carrefour Warda" after stemming, but its
                trigrams overlap heavily.

All three run in the database against an index. Doing fuzzy matching in Python
would mean loading the table per query, which is why rapidfuzz is not used here.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidPkMixin

landmark_kind_enum = PgEnum(
    "carrefour",
    "station",
    "market",
    "school",
    "hospital",
    "admin",
    "business",
    "quartier",
    name="landmark_kind",
    create_type=False,
)


class Landmark(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "landmarks"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    kind: Mapped[str] = mapped_column(landmark_kind_enum, nullable=False)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    quartier: Mapped[str | None] = mapped_column(Text)

    geom: Mapped[object] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )

    # Hand-set ranking weight. Two places can match a query equally well and
    # still not be equally likely to be meant: "Poste Centrale" is a landmark
    # everyone knows, a small business with a similar name is not.
    popularity: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    # Maintained by a trigger, not GENERATED ALWAYS. See the migration: the
    # accent-insensitive expression this needs is not IMMUTABLE, which a
    # generated column requires.
    search_vec: Mapped[object | None] = mapped_column(TSVECTOR)

    # Seeded rows can be refreshed wholesale; hand-added ones must survive that.
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="manual")
    osm_id: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_landmarks_search_vec", "search_vec", postgresql_using="gin"),
        Index("ix_landmarks_aliases", "aliases", postgresql_using="gin"),
        Index("ix_landmarks_geom", "geom", postgresql_using="gist"),
        Index("ix_landmarks_city_kind", "city", "kind"),
    )


class DriverPresence(TimestampMixin, Base):
    """Where each online driver is, right now.

    The GiST index on `geom` is the single most important index in the system:
    every matching wave is an ST_DWithin against it. Without it, matching is a
    sequential scan of every driver on every ride request.

    Separate from `drivers` because the access pattern is different. This row
    is rewritten every few seconds per driver; `drivers` is nearly static. The
    KYC and online flags live on `drivers` so the CHECK constraint that gates
    going online can exist at all.
    """

    __tablename__ = "driver_presence"

    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    geom: Mapped[object] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    heading: Mapped[int | None] = mapped_column(SmallInteger)
    speed_mps: Mapped[float | None] = mapped_column()
    accuracy_m: Mapped[float | None] = mapped_column()
    is_stale: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        Index("ix_driver_presence_geom", "geom", postgresql_using="gist"),
        Index("ix_driver_presence_recorded", "recorded_at"),
    )
