import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EmailJobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class EmailJob(Base):
    __tablename__ = "email_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # Only "verification" today; kept as a plain string (like ImportJob.type) rather than an enum
    # of one value, so a future email kind doesn't need a migration to add.
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[EmailJobStatus] = mapped_column(
        Enum(EmailJobStatus, native_enum=False), default=EmailJobStatus.QUEUED
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
