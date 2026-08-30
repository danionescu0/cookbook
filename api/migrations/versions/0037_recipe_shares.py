"""recipe_shares: private, expiring, person-to-person recipe links

Revision ID: 0037
Revises: 0036
Create Date: 2026-08-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recipe_shares",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column(
            "created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_recipe_shares_token", "recipe_shares", ["token"], unique=True)

    # Provenance only ("copied from a shared recipe") — see Recipe.shared_from_recipe_id's
    # docstring for why this is SET NULL rather than CASCADE.
    op.add_column(
        "recipes",
        sa.Column(
            "shared_from_recipe_id", sa.Integer(),
            sa.ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("recipes", "shared_from_recipe_id")
    op.drop_index("ix_recipe_shares_token", table_name="recipe_shares")
    op.drop_table("recipe_shares")
