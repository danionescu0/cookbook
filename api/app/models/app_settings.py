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
    # Page size for the backoffice's classic numbered recipe pagination — see
    # routers/recipes.py's list_recipes. Not secret, so it's readable via GET /settings/public
    # (a plain admin, not just a super-admin, needs it, and that's the endpoint already reachable
    # without the super-admin gate on GET /settings).
    backoffice_recipes_page_size: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    # Lifetime cap on how many recipes a non-admin user may ever import, counting successful
    # imports even after the recipe (or its import_jobs row) is deleted — see
    # users.imported_recipes_count and routers/imports.py's create_import_job. Admins are exempt.
    # Not secret, so it's readable via GET /settings/public alongside backoffice_recipes_page_size
    # — the Account page needs it to show usage before anything becomes public.
    max_imports_per_user: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    # Where the worker sends a contact-form notification email (see
    # worker/app/contact_handlers.py) — not secret (it's not a credential), but not exposed via
    # GET /settings/public either, since it has no front-end use before a submission happens.
    # Blank means "not configured yet": the worker fails a queued contact_messages job cleanly
    # with an actionable error rather than sending nowhere.
    contact_recipient_email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # Which LLM provider extraction/translation calls use — see worker/app/claude_client.py.
    # DeepSeek is reached through its own Anthropic-API-compatible endpoint (same Messages API
    # wire format, including forced tool_choice), so switching providers is just this flag plus
    # deepseek_api_key below, no worker code change. See README Design Decisions ("DeepSeek as an
    # alternate AI provider").
    preferred_ai_provider: Mapped[str] = mapped_column(String(20), nullable=False, default="claude")
    deepseek_api_key: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # Google OAuth Web Client ID, gating "Sign in with Google" — not secret (it's embedded in the
    # signup/login pages' HTML), same reasoning as turnstile_site_key. No client secret is stored
    # anywhere: the sign-in flow verifies the ID token's signature against Google's own public
    # keys rather than a server-to-server code exchange, so no secret is ever needed.
    google_client_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    @property
    def supported_languages_list(self) -> list[str]:
        return [lang.strip() for lang in self.supported_languages.split(",") if lang.strip()]
