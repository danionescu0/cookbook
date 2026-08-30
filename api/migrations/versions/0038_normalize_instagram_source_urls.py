"""normalize existing Instagram source URLs: strip share-tracking query params

Revision ID: 0038
Revises: 0037
Create Date: 2026-08-30

"""
from typing import Sequence, Union
from urllib.parse import urlparse, urlunparse

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Duplicated from app/url_normalize.py rather than imported — migrations stay self-contained so a
# later change to that module's logic can't silently change what an already-applied migration
# did. Real prod case this fixes: Instagram appends a different ?igsi=... tracking token to a
# link every time it's re-shared/re-copied, so the same reel imported multiple times (once per
# distinct token) ended up as several duplicate recipes instead of being caught by the
# already-imported check — see README Design Decisions, "Instagram URL normalization".
_INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com", "instagr.am"}


def _normalize(url: str) -> str:
    stripped = url.strip()
    parsed = urlparse(stripped)
    host = (parsed.hostname or "").lower()
    if host not in _INSTAGRAM_HOSTS:
        return stripped
    path = parsed.path if parsed.path.endswith("/") else f"{parsed.path}/"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def upgrade() -> None:
    bind = op.get_bind()

    # Row-by-row rather than a single UPDATE ... SET source = regexp_replace(...): the
    # normalization logic (host check, trailing-slash handling, query/fragment stripping) mirrors
    # app/url_normalize.py exactly, which is far easier to keep correct in Python than to
    # reproduce as a SQL expression. Both tables are small (imports/recipes, not a high-volume
    # table), so per-row UPDATEs are not a performance concern here. Only rows that actually
    # change are written, and re-running this migration is a no-op the second time.
    import_jobs = sa.table("import_jobs", sa.column("id", sa.Integer), sa.column("source", sa.String))
    for row in bind.execute(sa.select(import_jobs.c.id, import_jobs.c.source)).fetchall():
        normalized = _normalize(row.source)
        if normalized != row.source:
            bind.execute(
                import_jobs.update().where(import_jobs.c.id == row.id).values(source=normalized)
            )

    recipes = sa.table("recipes", sa.column("id", sa.Integer), sa.column("source_url", sa.String))
    for row in bind.execute(sa.select(recipes.c.id, recipes.c.source_url)).fetchall():
        if row.source_url is None:
            continue
        normalized = _normalize(row.source_url)
        if normalized != row.source_url:
            bind.execute(
                recipes.update().where(recipes.c.id == row.id).values(source_url=normalized)
            )


def downgrade() -> None:
    # Stripping a share-tracking query param loses no information anything else in the app reads
    # (see url_normalize.py's docstring) — there's nothing meaningful to restore, so this is a
    # deliberate no-op rather than a fabricated reverse transformation.
    pass
