"""Enable the Postgres extensions the whole build depends on.

No tables. Phase 0 is scaffolding and a contract; the first tables land in
Phase 1.

Each extension earns its place:

  postgis    Every geo query in the system. ST_DWithin against a GiST index is
             the difference between matching in milliseconds and hand-rolling
             haversine filtering in Python.
  pg_trgm    Trigram similarity. This is what makes "carefour warda" match
             "Carrefour Warda" inside the database index rather than in a
             Python fuzzy-matching loop over every landmark.
  unaccent   Accent folding, so "Nsimeyong" and "Nsimeyong" with any diacritic
             variation collide. Combined with pg_trgm it covers the real
             spelling variance in how people type Cameroonian place names.
  pgcrypto   gen_random_uuid() for primary keys.

Note for Phase 2: unaccent() is STABLE, not IMMUTABLE, because it depends on a
dictionary. It therefore cannot be used directly in a GENERATED ALWAYS AS
STORED column, which is how §5 sketches landmarks.search_vec. That column needs
an IMMUTABLE wrapper function, created in the landmarks migration.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")


def downgrade() -> None:
    # postgis is not dropped. Dropping it cascades to every geometry column in
    # the database, which is a far more destructive operation than the word
    # "downgrade" suggests to whoever runs it at 03:00.
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
    op.execute("DROP EXTENSION IF EXISTS unaccent")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
