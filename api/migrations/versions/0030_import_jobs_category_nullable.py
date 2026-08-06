"""Make import_jobs.category_id nullable — the category is no longer picked by the user at
import time, it's suggested by Claude from the recipe content once extraction finishes

Revision ID: 0030
Revises: 0029
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite (used by the test suite) can't ALTER a constrained column without batch mode — see
    # migration 0003 for the same pattern; Postgres (production) doesn't need it but tolerates it.
    with op.batch_alter_table("import_jobs") as batch_op:
        batch_op.alter_column("category_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("import_jobs") as batch_op:
        batch_op.alter_column("category_id", existing_type=sa.Integer(), nullable=False)
