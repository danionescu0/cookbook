"""remove users.username (login is by email now); add password_reset_tokens

Revision ID: 0033
Revises: 0032
Create Date: 2026-08-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_password_reset_tokens_token", "password_reset_tokens", ["token"], unique=True)

    # Belt-and-suspenders: the one known account without an email (the migration-0018-seeded
    # admin) was already backfilled by hand before this migration ships, but this guarantees the
    # NOT NULL below can't fail on some other environment that skipped that step. A fake
    # "@invalid.local" address reads as "this account needs attention" rather than silently
    # reusing real data.
    op.execute(
        "UPDATE users SET email = username || '-' || id || '@invalid.local' WHERE email IS NULL"
    )
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=False)

    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")


def downgrade() -> None:
    # Nullable, and left empty — the dropped username values are gone for good, same reasoning as
    # User.email being nullable for the original seeded admin (see 0012/0018's comments).
    op.add_column("users", sa.Column("username", sa.String(length=50), nullable=True))
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=True)
    op.drop_index("ix_password_reset_tokens_token", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
