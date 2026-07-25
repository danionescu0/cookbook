"""default import_jobs.status to pending

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-24

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No CHECK constraint to widen — ImportJobStatus is stored as a plain VARCHAR
    # (Enum(..., native_enum=False) doesn't add one by default), so "pending" is already a
    # valid value. Only the default for newly-created rows needs to change.
    with op.batch_alter_table("import_jobs") as batch_op:
        batch_op.alter_column("status", server_default="pending")


def downgrade() -> None:
    with op.batch_alter_table("import_jobs") as batch_op:
        batch_op.alter_column("status", server_default="queued")
