from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.settings_service import get_settings

router = APIRouter(prefix="/languages", tags=["languages"])


@router.get("")
def list_languages(db: Session = Depends(get_db)) -> dict[str, object]:
    row = get_settings(db)
    return {"supported": row.supported_languages_list, "default": row.default_language}
