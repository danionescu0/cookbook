from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
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

    # The UI language active at signup (see frontend/src/i18n) — used to send the verification
    # email (and any future account emails) in a language the user actually reads, rather than
    # whatever `default_language` happens to be configured. Not synced afterward if the user
    # later switches languages — email language and browsing language are independent.
    language: Mapped[str] = mapped_column(String(5), default="ro", nullable=False)

    # When/which version of the Terms and Conditions this account agreed to at signup. Null for
    # accounts that predate this policy (the migration-seeded admin, and anyone who signed up
    # before it existed) — nothing truthful to backfill for those.
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terms_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Lifetime count of successful imports, incremented once by the worker per completed import
    # (see worker/app/handlers.py::_finish_import) and never decremented — deleting a recipe (or
    # its import_jobs row) doesn't free up quota. Compared against app_settings.max_imports_per_user
    # in routers/imports.py's create_import_job; admins are exempt from the cap.
    imported_recipes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
