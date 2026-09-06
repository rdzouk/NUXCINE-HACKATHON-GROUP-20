"""Gazetteer and driver presence.

The interesting part of this migration is the accent-insensitive search vector,
which cannot be written the obvious way.

§5 specifies `search_vec tsvector GENERATED ALWAYS AS (...) STORED`. Postgres
requires a generated column's expression to be IMMUTABLE, and `unaccent()` is
only STABLE, because it depends on a dictionary that could in principle be
changed. So the natural expression

    to_tsvector('french', unaccent(name))

is rejected at CREATE TABLE time with "generation expression is not immutable".

Two ways out. Marking `unaccent` itself IMMUTABLE is the common advice and is a
lie to the planner: it would let a cached plan survive a dictionary change.
Instead we wrap it in our own IMMUTABLE SQL function that pins the dictionary
explicitly, and maintain the column with a trigger rather than a generated
expression. The trigger also lets the vector cover the alias array, which a
generated column over a single row expression would make awkward.

Accent-insensitivity is not cosmetic here. "Ngoa-Ekelle" gets typed as
"ngoa ekelle", "Ngoa Ekelle" and "NGOA-EKELLE"; "Marche" is written both with
and without the accent on the e. Without unaccent, each spelling is a different
lexeme and the match silently fails.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # An IMMUTABLE unaccent, safe because the dictionary is named explicitly
    # rather than resolved from a search path that could change under a plan.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION vora_unaccent(text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        PARALLEL SAFE
        STRICT
        AS $$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$;
        """
    )

    # Folded alias text, for the trigram index.
    #
    # `array_to_string` is STABLE rather than IMMUTABLE, so using it directly
    # in an index expression is rejected. The STABLE marking is a blanket
    # conservatism across every array type: for some element types the output
    # function is affected by run-time settings (DateStyle, for instance).
    #
    # Restricted to `text[]`, that concern does not apply. The output function
    # for text is the identity, so this is genuinely deterministic and the
    # IMMUTABLE claim is true rather than a convenient lie to the planner.
    # The signature is deliberately typed `text[]` and not `anyarray`, because
    # `anyarray` is exactly the case where the claim would be false.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION vora_alias_text(text[])
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        PARALLEL SAFE
        AS $$ SELECT vora_unaccent(lower(array_to_string($1, ' '))) $$;
        """
    )

    op.execute(
        "CREATE TYPE landmark_kind AS ENUM ('carrefour', 'station', 'market', "
        "'school', 'hospital', 'admin', 'business', 'quartier')"
    )

    landmark_kind = postgresql.ENUM(name="landmark_kind", create_type=False)

    op.create_table(
        "landmarks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "aliases",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("kind", landmark_kind, nullable=False),
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("quartier", sa.Text(), nullable=True),
        sa.Column("popularity", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("search_vec", postgresql.TSVECTOR(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("osm_id", sa.Text(), nullable=True),
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

    # Geography columns are added by raw DDL rather than through create_table.
    # GeoAlchemy2 registers DDL listeners that emit their own spatial-metadata
    # statements, and combining those with an explicit migration produces
    # duplicate index and AddGeometryColumn calls that fail on the second run.
    op.execute("ALTER TABLE landmarks ADD COLUMN geom geography(Point, 4326) NOT NULL")

    op.execute(
        """
        CREATE FUNCTION landmarks_search_vec_refresh() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            -- Name and aliases share one vector. A query matching any spelling
            -- of a place should find it, and weighting the canonical name
            -- above the aliases keeps "Marche Central" ahead of a business
            -- that merely lists it as a neighbouring landmark.
            NEW.search_vec :=
                setweight(
                    to_tsvector('simple', vora_unaccent(coalesce(NEW.name, ''))),
                    'A'
                ) ||
                setweight(
                    to_tsvector(
                        'simple',
                        vora_unaccent(array_to_string(coalesce(NEW.aliases, '{}'), ' '))
                    ),
                    'B'
                ) ||
                setweight(
                    to_tsvector('simple', vora_unaccent(coalesce(NEW.quartier, ''))),
                    'C'
                );
            RETURN NEW;
        END $$;
        """
    )
    # 'simple' rather than 'french': these are proper nouns. French stemming
    # would mangle "Nsimeyong" and "Biyem-Assi" into lexemes that no user query
    # reproduces, and it buys nothing on names that are not French words.
    op.execute(
        """
        CREATE TRIGGER landmarks_search_vec_trg
        BEFORE INSERT OR UPDATE OF name, aliases, quartier ON landmarks
        FOR EACH ROW EXECUTE FUNCTION landmarks_search_vec_refresh();
        """
    )

    op.create_index(
        "ix_landmarks_search_vec", "landmarks", ["search_vec"], postgresql_using="gin"
    )
    op.create_index(
        "ix_landmarks_aliases", "landmarks", ["aliases"], postgresql_using="gin"
    )
    op.create_index("ix_landmarks_geom", "landmarks", ["geom"], postgresql_using="gist")
    op.create_index("ix_landmarks_city_kind", "landmarks", ["city", "kind"])

    # Trigram indexes on the accent-folded name and alias text. This is the
    # layer that turns "carefour warda" into "Carrefour Warda": a misspelling
    # shares no lexeme with the correct spelling after tokenising, but its
    # trigrams overlap almost completely.
    op.execute(
        "CREATE INDEX ix_landmarks_name_trgm ON landmarks "
        "USING gin (vora_unaccent(lower(name)) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_landmarks_alias_trgm ON landmarks "
        "USING gin (vora_alias_text(aliases) gin_trgm_ops)"
    )

    op.create_table(
        "driver_presence",
        sa.Column(
            "driver_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("drivers.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("heading", sa.SmallInteger(), nullable=True),
        sa.Column("speed_mps", sa.Float(), nullable=True),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
        sa.Column(
            "is_stale", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
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
    op.execute(
        "ALTER TABLE driver_presence ADD COLUMN geom geography(Point, 4326) NOT NULL"
    )

    # The single most important index in the system. Every matching wave is an
    # ST_DWithin against it; without it, matching sequentially scans every
    # driver on every ride request.
    op.create_index(
        "ix_driver_presence_geom", "driver_presence", ["geom"], postgresql_using="gist"
    )
    op.create_index(
        "ix_driver_presence_recorded", "driver_presence", ["recorded_at"]
    )


def downgrade() -> None:
    op.drop_table("driver_presence")
    op.execute("DROP TRIGGER IF EXISTS landmarks_search_vec_trg ON landmarks")
    op.execute("DROP FUNCTION IF EXISTS landmarks_search_vec_refresh()")
    op.drop_table("landmarks")
    op.execute("DROP TYPE IF EXISTS landmark_kind")
    op.execute("DROP FUNCTION IF EXISTS vora_alias_text(text[])")
    op.execute("DROP FUNCTION IF EXISTS vora_unaccent(text)")
