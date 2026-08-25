from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth import AuthUser, get_current_user, get_optional_current_user, require_admin
from app.database import get_db
from app.models.category import Category
from app.models.import_job import ImportJob
from app.models.nutrition_job import NutritionJob, NutritionJobStatus
from app.models.recipe import Recipe, RecipeStatus
from app.models.recipe_favorite import RecipeFavorite
from app.models.recipe_reparse_job import RecipeReparseJob, RecipeReparseJobStatus
from app.models.recipe_translation import RecipeTranslation
from app.models.translation_sync_job import TranslationSyncJob, TranslationSyncJobStatus
from app.models.user import User
from app.queue import publish_reparse_job, publish_translation_sync_job
from app.routers.images import delete_images
from app.schemas.recipe import RecipeCategoryUpdate, RecipeCreate, RecipeRead, RecipeShareUpdate, RecipeUpdate
from app.settings_service import get_settings
from app.slugify import generate_unique_slug

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


def _is_public_clause():
    return and_(Recipe.status == RecipeStatus.APPROVED, Recipe.is_shared.is_(True))


def _visibility_clause(viewer: AuthUser | None):
    public = _is_public_clause()
    if viewer is None:
        return public
    return or_(Recipe.owner_user_id == viewer.id, public)


def _escape_like(value: str) -> str:
    # Postgres ILIKE treats "%"/"_" as wildcards — escape them (and the escape char itself) so a
    # literal "%" typed by a user is matched literally, not as "anything".
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _unaccent_lower(expr):
    # f_unaccent is a DB-side function (Postgres: the IMMUTABLE wrapper created by migration 0036
    # around the unaccent extension; SQLite tests: a registered Python equivalent, see conftest.py)
    # so "Briose" and "Brioșe" match each other regardless of which side has the diacritics — see
    # README Design Decisions, "Recipe search".
    return func.lower(func.f_unaccent(expr))


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
_ACTIVE_REPARSE_STATUSES = (RecipeReparseJobStatus.QUEUED, RecipeReparseJobStatus.PROCESSING)


def _processing_statuses(db: Session, recipe_ids: list[int]) -> dict[int, str]:
    """recipe_id -> "translating" | "recalculating_nutrition" | "reparsing" for whichever
    recipes currently have a job in flight — so the back office can show that a just-saved edit
    (or a reparse) is still being propagated/re-enriched, not silently stuck. Checked as "any
    active job", not "is it the *latest* job" (unlike nutrition.py's status resolution): each
    queue processes one job per recipe at a time, so an old job left at queued/processing would
    mean something already went wrong (a worker crash), and that's exactly the case where
    surfacing "still processing" is most important, not least.
    """
    if not recipe_ids:
        return {}

    statuses: dict[int, str] = {}
    # Later assignments win when more than one is active for the same recipe — ordered earliest
    # pipeline phase last (reparse triggers a translation update, which the frontend never sees
    # as a separate translation-sync step; nutrition is re-enriched once reparse/translation
    # settles), so the *current* phase is always what's shown.
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
    for recipe_id in db.scalars(
        select(RecipeReparseJob.recipe_id).where(
            RecipeReparseJob.recipe_id.in_(recipe_ids),
            RecipeReparseJob.status.in_(_ACTIVE_REPARSE_STATUSES),
        )
    ):
        statuses[recipe_id] = "reparsing"
    return statuses


def _serialize(
    recipe: Recipe,
    language: str,
    default_language: str,
    processing_status: str | None = None,
    current_user: AuthUser | None = None,
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
        slug=translation.slug,
        description=translation.description,
        ingredients=translation.ingredients,
        steps=translation.steps,
        tips=translation.tips,
        available_languages=sorted(t.language for t in recipe.translations),
        processing_status=processing_status,
        owner_user_id=recipe.owner_user_id,
        owner_email=recipe.owner.email if current_user and current_user.is_admin else None,
        is_shared=recipe.is_shared,
        import_reviewed_at=recipe.import_reviewed_at,
    )


