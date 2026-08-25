"""recipe title search: pg_trgm + unaccent, trigram index on recipe_translations.title

Revision ID: 0036
Revises: 0035
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Trigram, not tsvector: gives plain substring matching anywhere in the title with no
    # per-row language/dictionary config, which matters since a recipe_translations row can be
    # "ro" or "en" and tsvector stemming needs a config choice per row either way. See README
    # Design Decisions, "Recipe search".
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # unaccent, so "Briose" matches "Brioșe" and vice versa (and title-only text search doesn't
    # otherwise require the diacritics used inconsistently across recipe sources). unaccent()
    # itself is STABLE, not IMMUTABLE (it resolves its dictionary via search_path), so it can't be
    # used directly in an index expression — f_unaccent pins it to the "unaccent" dictionary by
    # name, which makes it deterministic and safe to mark IMMUTABLE. Same function is reused at
    # query time in routers/recipes.py so both sides of the comparison are normalized identically.
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute(
        "CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text AS "
        "$$ SELECT public.unaccent('public.unaccent', $1) $$ "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT"
    )
    op.execute(
        "CREATE INDEX ix_recipe_translations_title_trgm ON recipe_translations "
        "USING gin (lower(f_unaccent(title)) gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_recipe_translations_title_trgm")
    op.execute("DROP FUNCTION IF EXISTS f_unaccent(text)")
    # Extensions left in place — dropping them is a separate, riskier call if anything else ever
    # comes to depend on them.
