from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://cookbook:change-me@db:5432/cookbook"
    rabbitmq_url: str = "amqp://cookbook:change-me@rabbitmq:5672/"
    images_dir: str = "data/images"

    # Signs/verifies login JWTs. Auth itself is now per-user (see the `users` table / auth.py) —
    # this is just the shared signing secret, still .env-only since rotating it should invalidate
    # every existing session at once, which a DB-editable setting wouldn't guarantee (a stale
    # worker/API process would keep trusting old tokens signed with the old value).
    jwt_secret: str = "change-me-too"
    jwt_expires_minutes: int = 60 * 24


settings = Settings()
