from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth import AuthUser, get_current_user, get_optional_current_user, require_admin
from app.database import get_db
from app.models.category import Category
from app.models.nutrition_job import NutritionJob, NutritionJobStatus
from app.models.recipe import Recipe, RecipeStatus
from app.models.recipe_favorite import RecipeFavorite
from app.models.recipe_translation import RecipeTranslation
from app.models.translation_sync_job import TranslationSyncJob, TranslationSyncJobStatus
from app.queue import publish_translation_sync_job
from app.schemas.recipe import RecipeCreate, RecipeRead, RecipeShareUpdate, RecipeUpdate
from app.settings_service import get_settings

router = APIRouter(prefix="/recipes", tags=["recipes"])
# Kept as a second router (rather than folding into router above) so the path prefix can be
# "/users/me" instead of "/recipes" while still sharing this module's serialization helpers.
me_router = APIRouter(prefix="/users/me", tags=["users"])


def _get_or_404(db: Session, recipe_id: int) -> Recipe:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


def _is_public(recipe: Recipe) -> bool:
    return recipe.status == RecipeStatus.APPROVED and recipe.is_shared


def _is_visible(recipe: Recipe, viewer: AuthUser | None) -> bool:
    # Private by default, per owner — see README/migration 0020. An admin can see everything
    # (needed for back-office moderation, which reuses these same routes); anyone else only sees
    # their own recipes (any status) plus whatever's been explicitly shared and approved.
    if viewer is not None and (viewer.is_admin or recipe.owner_user_id == viewer.id):
        return True
    return _is_public(recipe)


def _visibility_clause(viewer: AuthUser | None):
    public = and_(Recipe.status == RecipeStatus.APPROVED, Recipe.is_shared.is_(True))
    if viewer is None:
        return public
    return or_(Recipe.owner_user_id == viewer.id, public)


def _get_visible_or_404(db: Session, recipe_id: int, viewer: AuthUser | None) -> Recipe:
    recipe = _get_or_404(db, recipe_id)
    if not _is_visible(recipe, viewer):
        # 404, not 403 — a private recipe's existence isn't confirmed to someone who can't see it.
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
        owner_username=recipe.owner.username,
        is_shared=recipe.is_shared,
    )


@router.get("", response_model=list[RecipeRead])
def list_recipes(
    category_id: int | None = None,
    language: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: AuthUser | None = Depends(get_optional_current_user),
) -> list[RecipeRead]:
    default_language = get_settings(db).default_language
    stmt = (
        select(Recipe)
        .options(selectinload(Recipe.translations), selectinload(Recipe.owner))
        .order_by(Recipe.added_at.desc())
    )
    if category_id is not None:
        stmt = stmt.where(Recipe.category_id == category_id)
    if current_user is None or not current_user.is_admin:
        stmt = stmt.where(_visibility_clause(current_user))
    recipes = list(db.scalars(stmt))
    statuses = _processing_statuses(db, [recipe.id for recipe in recipes])
    return [
        _serialize(recipe, language or default_language, default_language, statuses.get(recipe.id))
        for recipe in recipes
    ]


@router.post("", response_model=RecipeRead, status_code=201)
def create_recipe(
    payload: RecipeCreate, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> RecipeRead:
    _ensure_category_exists(db, payload.category_id)
    _ensure_not_a_pasted_url(payload)

    app_settings = get_settings(db)
    language = payload.language or app_settings.default_language
    if language not in app_settings.supported_languages_list:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")

    recipe = Recipe(category_id=payload.category_id, images=payload.images, owner_user_id=current_user.id)
    if current_user.is_admin:
        # An admin's own choice takes effect immediately — they're already the moderator, so
        # there's no one else to review it.
        recipe.is_shared = payload.is_shared
    elif payload.is_shared:
        # Asking to share goes through the same moderation step an import/admin-create skips —
        # the model's own default (APPROVED) is what the admin path above relies on instead.
        recipe.status = RecipeStatus.UNAPPROVED
        recipe.is_shared = True
    # else: stays private (status APPROVED, is_shared False) — nothing to moderate when only the
    # owner will ever see it.
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
    current_user: AuthUser | None = Depends(get_optional_current_user),
) -> RecipeRead:
    # Returns full detail regardless of status (as long as it's visible to this viewer), so this
    # also serves as the moderation "preview" for unapproved recipes — no separate preview
    # endpoint needed.
    default_language = get_settings(db).default_language
    recipe = _get_visible_or_404(db, recipe_id, current_user)
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


