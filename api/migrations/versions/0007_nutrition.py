"""ingredient nutrition: ingredients, recipe_ingredient_links, nutrition_jobs, servings, usda key

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingredients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("usda_fdc_id", sa.Integer(), nullable=True, unique=True),
        sa.Column("calories_per_100g", sa.Float(), nullable=False),
        sa.Column("protein_per_100g", sa.Float(), nullable=False),
        sa.Column("carbs_per_100g", sa.Float(), nullable=False),
        sa.Column("sugars_per_100g", sa.Float(), nullable=False),
        sa.Column("fat_per_100g", sa.Float(), nullable=False),
    )
    op.create_index("ix_ingredients_name", "ingredients", ["name"])

    op.create_table(
        "recipe_ingredient_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ingredient_index", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), sa.ForeignKey("ingredients.id"), nullable=False),
        sa.Column("raw_text", sa.String(length=500), nullable=False),
        sa.Column("estimated_grams", sa.Float(), nullable=False),
        sa.Column("grams_source", sa.String(length=20), nullable=False),
        sa.UniqueConstraint(
            "recipe_id", "ingredient_index", name="uq_recipe_ingredient_links_recipe_index"
        ),
    )

    op.create_table(
        "nutrition_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="queued"
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.add_column("recipes", sa.Column("estimated_servings", sa.Integer(), nullable=True))
    op.add_column(
        "app_settings",
        sa.Column("usda_api_key", sa.String(length=200), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "usda_api_key")
    op.drop_column("recipes", "estimated_servings")
    op.drop_table("nutrition_jobs")
    op.drop_table("recipe_ingredient_links")
    op.drop_index("ix_ingredients_name", table_name="ingredients")
    op.drop_table("ingredients")
