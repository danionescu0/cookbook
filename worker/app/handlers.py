import json
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.claude_client import RecipeExtractionError, extract_recipe, parse_recipe_from_text
from app.images import process_images
from app.instagram_client import InstagramFetchError, fetch_instagram_post
from app.models import (
    Category,
    ImportErrorKind,
    ImportJob,
    ImportJobStatus,
    ImportJobType,
    NutritionJob,
    NutritionJobStatus,
    Recipe,
    RecipeStatus,
    RecipeTranslation,
    User,
)
from app.queue import publish_nutrition_job
from app.scraping import ScrapeDisallowedError, fetch_page
from app.settings_service import SettingsSnapshot, get_settings
from app.slugify import generate_unique_slug

logger = logging.getLogger(__name__)


class NotARecipeError(Exception):
    """Extraction technically succeeded, but every returned translation was blank.

    Claude/DeepSeek is called with a forced tool choice (see claude_client.extract_recipe), so it
    has no way to say "there's no recipe here" — faced with a non-recipe page (most often a dead
    URL that now redirects somewhere unrelated, e.g. a since-deleted post redirecting to the
    site's homepage or the author's Instagram profile), it returns an otherwise-valid tool call
    with empty title/ingredients/steps instead. Left unchecked, that silently saves a real,
    `APPROVED` recipe row with nothing in it — see README Design Decisions.
    """


def _is_blank_translation(t: dict) -> bool:
    return not t.get("title", "").strip() and not t.get("ingredients") and not t.get("steps")


def _enqueue_nutrition_job(db: Session, recipe_id: int) -> None:
    # Mirrors what the old manual "Enrich nutrition" button used to do via
    # POST /recipes/{id}/nutrition — enrichment is now automatic, triggered right after a
    # successful import instead of by an admin click. See README Design Decisions
    # ("Ingredient nutrition").
    job = NutritionJob(recipe_id=recipe_id, status=NutritionJobStatus.QUEUED)
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        publish_nutrition_job(job.id, recipe_id)
    except Exception as exc:
        job.status = NutritionJobStatus.FAILED
        job.error = f"failed to publish to queue: {exc}"
        db.commit()


def _resolve_category_id(returned_name: str, categories: list[Category]) -> int:
    # Categories are admin-created, free-text rows (CategoryManager), not a fixed enum — Claude is
    # given the real list and asked to return one of those names verbatim (see claude_client.py's
    # _category_instruction), but nothing stops it from a typo, a case mismatch, or a name that no
    # longer exists by the time this runs. Falling back to the first category (stable, id order)
    # keeps the import succeeding either way — a wrong category is a quick fix via the owner's own
    # Edit page, not worth failing the whole import over.
    normalized = (returned_name or "").strip().lower()
    for category in categories:
        if category.name.strip().lower() == normalized:
            return category.id
    logger.warning(
        "Claude's suggested category %r matched none of %s — falling back to %r",
        returned_name, [c.name for c in categories], categories[0].name,
    )
    return categories[0].id


def _translations_from_data(db: Session, translations_data: list[dict]) -> list[RecipeTranslation]:
    return [
        RecipeTranslation(
            language=t["language"],
            title=t["title"],
            slug=generate_unique_slug(db, t["language"], t["title"]),
            description=t.get("description", ""),
            ingredients=t.get("ingredients", []),
            steps=t.get("steps", []),
            tips=t.get("tips", []),
        )
        for t in translations_data
    ]


def _finish_import(
    job: ImportJob,
    translations_data: list[dict],
    stored_images: list[str],
    category_id: int,
    db: Session,
    source_url: str,
) -> None:
    if not translations_data:
        raise RecipeExtractionError("Claude returned no translations")

    if all(_is_blank_translation(t) for t in translations_data):
        raise NotARecipeError("This page doesn't appear to contain a recipe")

    # Validate/construct before touching the DB: if this raises partway (e.g. a malformed
    # translation entry), nothing has been added to the session yet, so the caller's `except`
    # blocks can safely commit just the job status without leaving an orphan Recipe row behind.
    translations = _translations_from_data(db, translations_data)

    # An admin already explicitly approved importing this exact URL (see
    # POST /imports/{id}/approve), so a successful import publishes immediately rather than
    # landing as a second, separate `unapproved` moderation step.
    recipe = Recipe(
        category_id=category_id,
        images=stored_images,
        # The resolved URL actually fetched, not necessarily job.source — e.g. a Google
        # AMP-viewer link resolves to the real article (see scraping.fetch_page), and the "View
        # original recipe" link should point there, not back at a Google redirect page.
        source_url=source_url,
        status=RecipeStatus.APPROVED,
        approved_at=datetime.now(timezone.utc),
        translations=translations,
        # Imports are always private to whoever ran them — never shareable, see
        # routers/recipes.py's visibility rule and README migration 0020.
        owner_user_id=job.created_by_user_id,
        is_shared=False,
    )
    db.add(recipe)
    db.flush()  # assigns recipe.id, needed below, without committing yet

    # Lifetime counter for the import limit (see app_settings.max_imports_per_user in the API) —
    # incremented once per successful import, in the same transaction as the recipe insert, and
    # never decremented anywhere: deleting this recipe later must not free up quota.
    if job.created_by_user_id is not None:
        owner = db.get(User, job.created_by_user_id)
        if owner is not None:
            owner.imported_recipes_count += 1

    job.status = ImportJobStatus.DONE
    db.commit()

    try:
        _enqueue_nutrition_job(db, recipe.id)
    except Exception:
        # The import itself already succeeded and committed above — a problem enqueueing
        # nutrition enrichment (e.g. a DB hiccup) must not turn a successful import into a
        # reported failure.
        logger.exception("failed to auto-enqueue nutrition job for recipe %s", recipe.id)
        db.rollback()


