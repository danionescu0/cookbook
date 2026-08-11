"""recipe_ingredient_links: allow more than one item per source line

Revision ID: 0035
Revises: 0034
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A single ingredient line can legitimately name more than one food ("salt, black pepper",
    # "oil and vinegar") — Claude's nutrition parse correctly returns one item per food, not one
    # per line, so two items sharing a line_index is real data, not a duplicate. The unique
    # constraint made that combination fail the whole nutrition job (see README Design Decisions,
    # "Ingredient nutrition"). Kept as a plain, non-unique index — recipe_id/ingredient_index is
    # still the lookup/ordering key (see nutrition.py's ORDER BY), just no longer required unique.
    op.drop_constraint(
        "uq_recipe_ingredient_links_recipe_index", "recipe_ingredient_links", type_="unique"
    )
    op.create_index(
        "ix_recipe_ingredient_links_recipe_index",
        "recipe_ingredient_links",
        ["recipe_id", "ingredient_index"],
    )


def downgrade() -> None:
    op.drop_index("ix_recipe_ingredient_links_recipe_index", table_name="recipe_ingredient_links")
    op.create_unique_constraint(
        "uq_recipe_ingredient_links_recipe_index",
        "recipe_ingredient_links",
        ["recipe_id", "ingredient_index"],
    )
