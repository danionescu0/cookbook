from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://cookbook:change-me@db:5432/cookbook"
    rabbitmq_url: str = "amqp://cookbook:change-me@rabbitmq:5672/"

    anthropic_api_key: str = ""

    # Comma-separated language codes, e.g. "ro,en". Adding a language is a config change here,
    # not a migration — see README Design Decisions ("Multi-language content model").
    supported_languages: str = "ro,en"
    default_language: str = "ro"

    scrape_user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    default_rate_limit_requests_per_minute: int = 6
    scrape_timeout_seconds: float = 15.0
    max_html_chars: int = 200_000

    images_dir: str = "data/images"
    image_max_dimension: int = 1600
    image_max_size_kb: int = 500

    @property
    def supported_languages_list(self) -> list[str]:
        return [lang.strip() for lang in self.supported_languages.split(",") if lang.strip()]


settings = Settings()
