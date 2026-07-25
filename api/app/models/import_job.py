import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ImportJobType(str, enum.Enum):
    SINGLE = "single"
    BULK = "bulk"
    BOOKMARK = "bookmark"


class ImportJobStatus(str, enum.Enum):
    # A job sits here, unpublished to RabbitMQ, until an admin approves it — see
    # POST /imports/{id}/approve and the README's "Single or bulk URL import" workflow.
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

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
