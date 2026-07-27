from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://cookbook:change-me@db:5432/cookbook"
    rabbitmq_url: str = "amqp://cookbook:change-me@rabbitmq:5672/"
    images_dir: str = "data/images"

    # Single hard-coded admin account, stored in config — no users table, no self-registration.
    # Matches a self-hosted, single-operator tool: see README Design Decisions ("Back office
    # authentication").
    admin_username: str = "admin"
    jwt_secret: str = "change-me-too"
    jwt_expires_minutes: int = 60 * 24

    # Bootstrap-only: read once by migration 0006 to seed app_settings.admin_password on first
    # deploy, then ignored — the DB is authoritative from then on (change the password via
    # Backoffice > Settings, not here). See README Design Decisions ("Admin-editable settings").
    admin_password: str = "change-me"


settings = Settings()
