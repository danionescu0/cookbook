from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.models.category import Category
from app.models.recipe import Recipe, RecipeStatus
from app.models.recipe_translation import RecipeTranslation
from app.schemas.recipe import RecipeCreate, RecipeRead, RecipeUpdate

router = APIRouter(prefix="/recipes", tags=["recipes"])


def _get_or_404(db: Session, recipe_id: int) -> Recipe:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


def _ensure_category_exists(db: Session, category_id: int) -> None:
    if db.get(Category, category_id) is None:
        raise HTTPException(status_code=400, detail="Category does not exist")


def _looks_like_url(value: str) -> bool:
    return value.strip().lower().startswith(("http://", "https://"))


def _ensure_not_a_pasted_url(payload: RecipeCreate) -> None:
    # The recurring real-world mistake this guards against: pasting a recipe URL into this
    # manual-authoring form (title or an ingredient line) instead of using "Import from URL",
    # which actually fetches and translates the page. Catches the whole-field-is-a-URL case;
    # a URL embedded partway through a longer line (rare, and arguably intentional) still
    # goes through.
    fields = [payload.title, payload.description, *payload.ingredients, *payload.steps, *payload.tips]
    if any(_looks_like_url(value) for value in fields):
        raise HTTPException(
            status_code=400,
            detail='That looks like a URL — use "Import from URL" instead of adding a recipe manually.',
        )


def _resolve_translation(recipe: Recipe, language: str) -> RecipeTranslation:
    by_language = {t.language: t for t in recipe.translations}
    translation = by_language.get(language) or by_language.get(settings.default_language)
    return translation or next(iter(by_language.values()))


def _serialize(recipe: Recipe, language: str) -> RecipeRead:
    translation = _resolve_translation(recipe, language)
    return RecipeRead(
        id=recipe.id,
        category_id=recipe.category_id,
        images=recipe.images,
        source_url=recipe.source_url,
        status=recipe.status,
        added_at=recipe.added_at,
        approved_at=recipe.approved_at,
        language=translation.language,
        title=translation.title,
        description=translation.description,
        ingredients=translation.ingredients,
        steps=translation.steps,
        tips=translation.tips,
        available_languages=sorted(t.language for t in recipe.translations),
    )


@router.get("", response_model=list[RecipeRead])
def list_recipes(
    category_id: int | None = None,
    language: str = Query(default=settings.default_language),
    db: Session = Depends(get_db),
) -> list[RecipeRead]:
    stmt = (
        select(Recipe)
        .options(selectinload(Recipe.translations))
        .order_by(Recipe.added_at.desc())
    )
    if category_id is not None:
        stmt = stmt.where(Recipe.category_id == category_id)
    recipes = list(db.scalars(stmt))
    return [_serialize(recipe, language) for recipe in recipes]


@router.post("", response_model=RecipeRead, status_code=201)
def create_recipe(payload: RecipeCreate, db: Session = Depends(get_db)) -> RecipeRead:
    _ensure_category_exists(db, payload.category_id)
    _ensure_not_a_pasted_url(payload)

    language = payload.language or settings.default_language
    if language not in settings.supported_languages_list:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")

    recipe = Recipe(category_id=payload.category_id, images=payload.images)
    recipe.translations.append(
        RecipeTranslation(
            language=language,
            title=payload.title,
            description=payload.description,
            ingredients=payload.ingredients,
            steps=payload.steps,
            tips=payload.tips,
        )
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return _serialize(recipe, language)


@router.get("/{recipe_id}", response_model=RecipeRead)
def get_recipe(
    recipe_id: int,
    language: str = Query(default=settings.default_language),
    db: Session = Depends(get_db),
) -> RecipeRead:
    # Returns full detail regardless of status, so this also serves as the moderation
    # "preview" for unapproved recipes — no separate preview endpoint needed.
    recipe = _get_or_404(db, recipe_id)
    return _serialize(recipe, language)


@router.post("/{recipe_id}/approve", response_model=RecipeRead)
def approve_recipe(
    recipe_id: int,
    language: str = Query(default=settings.default_language),
    db: Session = Depends(get_db),
) -> RecipeRead:
    recipe = _get_or_404(db, recipe_id)
    recipe.status = RecipeStatus.APPROVED
    recipe.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(recipe)
    return _serialize(recipe, language)


@router.put("/{recipe_id}", response_model=RecipeRead)
def update_recipe(
    recipe_id: int,
    payload: RecipeUpdate,
    language: str = Query(default=settings.default_language),
    db: Session = Depends(get_db),
) -> RecipeRead:
    recipe = _get_or_404(db, recipe_id)

    updates = payload.model_dump(exclude_unset=True)
    if "category_id" in updates:
        _ensure_category_exists(db, updates["category_id"])

    for field, value in updates.items():
        setattr(recipe, field, value)

    db.commit()
    db.refresh(recipe)
    return _serialize(recipe, language)


@router.delete("/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int, db: Session = Depends(get_db)) -> None:
    recipe = _get_or_404(db, recipe_id)
    db.delete(recipe)
    db.commit()
