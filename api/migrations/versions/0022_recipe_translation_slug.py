"""recipe_translations.slug: SEO-friendly, per-language slug generated from title

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-03

"""
import re
import unicodedata
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Mirrors app.slugify.slugify as of when this migration was written — migrations are frozen
# snapshots and intentionally don't import from the (evolving) app package.
_EXTRA_CHAR_MAP = str.maketrans(
    {
        "ș": "s", "Ș": "S", "ş": "s", "Ş": "S",
        "ț": "t", "Ț": "T", "ţ": "t", "Ţ": "T",
    }
)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    text = text.translate(_EXTRA_CHAR_MAP)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = _NON_ALNUM_RE.sub("-", text).strip("-")
    if len(text) > 100:
        text = text[:100].rsplit("-", 1)[0]
    return text or "recipe"


def upgrade() -> None:
    op.add_column("recipe_translations", sa.Column("slug", sa.String(length=110), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, language, title FROM recipe_translations")).fetchall()

    used_per_language: dict[str, set[str]] = {}
    for row_id, language, title in rows:
        taken = used_per_language.setdefault(language, set())
        base = _slugify(title or "")
        candidate = base
        suffix = 2
        while candidate in taken:
            candidate = f"{base}-{suffix}"
            suffix += 1
        taken.add(candidate)
        bind.execute(
            sa.text("UPDATE recipe_translations SET slug = :slug WHERE id = :id"),
            {"slug": candidate, "id": row_id},
        )

    op.alter_column("recipe_translations", "slug", nullable=False)
    op.create_unique_constraint(
        "uq_recipe_translations_language_slug", "recipe_translations", ["language", "slug"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_recipe_translations_language_slug", "recipe_translations", type_="unique")
    op.drop_column("recipe_translations", "slug")
