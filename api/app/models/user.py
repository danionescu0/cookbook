from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    # Nullable so the migration-seeded admin (created directly in the DB, not through signup)
    # doesn't need one — every self-service signup always sets it.
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # A stricter tier than is_admin — gates the Settings subpage (API keys, SMTP, Turnstile,
    # rate limits, ...), not just the back office generally. Every super admin is expected to
    # also be a regular admin, but the two flags are independent columns rather than an enum so
    # granting/revoking either doesn't require migrating the other.
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
