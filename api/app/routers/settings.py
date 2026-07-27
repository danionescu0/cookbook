from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models.app_settings import AppSettings
from app.schemas.settings import SettingsRead, SettingsUpdate
from app.settings_service import get_settings, update_settings

# Same reasoning as imports.py: every route here is back-office-only, so the whole router is
# protected at once rather than route by route.
router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(require_admin)])


def _serialize(row: AppSettings) -> SettingsRead:
    return SettingsRead(
        supported_languages=row.supported_languages,
        default_language=row.default_language,
        admin_password_is_set=bool(row.admin_password),
        anthropic_api_key_is_set=bool(row.anthropic_api_key),
        calorie_ninjas_api_key_is_set=bool(row.calorie_ninjas_api_key),
        default_rate_limit_requests_per_minute=row.default_rate_limit_requests_per_minute,
        scrape_timeout_seconds=row.scrape_timeout_seconds,
        max_html_chars=row.max_html_chars,
        image_max_dimension=row.image_max_dimension,
        image_max_size_kb=row.image_max_size_kb,
    )


@router.get("", response_model=SettingsRead)
def read_settings(db: Session = Depends(get_db)) -> SettingsRead:
    return _serialize(get_settings(db))


@router.patch("", response_model=SettingsRead)
def patch_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsRead:
    return _serialize(update_settings(db, payload))
