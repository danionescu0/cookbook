"""email_verification_tokens: one-time tokens proving a signup's email address

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_email_verification_tokens_token", "email_verification_tokens", ["token"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_email_verification_tokens_token", table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")
