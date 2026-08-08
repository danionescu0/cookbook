from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import AppSettings

SETTINGS_ROW_ID = 1


@dataclass(frozen=True)
class SettingsSnapshot:
    supported_languages: str
    default_language: str
    anthropic_api_key: str
    calorie_ninjas_api_key: str
    default_rate_limit_requests_per_minute: int
    scrape_timeout_seconds: float
    max_html_chars: int
    image_max_dimension: int
    image_max_size_kb: int
    # Defaulted (unlike the fields above) so existing test call sites that predate SMTP support
    # and only care about scraping/nutrition settings don't all need updating.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = ""
    smtp_use_tls: bool = True
    public_site_url: str = ""
    contact_recipient_email: str = ""
    preferred_ai_provider: str = "claude"
    deepseek_api_key: str = ""

    @property
    def supported_languages_list(self) -> list[str]:
        return [lang.strip() for lang in self.supported_languages.split(",") if lang.strip()]

    @property
    def ai_api_key(self) -> str:
        # The key claude_client.py should actually use, resolved by preferred_ai_provider — so
        # every call site can pass (preferred_ai_provider, ai_api_key) without re-deriving this
        # itself.
        if self.preferred_ai_provider == "deepseek":
            return self.deepseek_api_key
        return self.anthropic_api_key


def get_settings(db: Session) -> SettingsSnapshot:
    """Reads the current admin-editable settings fresh from the DB.

    Called once per import/nutrition job, not per HTTP call within a job — one row read per job
    is cheap and means a setting change an admin applies takes effect on the very next job the
    worker picks up, with no cache to go stale and no restart.
    """
    row = db.get(AppSettings, SETTINGS_ROW_ID)
    if row is None:
        # Defensive fallback — mirrors api's migration 0006/0007 seed defaults /
        # app.config.Settings. Shouldn't happen once the api container has applied migrations.
        return SettingsSnapshot(
            supported_languages="ro,en",
            default_language="ro",
            anthropic_api_key="",
            calorie_ninjas_api_key="",
            default_rate_limit_requests_per_minute=6,
            scrape_timeout_seconds=15.0,
            max_html_chars=200_000,
            image_max_dimension=1600,
            image_max_size_kb=500,
            smtp_host="",
            smtp_port=587,
            smtp_username="",
            smtp_password="",
            smtp_from_address="",
            smtp_use_tls=True,
            public_site_url="",
            contact_recipient_email="",
            preferred_ai_provider="claude",
            deepseek_api_key="",
        )
    return SettingsSnapshot(
        supported_languages=row.supported_languages,
        default_language=row.default_language,
        anthropic_api_key=row.anthropic_api_key,
        calorie_ninjas_api_key=row.calorie_ninjas_api_key,
        default_rate_limit_requests_per_minute=row.default_rate_limit_requests_per_minute,
        scrape_timeout_seconds=row.scrape_timeout_seconds,
        max_html_chars=row.max_html_chars,
        image_max_dimension=row.image_max_dimension,
        image_max_size_kb=row.image_max_size_kb,
        smtp_host=row.smtp_host,
        smtp_port=row.smtp_port,
        smtp_username=row.smtp_username,
        smtp_password=row.smtp_password,
        smtp_from_address=row.smtp_from_address,
        smtp_use_tls=row.smtp_use_tls,
        public_site_url=row.public_site_url,
        contact_recipient_email=row.contact_recipient_email,
        preferred_ai_provider=row.preferred_ai_provider,
        deepseek_api_key=row.deepseek_api_key,
    )
