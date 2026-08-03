"""Lifetime import limit: app_settings.max_imports_per_user + users.imported_recipes_count

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("max_imports_per_user", sa.Integer(), nullable=False, server_default="30"),
    )
    # Incremented once per successful import, never decremented — a lifetime counter, not a
    # live count of the user's current imported recipes, so deleting a recipe (or its import_jobs
    # row) never frees up quota. See worker/app/handlers.py::_finish_import.
    op.add_column(
        "users",
        sa.Column("imported_recipes_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "imported_recipes_count")
    op.drop_column("app_settings", "max_imports_per_user")
