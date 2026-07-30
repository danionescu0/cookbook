"""recipes.submitted_by_user_id: track user-submitted recipes distinct from admin/import ones

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column(
            "submitted_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("recipes", "submitted_by_user_id")
