"""add app_settings table, seeded with defaults (admin_password/anthropic_api_key from .env)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-27

"""
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

app_settings = sa.table(
    "app_settings",
    sa.column("id", sa.Integer),
    sa.column("supported_languages", sa.String),
    sa.column("default_language", sa.String),
    sa.column("admin_password", sa.String),
    sa.column("anthropic_api_key", sa.String),
    sa.column("default_rate_limit_requests_per_minute", sa.Integer),
    sa.column("scrape_timeout_seconds", sa.Float),
    sa.column("max_html_chars", sa.Integer),
    sa.column("image_max_dimension", sa.Integer),
    sa.column("image_max_size_kb", sa.Integer),
)


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("supported_languages", sa.String(length=100), nullable=False),
        sa.Column("default_language", sa.String(length=10), nullable=False),
        sa.Column("admin_password", sa.String(length=200), nullable=False),
        sa.Column("anthropic_api_key", sa.String(length=200), nullable=False),
        sa.Column("default_rate_limit_requests_per_minute", sa.Integer(), nullable=False),
        sa.Column("scrape_timeout_seconds", sa.Float(), nullable=False),
        sa.Column("max_html_chars", sa.Integer(), nullable=False),
        sa.Column("image_max_dimension", sa.Integer(), nullable=False),
        sa.Column("image_max_size_kb", sa.Integer(), nullable=False),
    )

    # Seed the single row. Only admin_password and anthropic_api_key are genuine bootstrap
    # secrets read from .env here (there's no other way to get an initial value into a system
    # gated behind the very password being set) — api and worker both load the same file via
    # env_file:, so it's readable here. Every other field is DB-only from the start: it was never
    # meant to be tunable via .env, so it gets the same hardcoded default app.config.Settings used
    # to ship, not an os.getenv() read. Once this migration has run, editing any of these nine in
    # .env again does nothing — change them via Backoffice > Settings instead. See README Design
    # Decisions ("Admin-editable settings").
    op.bulk_insert(
        app_settings,
        [
            {
                "id": 1,
                "supported_languages": "ro,en",
                "default_language": "ro",
                "admin_password": os.getenv("ADMIN_PASSWORD", "change-me"),
                "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
                "default_rate_limit_requests_per_minute": 6,
                "scrape_timeout_seconds": 15.0,
                "max_html_chars": 200_000,
                "image_max_dimension": 1600,
                "image_max_size_kb": 500,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("app_settings")
