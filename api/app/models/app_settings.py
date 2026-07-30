from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppSettings(Base):
    """Single-row table (id is always 1) holding the admin-editable subset of config.

    Once this row exists it is the source of truth for these fields — the matching .env vars
    only seed its initial value via migration 0006. See README Design Decisions
    ("Admin-editable settings"). Secrets (anthropic_api_key, smtp_password, ...) are stored in
    plaintext, matching this project's existing single-operator security posture (see
    "Back office authentication"). Per-user login credentials live in the `users` table instead
    (password hashed) — admin_password was removed once auth became per-user.
    """

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    supported_languages: Mapped[str] = mapped_column(String(100), nullable=False)
    default_language: Mapped[str] = mapped_column(String(10), nullable=False)
    anthropic_api_key: Mapped[str] = mapped_column(String(200), nullable=False)
    # CalorieNinjas API key, used by the nutrition-enrichment job — see README Design Decisions
    # ("Ingredient nutrition"). Get a free one at calorieninjas.com/api.
    calorie_ninjas_api_key: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    default_rate_limit_requests_per_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    scrape_timeout_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    max_html_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    image_max_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    image_max_size_kb: Mapped[int] = mapped_column(Integer, nullable=False)

    # SMTP, used by the worker to send account-verification emails — see
    # worker/app/email_handlers.py.
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    smtp_username: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    smtp_password: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    smtp_from_address: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Cloudflare Turnstile, gating self-service signup — the site key isn't secret (it's embedded
    # in the signup page's HTML), the secret key is used server-side to verify a solved token.
    turnstile_site_key: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    turnstile_secret_key: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # Used to build the link inside verification emails, e.g. "https://cookbook.example.com" +
    # "/verify-email?token=...". Not derivable from the request the way an API route can use its
    # own host, since this link is built by the worker, which never sees an HTTP request at all.
    public_site_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    @property
    def supported_languages_list(self) -> list[str]:
        return [lang.strip() for lang in self.supported_languages.split(",") if lang.strip()]
