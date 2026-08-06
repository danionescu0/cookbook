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


class ImportErrorKind(str, enum.Enum):
    # The site's robots.txt disallowed us — retrying won't help, and it's not our bug. Everything
    # else (network errors, a bad extraction, an unexpected exception) is lumped into TECHNICAL —
    # a non-admin viewer only ever sees this categorized kind, never the raw `error` text (see
    # routers/imports.py's _serialize), so the split only needs to be coarse enough to pick the
    # right canned copy.
    DISALLOWED = "disallowed"
    TECHNICAL = "technical"


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
    # Null until the worker resolves it from Claude's own suggestion, once extraction succeeds —
    # the requester no longer picks a category up front (see routers/imports.py's
    # create_import_job and worker/app/handlers.py's _resolve_category_id). Stays null forever for
    # a job that never reaches that point (e.g. a failed fetch).
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    type: Mapped[ImportJobType] = mapped_column(
        Enum(ImportJobType, native_enum=False), default=ImportJobType.SINGLE
    )
    source: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[ImportJobStatus] = mapped_column(
        Enum(ImportJobStatus, native_enum=False), default=ImportJobStatus.PENDING
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set alongside `error` whenever status becomes FAILED (see worker/app/handlers.py) — lets a
    # non-admin viewer get a categorized, friendly message without ever seeing the raw `error`
    # text. Null for a job that never failed, and for jobs that failed before this column existed.
    error_kind: Mapped[ImportErrorKind | None] = mapped_column(
        Enum(ImportErrorKind, native_enum=False), nullable=True
    )
    # Whoever created this job — the worker sets the resulting Recipe's owner_user_id from this
    # once the import finishes (imports are always private to whoever ran them, never shareable).
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # Set when the owner dismisses a failed job from their account page (POST
    # /imports/{id}/dismiss) — hides it from their own view only. Deliberately never consulted by
    # the admin failed-imports page, which needs the full history regardless of what an owner's
    # already dismissed.
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set when an admin marks a failed job as handled on the Failed Imports back office page (POST
    # /imports/{id}/mark-reviewed) — completely independent of the owner's own dismissed_at above.
    # An owner dismissing their own notification never sets this, and an admin marking a job
    # reviewed never touches dismissed_at — the two audiences track "have I dealt with this" on
    # their own axis, on purpose, so neither can silently clear it for the other.
    admin_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    created_by: Mapped["User | None"] = relationship()

    @property
    def created_by_username(self) -> str | None:
        return self.created_by.username if self.created_by else None
