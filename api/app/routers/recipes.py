from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import require_admin
from app.database import get_db
from app.models.category import Category
from app.models.nutrition_job import NutritionJob, NutritionJobStatus
from app.models.recipe import Recipe, RecipeStatus
from app.models.recipe_translation import RecipeTranslation
from app.models.translation_sync_job import TranslationSyncJob, TranslationSyncJobStatus
from app.queue import publish_translation_sync_job
from app.schemas.recipe import RecipeCreate, RecipeRead, RecipeUpdate
from app.settings_service import get_settings

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


def _enqueue_translation_sync_job(db: Session, recipe_id: int, source_language: str) -> None:
    # Hand-editing one language's translation must not leave the others behind: the worker
    # translates this edit into every other supported language via Claude, then re-runs
    # nutrition enrichment once everything (including whatever language nutrition parsing
    # actually reads) is back in sync. See app.models.translation_sync_job.
    job = TranslationSyncJob(
        recipe_id=recipe_id, source_language=source_language, status=TranslationSyncJobStatus.QUEUED
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        publish_translation_sync_job(job.id, recipe_id)
    except Exception as exc:
        job.status = TranslationSyncJobStatus.FAILED
        job.error = f"failed to publish to queue: {exc}"
        db.commit()


def _resolve_translation(recipe: Recipe, language: str, default_language: str) -> RecipeTranslation:
    by_language = {t.language: t for t in recipe.translations}
    translation = by_language.get(language) or by_language.get(default_language)
    return translation or next(iter(by_language.values()))


_ACTIVE_NUTRITION_STATUSES = (NutritionJobStatus.QUEUED, NutritionJobStatus.PROCESSING)
_ACTIVE_SYNC_STATUSES = (TranslationSyncJobStatus.QUEUED, TranslationSyncJobStatus.PROCESSING)


def _processing_statuses(db: Session, recipe_ids: list[int]) -> dict[int, str]:
    """recipe_id -> "translating" | "recalculating_nutrition" for whichever recipes currently
    have a job in flight — so the back office can show that a just-saved edit is still being
    propagated/re-enriched, not silently stuck. Checked as "any active job", not "is it the
    *latest* job" (unlike nutrition.py's status resolution): the two queues process one job per
    recipe at a time, so an old job left at queued/processing would mean something already went
    wrong (a worker crash), and that's exactly the case where surfacing "still processing" is
    most important, not least.
    """
    if not recipe_ids:
        return {}

    statuses: dict[int, str] = {}
    # Nutrition first, so translating (which triggers nutrition next) wins if both happen to be
    # active for the same recipe at once — it's the earlier phase of the same edit's pipeline.
    for recipe_id in db.scalars(
        select(NutritionJob.recipe_id).where(
            NutritionJob.recipe_id.in_(recipe_ids), NutritionJob.status.in_(_ACTIVE_NUTRITION_STATUSES)
        )
    ):
        statuses[recipe_id] = "recalculating_nutrition"
    for recipe_id in db.scalars(
        select(TranslationSyncJob.recipe_id).where(
            TranslationSyncJob.recipe_id.in_(recipe_ids),
            TranslationSyncJob.status.in_(_ACTIVE_SYNC_STATUSES),
        )
    ):
        statuses[recipe_id] = "translating"
    return statuses


def _serialize(
    recipe: Recipe, language: str, default_language: str, processing_status: str | None = None
) -> RecipeRead:
    translation = _resolve_translation(recipe, language, default_language)
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
        processing_status=processing_status,
    )


@router.get("", response_model=list[RecipeRead])
def list_recipes(
    category_id: int | None = None,
    language: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[RecipeRead]:
    default_language = get_settings(db).default_language
    stmt = (
        select(Recipe)
        .options(selectinload(Recipe.translations))
        .order_by(Recipe.added_at.desc())
    )
    if category_id is not None:
        stmt = stmt.where(Recipe.category_id == category_id)
    recipes = list(db.scalars(stmt))
    statuses = _processing_statuses(db, [recipe.id for recipe in recipes])
    return [
        _serialize(recipe, language or default_language, default_language, statuses.get(recipe.id))
        for recipe in recipes
    ]


@router.post("", response_model=RecipeRead, status_code=201, dependencies=[Depends(require_admin)])
def create_recipe(payload: RecipeCreate, db: Session = Depends(get_db)) -> RecipeRead:
    _ensure_category_exists(db, payload.category_id)
    _ensure_not_a_pasted_url(payload)

    app_settings = get_settings(db)
    language = payload.language or app_settings.default_language
    if language not in app_settings.supported_languages_list:
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
    return _serialize(recipe, language, app_settings.default_language)


@router.get("/{recipe_id}", response_model=RecipeRead)
def get_recipe(
    recipe_id: int,
    language: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RecipeRead:
    # Returns full detail regardless of status, so this also serves as the moderation
    # "preview" for unapproved recipes — no separate preview endpoint needed.
    default_language = get_settings(db).default_language
    recipe = _get_or_404(db, recipe_id)
    processing_status = _processing_statuses(db, [recipe.id]).get(recipe.id)
    return _serialize(recipe, language or default_language, default_language, processing_status)


@router.post(
    "/{recipe_id}/approve", response_model=RecipeRead, dependencies=[Depends(require_admin)]
)
def approve_recipe(
    recipe_id: int,
    language: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RecipeRead:
    default_language = get_settings(db).default_language
    recipe = _get_or_404(db, recipe_id)
    recipe.status = RecipeStatus.APPROVED
    recipe.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(recipe)
    processing_status = _processing_statuses(db, [recipe.id]).get(recipe.id)
    return _serialize(recipe, language or default_language, default_language, processing_status)


@router.put("/{recipe_id}", response_model=RecipeRead, dependencies=[Depends(require_admin)])
def update_recipe(
    recipe_id: int,
    payload: RecipeUpdate,
    language: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RecipeRead:
    default_language = get_settings(db).default_language
    recipe = _get_or_404(db, recipe_id)
    target_language = language or default_language

    updates = payload.model_dump(exclude_unset=True, exclude={"translation"})
    if "category_id" in updates:
        _ensure_category_exists(db, updates["category_id"])

    for field, value in updates.items():
        setattr(recipe, field, value)

    translation_changed = False
    if payload.translation is not None:
        by_language = {t.language: t for t in recipe.translations}
        translation = by_language.get(target_language)
        if translation is None:
            translation = RecipeTranslation(
                recipe_id=recipe.id, language=target_language, title="", description=""
            )
            recipe.translations.append(translation)

        translation_updates = payload.translation.model_dump(exclude_unset=True)
        for field, value in translation_updates.items():
            setattr(translation, field, value)
        translation_changed = bool(translation_updates)

    db.commit()
    db.refresh(recipe)

    if translation_changed:
        # Propagate this edit to the other languages and re-run nutrition once they're in sync
        # — see _enqueue_translation_sync_job. Runs for any edited field (not just ingredients):
        # title/description/steps/tips need to stay in sync across languages too.
        _enqueue_translation_sync_job(db, recipe.id, target_language)

    processing_status = _processing_statuses(db, [recipe.id]).get(recipe.id)
    return _serialize(recipe, target_language, default_language, processing_status)


@router.delete("/{recipe_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_recipe(recipe_id: int, db: Session = Depends(get_db)) -> None:
    recipe = _get_or_404(db, recipe_id)
    db.delete(recipe)
    db.commit()
