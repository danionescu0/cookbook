"""Add app_settings.preferred_ai_provider and app_settings.deepseek_api_key — lets an admin switch
recipe extraction/translation from Claude to DeepSeek (reached through DeepSeek's own
Anthropic-API-compatible endpoint) without a code deploy

Revision ID: 0032
Revises: 0031
Create Date: 2026-08-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column(
            "preferred_ai_provider", sa.String(length=20), nullable=False, server_default="claude"
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column("deepseek_api_key", sa.String(length=200), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "deepseek_api_key")
    op.drop_column("app_settings", "preferred_ai_provider")