def handle_import_job(body: bytes, db: Session) -> None:
    payload = json.loads(body)
    job_id = payload["job_id"]

    job = db.get(ImportJob, job_id)
    if job is None:
        logger.warning("import job %s not found, skipping", job_id)
        return

    # Read once per job (not once per HTTP call within it) — see settings_service.get_settings.
    app_settings = get_settings(db)

    job.status = ImportJobStatus.FETCHING
    db.commit()

    try:
        # The category is no longer picked by whoever created the job — Claude suggests one from
        # the real, current list, resolved to an id once extraction succeeds (see
        # _resolve_category_id). Fetched fresh per job, not cached, same reasoning as
        # settings_service.get_settings: an admin can add a category at any time.
        categories = list(db.scalars(select(Category).order_by(Category.id)))
        if not categories:
            raise RecipeExtractionError("No categories exist yet — create one in the back office first")
        category_names = [c.name for c in categories]

        if job.type == ImportJobType.INSTAGRAM:
            post = fetch_instagram_post(job.source, app_settings.scrape_timeout_seconds)
            job.status = ImportJobStatus.PROCESSING
            db.commit()

            # Same "cap what's sent to Claude" cost control as the HTML path's max_html_chars
            # below — the setting name predates this second fetch path but the concept (and the
            # config knob) is the same one, so it's reused rather than adding a near-duplicate.
            source_text = post.text[: app_settings.max_html_chars]
            extracted = parse_recipe_from_text(
                source_text,
                app_settings.supported_languages_list,
                app_settings.ai_api_key,
                category_names,
                provider=app_settings.preferred_ai_provider,
            )
            # Already resolved by fetch_instagram_post — nothing for Claude to find here, unlike
            # the HTML path where image URLs come out of the extraction itself.
            image_urls = [post.image_url] if post.image_url else []
            resolved_source_url = job.source
        else:
            resolved_source_url, html = fetch_page(job.source, app_settings)
            job.status = ImportJobStatus.PROCESSING
            db.commit()

            extracted = extract_recipe(
                html,
                app_settings.supported_languages_list,
                app_settings.ai_api_key,
                category_names,
                provider=app_settings.preferred_ai_provider,
            )
            # Joined against the page actually fetched, not job.source — the two can differ after
            # a redirect (e.g. a Google AMP-viewer link resolved to the real article, see
            # scraping.fetch_page), and a relative image URL on the page is relative to that real
            # article's own URL, not to whatever the requester originally pasted.
            image_urls = [urljoin(resolved_source_url, image) for image in extracted.get("images", [])]

        stored_images = process_images(image_urls, app_settings)
        category_id = _resolve_category_id(extracted.get("category", ""), categories)
        job.category_id = category_id
        _finish_import(
            job, extracted.get("translations", []), stored_images, category_id, db, resolved_source_url
        )
    except InstagramFetchError as exc:
        job.status = ImportJobStatus.FAILED
        job.error = str(exc)
        job.error_kind = ImportErrorKind.TECHNICAL
        db.commit()
    except ScrapeDisallowedError as exc:
        job.status = ImportJobStatus.FAILED
        job.error = str(exc)
        # Not a bug on our end — retrying won't help, so a non-admin viewer gets a distinct,
        # non-actionable message instead of the generic "an admin will take a look" one.
        job.error_kind = ImportErrorKind.DISALLOWED
        db.commit()
    except httpx.HTTPError as exc:
        job.status = ImportJobStatus.FAILED
        job.error = f"failed to fetch page: {exc}"
        job.error_kind = ImportErrorKind.TECHNICAL
        db.commit()
    except NotARecipeError as exc:
        job.status = ImportJobStatus.FAILED
        job.error = str(exc)
        # Not a bug on our end and retrying the same URL won't help — same "distinct,
        # non-actionable message" treatment as ScrapeDisallowedError above.
        job.error_kind = ImportErrorKind.NOT_A_RECIPE
        db.commit()
    except RecipeExtractionError as exc:
        job.status = ImportJobStatus.FAILED
        job.error = str(exc)
        job.error_kind = ImportErrorKind.TECHNICAL
        db.commit()
    except Exception as exc:
        logger.exception("unexpected error handling import job %s", job_id)
        job.status = ImportJobStatus.FAILED
        job.error = f"unexpected error: {exc}"
        job.error_kind = ImportErrorKind.TECHNICAL
        db.commit()
