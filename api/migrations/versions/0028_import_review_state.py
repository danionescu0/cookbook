"""Add recipes.import_reviewed_at and import_jobs.error_kind/dismissed_at, powering the account
page's post-import review panel and the admin failed-imports page

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recipes", sa.Column("import_reviewed_at", sa.DateTime(timezone=True), nullable=True)
    )
    # Backfill existing imports as already-reviewed — otherwise every import ever made would
    # suddenly flood every owner's account page the moment this ships. Only new imports going
    # forward are actually null (unreviewed).
    op.execute("UPDATE recipes SET import_reviewed_at = added_at WHERE source_url IS NOT NULL")

    op.add_column("import_jobs", sa.Column("error_kind", sa.String(length=20), nullable=True))
    op.add_column(
        "import_jobs", sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("import_jobs", "dismissed_at")
    op.drop_column("import_jobs", "error_kind")
    op.drop_column("recipes", "import_reviewed_at")
