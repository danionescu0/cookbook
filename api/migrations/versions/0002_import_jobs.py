"""import_jobs table

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "type",
            sa.Enum("single", "bulk", "bookmark", name="importjobtype", native_enum=False),
            nullable=False,
            server_default="single",
        ),
        sa.Column("source", sa.String(length=2048), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued", "fetching", "processing", "done", "failed",
                name="importjobstatus", native_enum=False,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("import_jobs")