@router.get("", response_model=list[RecipeRead])
def list_recipes(
    response: Response,
    category_id: int | None = None,
    language: str | None = Query(default=None),
    # "me": only the caller's own recipes, any status — powers the frontend's "My recipes"
    # infinite scroll (requires auth; 401 for an anonymous caller). Any other value is treated as
    # a target user id and requires the caller to be an admin (403 otherwise) — powers the
    # superadmin Users page's per-user recipe list (see routers/users.py's list_users). Mutually
    # exclusive with only_public in practice, though nothing stops both being set — owner wins.
    owner: str | None = Query(default=None),
    # Forces the public-only visibility clause regardless of who's asking, admin included —
    # powers the "From the community" infinite scroll, so an authenticated user can fetch just
    # the shared+approved pool instead of the mixed "mine + public" result the default gives them.
    only_public: bool = Query(default=False),
    # Powers the front office's "Favorites" filter pill — combinable with category_id (both
    # narrow the same query), mutually exclusive with owner/only_public in practice since the
    # frontend never sends them together. Requires auth, same as owner="me".
    favorites_only: bool = Query(default=False),
    # Title-only substring filter, scoped to whichever language is actually being displayed (the
    # same `language or default_language` fallback _serialize uses) — see README Design
    # Decisions, "Recipe search". min_length is defense in depth; the frontend never sends fewer
    # than 3 characters either.
    search: str | None = Query(default=None, min_length=3),
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: AuthUser | None = Depends(get_optional_current_user),
) -> list[RecipeRead]:
    default_language = get_settings(db).default_language
    stmt = select(Recipe).options(selectinload(Recipe.translations), selectinload(Recipe.owner))
    count_stmt = select(func.count()).select_from(Recipe)

    if category_id is not None:
        stmt = stmt.where(Recipe.category_id == category_id)
        count_stmt = count_stmt.where(Recipe.category_id == category_id)

    if owner == "me":
        if current_user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        clause = Recipe.owner_user_id == current_user.id
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    elif owner is not None:
        if current_user is None or not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")
        try:
            target_id = int(owner)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid owner id")
        target = db.get(User, target_id)
        if target is None:
            raise HTTPException(status_code=404, detail="User not found")
        clause = Recipe.owner_user_id == target.id
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    elif only_public:
        clause = _is_public_clause()
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    elif favorites_only:
        if current_user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        stmt = stmt.join(RecipeFavorite, RecipeFavorite.recipe_id == Recipe.id).where(
            RecipeFavorite.user_id == current_user.id
        )
        count_stmt = count_stmt.join(RecipeFavorite, RecipeFavorite.recipe_id == Recipe.id).where(
            RecipeFavorite.user_id == current_user.id
        )
        # A favorite can outlive the recipe's visibility (e.g. the owner un-shares it after you
        # favorited it) — same clause list_my_favorites already applies, kept here rather than
        # leaking a since-hidden recipe back through this filter.
        visibility = _visibility_clause(current_user)
        stmt = stmt.where(visibility)
        count_stmt = count_stmt.where(visibility)
    elif current_user is None or not current_user.is_admin:
        stmt = stmt.where(_visibility_clause(current_user))
        count_stmt = count_stmt.where(_visibility_clause(current_user))

    if search and search.strip():
        # AND, not OR: every word must appear somewhere in the title (any order) — see README
        # Design Decisions, "Recipe search". Each word is its own .any() clause rather than one
        # combined ILIKE so "chicken soup" also matches "Soup with Chicken". Both sides go through
        # _unaccent_lower so a search matches regardless of which side (query or title) has
        # diacritics — "Briose" matches "Brioșe" and vice versa.
        search_language = language or default_language
        for word in search.strip().split():
            pattern = _unaccent_lower(f"%{_escape_like(word)}%")
            clause = Recipe.translations.any(
                (RecipeTranslation.language == search_language)
                & (_unaccent_lower(RecipeTranslation.title).ilike(pattern, escape="\\"))
            )
            stmt = stmt.where(clause)
            count_stmt = count_stmt.where(clause)

    response.headers["X-Total-Count"] = str(db.scalar(count_stmt) or 0)

    # id as a tie-breaker: added_at alone isn't unique enough to guarantee a stable order across
    # pages (same-second inserts are common, e.g. a bulk import) — without it, a tied row can be
    # skipped or repeated across two consecutive paginated requests.
    stmt = stmt.order_by(Recipe.added_at.desc(), Recipe.id.desc()).offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)

    recipes = list(db.scalars(stmt))
    statuses = _processing_statuses(db, [recipe.id for recipe in recipes])
    return [
        _serialize(
            recipe, language or default_language, default_language, statuses.get(recipe.id), current_user
        )
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
            slug=generate_unique_slug(db, language, payload.title),
        )
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return _serialize(recipe, language, app_settings.default_language, current_user=current_user)


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
    return _serialize(recipe, language or default_language, default_language, processing_status, current_user)


