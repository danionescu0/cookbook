from typing import Literal

from pydantic import BaseModel, Field

AiProvider = Literal["claude", "deepseek"]


class SettingsRead(BaseModel):
    supported_languages: str
    default_language: str
    anthropic_api_key_is_set: bool
    calorie_ninjas_api_key_is_set: bool
    default_rate_limit_requests_per_minute: int
    scrape_timeout_seconds: float
    max_html_chars: int
    image_max_dimension: int
    image_max_size_kb: int
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_from_address: str
    smtp_password_is_set: bool
    smtp_use_tls: bool
    # Not secret — embedded directly into the signup page's HTML, so it's returned as-is (unlike
    # turnstile_secret_key, which is only ever verified server-side and follows the *_is_set
    # convention like every other real secret here).
    turnstile_site_key: str
    turnstile_secret_key_is_set: bool
    public_site_url: str
    backoffice_recipes_page_size: int
    max_imports_per_user: int
    contact_recipient_email: str
    preferred_ai_provider: AiProvider
    deepseek_api_key_is_set: bool
    # Not secret — see app_settings.py's google_client_id docstring.
    google_client_id: str


class SettingsUpdate(BaseModel):
    supported_languages: str | None = None
    default_language: str | None = None
    anthropic_api_key: str | None = None
    calorie_ninjas_api_key: str | None = None
    default_rate_limit_requests_per_minute: int | None = Field(default=None, gt=0)
    scrape_timeout_seconds: float | None = Field(default=None, gt=0)
    max_html_chars: int | None = Field(default=None, gt=0)
    image_max_dimension: int | None = Field(default=None, gt=0)
    image_max_size_kb: int | None = Field(default=None, gt=0)
    smtp_host: str | None = None
    smtp_port: int | None = Field(default=None, gt=0)
    smtp_username: str | None = None
    smtp_from_address: str | None = None
    # Secrets: omit the field (or send "") to keep the current value — the UI never has the
    # real value to redisplay, so "blank means unchanged" is the only sane semantics.
    smtp_password: str | None = None
    smtp_use_tls: bool | None = None
    turnstile_site_key: str | None = None
    turnstile_secret_key: str | None = None
    public_site_url: str | None = None
    backoffice_recipes_page_size: int | None = Field(default=None, gt=0)
    max_imports_per_user: int | None = Field(default=None, gt=0)
    contact_recipient_email: str | None = None
    preferred_ai_provider: AiProvider | None = None
    # Secret: same "blank/omitted means keep current value" semantics as anthropic_api_key above.
    deepseek_api_key: str | None = None
    google_client_id: str | None = None