@router.patch("/{recipe_id}/share", response_model=RecipeRead)
def update_recipe_sharing(
    recipe_id: int,
    payload: RecipeShareUpdate,
    language: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> RecipeRead:
    default_language = get_settings(db).default_language
    recipe = _get_or_404(db, recipe_id)
    if not current_user.is_admin and recipe.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the owner or an admin can change sharing")
    if recipe.source_url is not None:
        raise HTTPException(status_code=400, detail="Imported recipes can't be shared with the community")

    recipe.is_shared = payload.is_shared
    if payload.is_shared and not current_user.is_admin:
        # Re-review on every private-to-shared transition, same safeguard as sharing at creation
        # time — a non-admin's content never goes public without a look first.
        recipe.status = RecipeStatus.UNAPPROVED
    db.commit()
    db.refresh(recipe)
    processing_status = _processing_statuses(db, [recipe.id]).get(recipe.id)
    return _serialize(recipe, language or default_language, default_language, processing_status)


@router.delete("/{recipe_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_recipe(recipe_id: int, db: Session = Depends(get_db)) -> None:
    recipe = _get_or_404(db, recipe_id)
    db.delete(recipe)
    db.commit()


@router.post("/{recipe_id}/favorite", status_code=204)
def add_favorite(
    recipe_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> None:
    _get_visible_or_404(db, recipe_id, current_user)
    db.add(RecipeFavorite(user_id=current_user.id, recipe_id=recipe_id))
    try:
        db.commit()
    except IntegrityError:
        # Already favorited — adding it again is a no-op, not an error.
        db.rollback()


@router.delete("/{recipe_id}/favorite", status_code=204)
def remove_favorite(
    recipe_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> None:
    favorite = db.scalar(
        select(RecipeFavorite).where(
            RecipeFavorite.user_id == current_user.id, RecipeFavorite.recipe_id == recipe_id
        )
    )
    if favorite is not None:
        db.delete(favorite)
        db.commit()


@me_router.get("/favorites", response_model=list[RecipeRead])
def list_my_favorites(
    db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> list[RecipeRead]:
    default_language = get_settings(db).default_language
    stmt = (
        select(Recipe)
        .join(RecipeFavorite, RecipeFavorite.recipe_id == Recipe.id)
        .where(RecipeFavorite.user_id == current_user.id)
        # A favorite can outlive the recipe's visibility (e.g. the owner un-shares it after you
        # favorited it) — don't leak it back through this list once that happens.
        .where(_visibility_clause(current_user))
        .options(selectinload(Recipe.translations), selectinload(Recipe.owner))
        .order_by(RecipeFavorite.created_at.desc())
    )
    recipes = list(db.scalars(stmt))
    statuses = _processing_statuses(db, [recipe.id for recipe in recipes])
    return [
        _serialize(recipe, default_language, default_language, statuses.get(recipe.id))
        for recipe in recipes
    ]


@me_router.get("/submissions", response_model=list[RecipeRead])
def list_my_submissions(
    db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> list[RecipeRead]:
    default_language = get_settings(db).default_language
    stmt = (
        select(Recipe)
        .where(Recipe.owner_user_id == current_user.id)
        .options(selectinload(Recipe.translations), selectinload(Recipe.owner))
        .order_by(Recipe.added_at.desc())
    )
    recipes = list(db.scalars(stmt))
    statuses = _processing_statuses(db, [recipe.id for recipe in recipes])
    return [
        _serialize(recipe, default_language, default_language, statuses.get(recipe.id))
        for recipe in recipes
    ]