@router.post("/{recipe_id}/approve", response_model=RecipeRead)
def approve_recipe(
    recipe_id: int,
    language: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_admin),
) -> RecipeRead:
    default_language = get_settings(db).default_language
    recipe = _get_or_404(db, recipe_id)
    recipe.status = RecipeStatus.APPROVED
    recipe.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(recipe)
    processing_status = _processing_statuses(db, [recipe.id]).get(recipe.id)
    return _serialize(recipe, language or default_language, default_language, processing_status, current_user)


@router.put("/{recipe_id}", response_model=RecipeRead)
def update_recipe(
    recipe_id: int,
    payload: RecipeUpdate,
    language: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> RecipeRead:
    default_language = get_settings(db).default_language
    recipe = _get_or_404(db, recipe_id)
    # Owner-or-admin, same as sharing/category above — this is what lets a non-admin fix their own
    # recipe (e.g. after an import) rather than only ever viewing it.
    if not current_user.is_admin and recipe.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the owner or an admin can edit this recipe")
    target_language = language or default_language
    previous_images = list(recipe.images)

    updates = payload.model_dump(exclude_unset=True, exclude={"translation"})
    if not current_user.is_admin and "status" in updates:
        raise HTTPException(status_code=400, detail="Only an admin can change a recipe's status")
    if "category_id" in updates:
        _ensure_category_exists(db, updates["category_id"])

    for field, value in updates.items():
        setattr(recipe, field, value)

    translation_changed = False
    if payload.translation is not None:
        by_language = {t.language: t for t in recipe.translations}
        translation = by_language.get(target_language)
        is_new_translation = translation is None
        if translation is None:
            translation = RecipeTranslation(
                recipe_id=recipe.id, language=target_language, title="", description="", slug=""
            )
            recipe.translations.append(translation)

        translation_updates = payload.translation.model_dump(exclude_unset=True)
        for field, value in translation_updates.items():
            setattr(translation, field, value)
        translation_changed = bool(translation_updates)

        if is_new_translation:
            # Slug is generated once, here, and never auto-regenerated on later edits — see
            # RecipeTranslation.slug's docstring.
            translation.slug = generate_unique_slug(db, target_language, translation.title)

    db.commit()
    db.refresh(recipe)

    if "images" in updates:
        # Only ever the ones actually dropped from the list — a still-referenced image (or one
        # simply reordered) must not be touched. Same after-commit ordering as delete_recipe: an
        # orphaned file is recoverable, a live recipe with a missing photo isn't.
        removed_images = [url for url in previous_images if url not in recipe.images]
        delete_images(removed_images)

    if translation_changed:
        # Propagate this edit to the other languages and re-run nutrition once they're in sync
        # — see _enqueue_translation_sync_job. Runs for any edited field (not just ingredients):
        # title/description/steps/tips need to stay in sync across languages too.
        _enqueue_translation_sync_job(db, recipe.id, target_language)

    processing_status = _processing_statuses(db, [recipe.id]).get(recipe.id)
    return _serialize(recipe, target_language, default_language, processing_status, current_user)


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
    return _serialize(recipe, language or default_language, default_language, processing_status, current_user)


@router.patch("/{recipe_id}/category", response_model=RecipeRead)
def update_recipe_category(
    recipe_id: int,
    payload: RecipeCategoryUpdate,
    language: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> RecipeRead:
    # Owner-or-admin, same as sharing above — unlike sharing, this has no manual/imported
    # restriction: an import's category is only ever a guess made before the page was even
    # fetched, and a hand-authored recipe's owner already picks its category at creation time, so
    # there's no reason to let them fix one but not the other.
    default_language = get_settings(db).default_language
    recipe = _get_or_404(db, recipe_id)
    if not current_user.is_admin and recipe.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the owner or an admin can change the category")
    _ensure_category_exists(db, payload.category_id)

    recipe.category_id = payload.category_id
    db.commit()
    db.refresh(recipe)
    processing_status = _processing_statuses(db, [recipe.id]).get(recipe.id)
    return _serialize(recipe, language or default_language, default_language, processing_status, current_user)


@router.post("/{recipe_id}/acknowledge-import", response_model=RecipeRead)
def acknowledge_import(
    recipe_id: int,
    language: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> RecipeRead:
    # Clears the post-import review panel on the account page for this one recipe — see
    # frontend's PendingImportsPanel. Owner-or-admin, same pattern as sharing/category/update.
    default_language = get_settings(db).default_language
    recipe = _get_or_404(db, recipe_id)
    if not current_user.is_admin and recipe.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the owner or an admin can do this")
    if recipe.source_url is None:
        raise HTTPException(status_code=400, detail="This recipe wasn't imported — nothing to acknowledge")

    recipe.import_reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(recipe)
    processing_status = _processing_statuses(db, [recipe.id]).get(recipe.id)
    return _serialize(recipe, language or default_language, default_language, processing_status, current_user)


@router.delete("/{recipe_id}", status_code=204)
def delete_recipe(
    recipe_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> None:
    # Owner-or-admin, same pattern as sharing/category/update above — a regular user can already
    # do everything else to their own recipe, deleting it shouldn't be admin-only either.
    recipe = _get_or_404(db, recipe_id)
    if not current_user.is_admin and recipe.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the owner or an admin can delete this recipe")
    images = list(recipe.images)
    if recipe.source_url is not None:
        # POST /imports' duplicate-URL guard checks for *any* existing ImportJob row for this
        # URL/creator, regardless of whether its resulting recipe still exists — without this
        # cleanup, deleting an imported recipe and trying to re-import the same URL would
        # permanently 409 with "This URL is already in the import queue," even though nothing is
        # actually queued or imported anymore. created_by_user_id, not current_user.id: an admin
        # deleting someone else's import should free up *that owner's* URL, not the admin's own.
        db.execute(
            delete(ImportJob).where(
                ImportJob.source == recipe.source_url,
                ImportJob.created_by_user_id == recipe.owner_user_id,
            )
        )
    db.delete(recipe)
    db.commit()
    # After the commit, not before: if the DB delete somehow fails, the recipe (and its images)
    # are still around — an orphaned file is recoverable, a live recipe with missing photos isn't.
    delete_images(images)


def _create_reparse_job(db: Session, recipe_id: int) -> RecipeReparseJob:
    job = RecipeReparseJob(recipe_id=recipe_id, status=RecipeReparseJobStatus.QUEUED)
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        publish_reparse_job(job.id, recipe_id)
    except Exception as exc:
        job.status = RecipeReparseJobStatus.FAILED
        job.error = f"failed to publish to queue: {exc}"
        db.commit()
    return job


@router.post("/{recipe_id}/reparse", status_code=202, dependencies=[Depends(require_admin)])
def reparse_recipe(recipe_id: int, db: Session = Depends(get_db)) -> dict[str, int]:
    # Re-scrapes the recipe's existing source_url and updates its translations in place — used
    # to pick up extraction-quality fixes for recipes imported before those fixes existed. See
    # worker/app/reparse_handlers.py.
    recipe = _get_or_404(db, recipe_id)
    if not recipe.source_url:
        raise HTTPException(status_code=400, detail="Recipe has no source URL to reparse from")
    job = _create_reparse_job(db, recipe.id)
    return {"job_id": job.id}


@router.post("/reparse-all-imported", status_code=202, dependencies=[Depends(require_admin)])
def reparse_all_imported_recipes(db: Session = Depends(get_db)) -> dict[str, int]:
    recipe_ids = list(db.scalars(select(Recipe.id).where(Recipe.source_url.is_not(None))))
    for recipe_id in recipe_ids:
        _create_reparse_job(db, recipe_id)
    return {"queued": len(recipe_ids)}


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
        _serialize(recipe, default_language, default_language, statuses.get(recipe.id), current_user)
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
        _serialize(recipe, default_language, default_language, statuses.get(recipe.id), current_user)
        for recipe in recipes
    ]
