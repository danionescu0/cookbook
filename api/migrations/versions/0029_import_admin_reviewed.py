"""Add import_jobs.admin_reviewed_at, letting an admin mark a failed import as handled on the
Failed Imports back office page independently of the owner's own dismissal

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "import_jobs", sa.Column("admin_reviewed_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("import_jobs", "admin_reviewed_at")
