from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://cookbook:change-me@db:5432/cookbook"
    rabbitmq_url: str = "amqp://cookbook:change-me@rabbitmq:5672/"
    images_dir: str = "data/images"

    # Comma-separated language codes, e.g. "ro,en". Adding a language is a config change here,
    # not a migration — see README Design Decisions ("Multi-language content model").
    supported_languages: str = "ro,en"
    default_language: str = "ro"

    @property
    def supported_languages_list(self) -> list[str]:
        return [lang.strip() for lang in self.supported_languages.split(",") if lang.strip()]


settings = Settings()
