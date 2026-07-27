from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://cookbook:change-me@db:5432/cookbook"
    rabbitmq_url: str = "amqp://cookbook:change-me@rabbitmq:5672/"

    # Bootstrap-only: read once by migration 0006 to seed app_settings.anthropic_api_key on first
    # deploy, then ignored — the DB is authoritative from then on (edit via Backoffice > Settings,
    # not here). See README Design Decisions ("Admin-editable settings"). Not used anywhere else
    # at runtime; kept here only so this module stays "the .env reader" for the whole app.
    anthropic_api_key: str = ""

    scrape_user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    images_dir: str = "data/images"


settings = Settings()
