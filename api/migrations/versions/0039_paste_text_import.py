"""paste-text recipe import: import_jobs.source_text/enrich_from_web, recipes.is_from_import

Revision ID: 0039
Revises: 0038
Create Date: 2026-09-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0039"
down_revision: Union[str, None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The full pasted text (source stores only a short display excerpt for paste jobs — see
    # models/import_job.py). Nullable: null for every non-paste job type.
    op.add_column("import_jobs", sa.Column("source_text", sa.Text(), nullable=True))
    # The user's opt-in checkbox to let the worker do a preceding web-search call to fill gaps in
    # a pasted recipe — read only for ImportJobType.PASTE jobs.
    op.add_column(
        "import_jobs",
        sa.Column("enrich_from_web", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # True for any recipe that came out of the import pipeline (URL, bookmark, Instagram, or
    # paste) rather than being typed by hand on /submit-recipe. Needed because a paste import has
    # no source_url, so "source_url is not null" (the previous proxy for "this is an import") can
    # no longer distinguish import provenance — see routers/recipes.py's acknowledge_import and
    # PendingImportsPanel.tsx.
    op.add_column(
        "recipes",
        sa.Column("is_from_import", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    recipes = sa.table("recipes", sa.column("id", sa.Integer), sa.column("source_url", sa.String))
    bind = op.get_bind()
    bind.execute(
        recipes.update()
        .where(recipes.c.source_url.isnot(None))
        .values(is_from_import=True)
    )


def downgrade() -> None:
    op.drop_column("recipes", "is_from_import")
    op.drop_column("import_jobs", "enrich_from_web")
    op.drop_column("import_jobs", "source_text")
