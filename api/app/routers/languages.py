from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/languages", tags=["languages"])


@router.get("")
def list_languages() -> dict[str, object]:
    return {"supported": settings.supported_languages_list, "default": settings.default_language}
