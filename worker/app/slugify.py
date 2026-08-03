import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RecipeTranslation

# Kept in sync by hand with api/app/slugify.py — see the "Worker/API code sharing" design
# decision referenced elsewhere in this module (worker and api are separate deployable images,
# neither imports the other).
_EXTRA_CHAR_MAP = str.maketrans(
    {
        "ș": "s", "Ș": "S", "ş": "s", "Ş": "S",
        "ț": "t", "Ț": "T", "ţ": "t", "Ţ": "T",
    }
)

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_MAX_SLUG_LENGTH = 100


def slugify(text: str) -> str:
    text = text.translate(_EXTRA_CHAR_MAP)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = _NON_ALNUM_RE.sub("-", text).strip("-")

    if len(text) > _MAX_SLUG_LENGTH:
        text = text[:_MAX_SLUG_LENGTH].rsplit("-", 1)[0]

    return text or "recipe"


def generate_unique_slug(
    db: Session, language: str, title: str, exclude_translation_id: int | None = None
) -> str:
    base = slugify(title)
    candidate = base
    suffix = 2
    while True:
        stmt = select(RecipeTranslation.id).where(
            RecipeTranslation.language == language, RecipeTranslation.slug == candidate
        )
        if exclude_translation_id is not None:
            stmt = stmt.where(RecipeTranslation.id != exclude_translation_id)
        if db.scalar(stmt) is None:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1
