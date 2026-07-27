from pydantic import BaseModel, Field


class SettingsRead(BaseModel):
    supported_languages: str
    default_language: str
    admin_password_is_set: bool
    anthropic_api_key_is_set: bool
    calorie_ninjas_api_key_is_set: bool
    default_rate_limit_requests_per_minute: int
    scrape_timeout_seconds: float
    max_html_chars: int
    image_max_dimension: int
    image_max_size_kb: int


class SettingsUpdate(BaseModel):
    supported_languages: str | None = None
    default_language: str | None = None
    # Secrets: omit the field (or send "") to keep the current value — the UI never has the
    # real value to redisplay, so "blank means unchanged" is the only sane semantics.
    admin_password: str | None = None
    anthropic_api_key: str | None = None
    calorie_ninjas_api_key: str | None = None
    default_rate_limit_requests_per_minute: int | None = Field(default=None, gt=0)
    scrape_timeout_seconds: float | None = Field(default=None, gt=0)
    max_html_chars: int | None = Field(default=None, gt=0)
    image_max_dimension: int | None = Field(default=None, gt=0)
    image_max_size_kb: int | None = Field(default=None, gt=0)
