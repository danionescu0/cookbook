"""seed the admin user, replacing the old hard-coded ADMIN_USERNAME/admin_password account

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-29

"""
from typing import Sequence, Union

import bcrypt
from alembic import op
import sqlalchemy as sa

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

users = sa.table(
    "users",
    sa.column("id", sa.Integer),
    sa.column("username", sa.String),
    sa.column("email", sa.String),
    sa.column("password_hash", sa.String),
    sa.column("is_admin", sa.Boolean),
    sa.column("is_verified", sa.Boolean),
)


def upgrade() -> None:
    # No email on purpose — this account is created directly here, not through self-service
    # signup, so there's nothing to verify. It can add an email later from the account page.
    password_hash = bcrypt.hashpw(b"anaaremere", bcrypt.gensalt()).decode("ascii")
    op.bulk_insert(
        users,
        [
            {
                "username": "danionescu",
                "email": None,
                "password_hash": password_hash,
                "is_admin": True,
                "is_verified": True,
            }
        ],
    )


def downgrade() -> None:
    op.execute(users.delete().where(users.c.username == "danionescu"))
