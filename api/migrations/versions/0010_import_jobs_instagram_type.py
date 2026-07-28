"""widen import_jobs.type to fit the new "instagram" job type

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Column was auto-sized to fit "bookmark" (8 chars) when created — "instagram" (9 chars)
    # overflows it. No CHECK constraint to widen (Enum(..., native_enum=False) doesn't add one by
    # default, same reasoning as migration 0005), just the VARCHAR length.
    with op.batch_alter_table("import_jobs") as batch_op:
        batch_op.alter_column("type", type_=sa.String(length=20))


def downgrade() -> None:
    with op.batch_alter_table("import_jobs") as batch_op:
        batch_op.alter_column("type", type_=sa.String(length=8))
