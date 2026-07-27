from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppSettings(Base):
    """Single-row table (id is always 1) holding the admin-editable subset of config.

    Once this row exists it is the source of truth for these fields — the matching .env vars
    only seed its initial value via migration 0006. See README Design Decisions
    ("Admin-editable settings"). Secrets (admin_password, anthropic_api_key) are stored in
    plaintext, matching this project's existing single-operator security posture (see
    "Back office authentication").
    """

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    supported_languages: Mapped[str] = mapped_column(String(100), nullable=False)
    default_language: Mapped[str] = mapped_column(String(10), nullable=False)
    admin_password: Mapped[str] = mapped_column(String(200), nullable=False)
    anthropic_api_key: Mapped[str] = mapped_column(String(200), nullable=False)
    default_rate_limit_requests_per_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    scrape_timeout_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    max_html_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    image_max_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    image_max_size_kb: Mapped[int] = mapped_column(Integer, nullable=False)

    @property
    def supported_languages_list(self) -> list[str]:
        return [lang.strip() for lang in self.supported_languages.split(",") if lang.strip()]
