"""Add users.language, so the verification email can be sent in the language a user signed up in

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Default matches frontend/src/i18n/config.ts's DEFAULT_LANGUAGE, for existing rows (the
    # migration-seeded admin, and any account created before this column existed).
    op.add_column(
        "users",
        sa.Column("language", sa.String(length=5), nullable=False, server_default="ro"),
    )


def downgrade() -> None:
    op.drop_column("users", "language")
