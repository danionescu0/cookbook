"""users.terms_accepted_at / terms_version: record consent to the Terms and Conditions at signup

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable — existing accounts predate this policy and never went through the acceptance
    # step, so there's nothing truthful to backfill here (same reasoning as User.email being
    # nullable for the migration-seeded admin).
    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("terms_version", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "terms_version")
    op.drop_column("users", "terms_accepted_at")
