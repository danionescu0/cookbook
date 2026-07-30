import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ImportJobType(str, enum.Enum):
    SINGLE = "single"
    BULK = "bulk"
    BOOKMARK = "bookmark"
    INSTAGRAM = "instagram"


class ImportJobStatus(str, enum.Enum):
    # An admin's job sits here, unpublished to RabbitMQ, until they approve it — see
    # POST /imports/{id}/approve and the README's "Single or bulk URL import" workflow. A
    # non-admin's own job skips this step and queues immediately (see routers/imports.py) —
    # imports are always private, so there's nothing to review before it's exposed to anyone.
    PENDING = "pending"
    QUEUED = "queued"
    FETCHING = "fetching"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    type: Mapped[ImportJobType] = mapped_column(
        Enum(ImportJobType, native_enum=False), default=ImportJobType.SINGLE
    )
    source: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[ImportJobStatus] = mapped_column(
        Enum(ImportJobStatus, native_enum=False), default=ImportJobStatus.PENDING
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Whoever created this job — the worker sets the resulting Recipe's owner_user_id from this
    # once the import finishes (imports are always private to whoever ran them, never shareable).
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    created_by: Mapped["User | None"] = relationship()

    @property
    def created_by_username(self) -> str | None:
        return self.created_by.username if self.created_by else None
