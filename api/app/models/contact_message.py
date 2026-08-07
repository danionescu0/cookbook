import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ContactMessageStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class ContactMessage(Base):
    """A visitor-submitted contact form message, queued for the worker to email to the site
    owner (app_settings.contact_recipient_email) — see worker/app/contact_handlers.py. There's no
    admin viewer page for these; the notification email itself is the record.
    """

    __tablename__ = "contact_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # At least one of email/phone is required (enforced in ContactMessageCreate, not here) — a
    # visitor needs to be reachable somehow, but not necessarily both ways.
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # Set when the submitter was logged in — purely informational (included in the notification
    # email so the reply can address them by account), never required; a logged-out visitor still
    # gets a captcha instead (see routers/contact.py).
    submitted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[ContactMessageStatus] = mapped_column(
        Enum(ContactMessageStatus, native_enum=False), default=ContactMessageStatus.QUEUED
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
