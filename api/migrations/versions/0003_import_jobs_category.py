"""add category_id to import_jobs

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("import_jobs") as batch_op:
        batch_op.add_column(sa.Column("category_id", sa.Integer(), nullable=False))
        batch_op.create_foreign_key(
            "fk_import_jobs_category_id_categories", "categories", ["category_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("import_jobs") as batch_op:
        batch_op.drop_constraint("fk_import_jobs_category_id_categories", type_="foreignkey")
        batch_op.drop_column("category_id")
