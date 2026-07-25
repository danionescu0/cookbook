from datetime import datetime

from pydantic import BaseModel

from app.models.recipe import RecipeStatus


class RecipeCreate(BaseModel):
    category_id: int
    images: list[str] = []
    # Defaults to settings.default_language if omitted.
    language: str | None = None
    title: str
    description: str = ""
    ingredients: list[str] = []
    steps: list[str] = []
    tips: list[str] = []


class RecipeUpdate(BaseModel):
    category_id: int | None = None
    status: RecipeStatus | None = None


class RecipeRead(BaseModel):
    id: int
    category_id: int
    images: list[str]
    source_url: str | None
    status: RecipeStatus
    added_at: datetime
    approved_at: datetime | None

    # Resolved translation: `language` is what actually got returned, which may differ from what
    # was requested if that translation didn't exist (falls back to the site's default language).
    language: str
    title: str
    description: str
    ingredients: list[str]
    steps: list[str]
    tips: list[str]
    available_languages: list[str]
