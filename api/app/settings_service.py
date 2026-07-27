import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings as env_settings
from app.models.app_settings import AppSettings
from app.schemas.settings import SettingsUpdate

_LANGUAGE_CODE_RE = re.compile(r"^[a-z]{2,3}$")

SETTINGS_ROW_ID = 1


def get_settings(db: Session) -> AppSettings:
    row = db.get(AppSettings, SETTINGS_ROW_ID)
    if row is not None:
        return row

    # Defensive fallback for anything that skips the Alembic migration (e.g. the SQLite test
    # database, built from Base.metadata.create_all rather than `alembic upgrade head`). Mirrors
    # migration 0006's seed defaults — hardcoded here too, since these 7 fields are DB-only from
    # the start (never read from .env at all). admin_password is the one exception: it's still a
    # genuine bootstrap secret, so it comes from the .env-backed Settings object like the
    # migration does.
    row = AppSettings(
        id=SETTINGS_ROW_ID,
        supported_languages="ro,en",
        default_language="ro",
        admin_password=env_settings.admin_password,
        anthropic_api_key="",
        calorie_ninjas_api_key="",
        default_rate_limit_requests_per_minute=6,
        scrape_timeout_seconds=15.0,
        max_html_chars=200_000,
        image_max_dimension=1600,
        image_max_size_kb=500,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _parse_languages(raw: str) -> list[str]:
    codes = [code.strip().lower() for code in raw.split(",") if code.strip()]
    if not codes:
        raise HTTPException(status_code=400, detail="supported_languages cannot be empty")
    invalid = [code for code in codes if not _LANGUAGE_CODE_RE.match(code)]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language code(s): {', '.join(invalid)} (expected e.g. 'ro', 'en')",
        )
    # De-duplicate while preserving order.
    return list(dict.fromkeys(codes))


def update_settings(db: Session, patch: SettingsUpdate) -> AppSettings:
    row = get_settings(db)
    updates = patch.model_dump(exclude_unset=True)

    if "supported_languages" in updates:
        codes = _parse_languages(updates["supported_languages"])
        row.supported_languages = ",".join(codes)

    if "default_language" in updates:
        row.default_language = updates["default_language"].strip().lower()

    if row.default_language not in row.supported_languages_list:
        raise HTTPException(
            status_code=400,
            detail=(
                f"default_language '{row.default_language}' must be one of the "
                f"supported_languages ({row.supported_languages})"
            ),
        )

    # Blank/omitted secret means "leave unchanged" — the UI never has the real value to send back.
    if updates.get("admin_password"):
        row.admin_password = updates["admin_password"]
    if updates.get("anthropic_api_key"):
        row.anthropic_api_key = updates["anthropic_api_key"]
    if updates.get("calorie_ninjas_api_key"):
        row.calorie_ninjas_api_key = updates["calorie_ninjas_api_key"]

    for field in (
        "default_rate_limit_requests_per_minute",
        "scrape_timeout_seconds",
        "max_html_chars",
        "image_max_dimension",
        "image_max_size_kb",
    ):
        if field in updates:
            setattr(row, field, updates[field])

    db.commit()
    db.refresh(row)
    return row
