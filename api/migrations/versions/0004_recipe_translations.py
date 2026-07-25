"""split recipe text content into recipe_translations

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recipe_translations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recipe_id",
            sa.Integer(),
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("ingredients", sa.JSON(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("tips", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "recipe_id", "language", name="uq_recipe_translations_recipe_language"
        ),
    )

    # Move each existing recipe's text content into a translation row in its current language,
    # before the columns holding that content are dropped from `recipes` below.
    op.execute(
        """
        INSERT INTO recipe_translations
            (recipe_id, language, title, description, ingredients, steps, tips)
        SELECT id, language, title, description, ingredients, steps, tips FROM recipes
        """
    )

    with op.batch_alter_table("recipes") as batch_op:
        batch_op.drop_column("title")
        batch_op.drop_column("description")
        batch_op.drop_column("ingredients")
        batch_op.drop_column("steps")
        batch_op.drop_column("tips")
        batch_op.drop_column("language")


def downgrade() -> None:
    with op.batch_alter_table("recipes") as batch_op:
        batch_op.add_column(
            sa.Column("title", sa.String(length=200), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("description", sa.Text(), nullable=False, server_default="")
        )
        batch_op.add_column(sa.Column("ingredients", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("steps", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("tips", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("language", sa.String(length=10), nullable=False, server_default="en")
        )

    op.drop_table("recipe_translations")
