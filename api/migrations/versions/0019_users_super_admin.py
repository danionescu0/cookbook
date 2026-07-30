"""users.is_super_admin: a stricter tier with access to Settings (API keys, SMTP, Turnstile, ...)

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

users = sa.table("users", sa.column("username", sa.String), sa.column("is_super_admin", sa.Boolean))


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("is_super_admin", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.execute(users.update().where(users.c.username == "danionescu").values(is_super_admin=True))


def downgrade() -> None:
    op.drop_column("users", "is_super_admin")
