"""google sign-in: users.google_sub, app_settings.google_client_id

Revision ID: 0034
Revises: 0033
Create Date: 2026-08-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.String(length=255), nullable=True))
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)

    # Not secret — the same public Client ID embedded in the signup page's HTML, same reasoning
    # as turnstile_site_key.
    op.add_column(
        "app_settings",
        sa.Column("google_client_id", sa.String(length=255), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "google_client_id")
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_column("users", "google_sub")
