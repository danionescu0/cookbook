"""swap USDA FoodData Central for CalorieNinjas: rename api key, drop usda_fdc_id

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("app_settings") as batch_op:
        batch_op.alter_column("usda_api_key", new_column_name="calorie_ninjas_api_key")

    # No stable per-food ID from the CalorieNinjas API to key on — ingredients are matched (and
    # refreshed) by name alone from here on. See README Design Decisions ("Ingredient nutrition").
    with op.batch_alter_table("ingredients") as batch_op:
        batch_op.drop_column("usda_fdc_id")


def downgrade() -> None:
    with op.batch_alter_table("ingredients") as batch_op:
        batch_op.add_column(sa.Column("usda_fdc_id", sa.Integer(), nullable=True, unique=True))

    with op.batch_alter_table("app_settings") as batch_op:
        batch_op.alter_column("calorie_ninjas_api_key", new_column_name="usda_api_key")
