import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TranslationSyncJobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class TranslationSyncJob(Base):
    """Triggered whenever an admin edits a recipe's translation (PUT /recipes/{id}) — propagates
    the edited language's content to every other supported language via Claude, then re-enqueues
    nutrition enrichment once every language (and therefore the default-language ingredients that
    nutrition parsing reads) is back in sync. See README Design Decisions ("Ingredient nutrition").
    """

    __tablename__ = "translation_sync_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    # The language that was just hand-edited — translated *from* this into every other
    # supported language, not the other way around.
    source_language: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[TranslationSyncJobStatus] = mapped_column(
        Enum(TranslationSyncJobStatus, native_enum=False), default=TranslationSyncJobStatus.QUEUED
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
