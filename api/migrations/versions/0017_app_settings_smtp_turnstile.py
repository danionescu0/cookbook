"""app_settings: add SMTP + Turnstile + public_site_url, drop admin_password (now per-user)

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "app_settings", sa.Column("smtp_host", sa.String(length=255), nullable=False, server_default="")
    )
    op.add_column(
        "app_settings",
        sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="587"),
    )
    op.add_column(
        "app_settings",
        sa.Column("smtp_username", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "app_settings",
        sa.Column("smtp_password", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "app_settings",
        sa.Column("smtp_from_address", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "app_settings",
        sa.Column("smtp_use_tls", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "app_settings",
        sa.Column("turnstile_site_key", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "app_settings",
        sa.Column("turnstile_secret_key", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "app_settings",
        sa.Column("public_site_url", sa.String(length=255), nullable=False, server_default=""),
    )
    op.drop_column("app_settings", "admin_password")


def downgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("admin_password", sa.String(length=200), nullable=False, server_default="change-me"),
    )
    op.drop_column("app_settings", "public_site_url")
    op.drop_column("app_settings", "turnstile_secret_key")
    op.drop_column("app_settings", "turnstile_site_key")
    op.drop_column("app_settings", "smtp_use_tls")
    op.drop_column("app_settings", "smtp_from_address")
    op.drop_column("app_settings", "smtp_password")
    op.drop_column("app_settings", "smtp_username")
    op.drop_column("app_settings", "smtp_port")
    op.drop_column("app_settings", "smtp_host")
