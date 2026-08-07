from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_super_admin
from app.database import get_db
from app.models.app_settings import AppSettings
from app.schemas.settings import SettingsRead, SettingsUpdate
from app.settings_service import get_settings, update_settings

# Stricter than the rest of the back office (require_admin) — this page holds API keys, SMTP
# credentials, and the Turnstile secret, so it's gated to the super-admin tier instead. See
# users.is_super_admin.
router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(require_super_admin)])


def _serialize(row: AppSettings) -> SettingsRead:
    return SettingsRead(
        supported_languages=row.supported_languages,
        default_language=row.default_language,
        anthropic_api_key_is_set=bool(row.anthropic_api_key),
        calorie_ninjas_api_key_is_set=bool(row.calorie_ninjas_api_key),
        default_rate_limit_requests_per_minute=row.default_rate_limit_requests_per_minute,
        scrape_timeout_seconds=row.scrape_timeout_seconds,
        max_html_chars=row.max_html_chars,
        image_max_dimension=row.image_max_dimension,
        image_max_size_kb=row.image_max_size_kb,
        smtp_host=row.smtp_host,
        smtp_port=row.smtp_port,
        smtp_username=row.smtp_username,
        smtp_from_address=row.smtp_from_address,
        smtp_password_is_set=bool(row.smtp_password),
        smtp_use_tls=row.smtp_use_tls,
        turnstile_site_key=row.turnstile_site_key,
        turnstile_secret_key_is_set=bool(row.turnstile_secret_key),
        public_site_url=row.public_site_url,
        backoffice_recipes_page_size=row.backoffice_recipes_page_size,
        max_imports_per_user=row.max_imports_per_user,
        contact_recipient_email=row.contact_recipient_email,
    )


@router.get("", response_model=SettingsRead)
def read_settings(db: Session = Depends(get_db)) -> SettingsRead:
    return _serialize(get_settings(db))


@router.patch("", response_model=SettingsRead)
def patch_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsRead:
    return _serialize(update_settings(db, payload))
