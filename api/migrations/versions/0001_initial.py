"""initial schema: categories, recipes

Revision ID: 0001
Revises:
Create Date: 2026-07-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
    )
    op.create_index("ix_categories_slug", "categories", ["slug"], unique=True)

    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("ingredients", sa.JSON(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("tips", sa.JSON(), nullable=False),
        sa.Column("images", sa.JSON(), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("language", sa.String(length=10), nullable=False, server_default="en"),
        sa.Column(
            "status",
            sa.Enum("unapproved", "approved", name="recipestatus", native_enum=False),
            nullable=False,
            server_default="approved",
        ),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("recipes")
    op.drop_index("ix_categories_slug", table_name="categories")
    op.drop_table("categories")
