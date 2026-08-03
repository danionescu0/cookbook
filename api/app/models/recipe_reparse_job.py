import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RecipeReparseJobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class RecipeReparseJob(Base):
    """Re-scrapes and re-extracts an already-imported recipe's source_url, then updates that
    recipe's existing translations in place (same id, owner, status, sharing, images) — used to
    pick up extraction-quality fixes (e.g. sub-group headers, see app.recipe_sections) for
    recipes that were imported before those fixes existed. See worker/app/reparse_handlers.py.
    """

    __tablename__ = "recipe_reparse_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[RecipeReparseJobStatus] = mapped_column(
        Enum(RecipeReparseJobStatus, native_enum=False), default=RecipeReparseJobStatus.QUEUED
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
