"""recipes: every recipe has an owner and is private by default; opt-in sharing for non-imports

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("recipes", "submitted_by_user_id", new_column_name="owner_user_id")
    op.add_column(
        "recipes", sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "import_jobs",
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    bind = op.get_bind()
    danionescu_id = bind.execute(
        sa.text("SELECT id FROM users WHERE username = 'danionescu'")
    ).scalar()

    if danionescu_id is not None:
        # Backfill: every recipe that predates per-user ownership (i.e. everything danionescu
        # imported or created himself before this feature existed) becomes his. Only a recipe
        # that was already manually added (not imported) and already approved keeps its current
        # public visibility — every import defaults to private, which is the actual bug fix this
        # migration exists for.
        bind.execute(
            sa.text("UPDATE recipes SET owner_user_id = :uid WHERE owner_user_id IS NULL"),
            {"uid": danionescu_id},
        )
        bind.execute(
            sa.text(
                # The Enum column (native_enum=False) stores the Python enum member's *name*
                # ("APPROVED"), not its .value ("approved") — matching on the lowercase value
                # here silently matches nothing. Confirmed against the actual column contents,
                # not assumed.
                "UPDATE recipes SET is_shared = true "
                "WHERE source_url IS NULL AND status = 'APPROVED'"
            )
        )
        bind.execute(
            sa.text(
                "UPDATE import_jobs SET created_by_user_id = :uid WHERE created_by_user_id IS NULL"
            ),
            {"uid": danionescu_id},
        )

    op.alter_column("recipes", "owner_user_id", nullable=False)


def downgrade() -> None:
    op.alter_column("recipes", "owner_user_id", nullable=True)
    op.drop_column("import_jobs", "created_by_user_id")
    op.drop_column("recipes", "is_shared")
    op.alter_column("recipes", "owner_user_id", new_column_name="submitted_by_user_id")
