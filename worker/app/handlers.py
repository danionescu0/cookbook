import json
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from sqlalchemy.orm import Session

from app.claude_client import RecipeExtractionError, extract_recipe, parse_recipe_from_text
from app.images import process_images
from app.instagram_client import InstagramFetchError, fetch_instagram_post
from app.models import (
    ImportJob,
    ImportJobStatus,
    ImportJobType,
    NutritionJob,
    NutritionJobStatus,
    Recipe,
    RecipeStatus,
    RecipeTranslation,
)
from app.queue import publish_nutrition_job
from app.scraping import ScrapeDisallowedError, fetch_page
from app.settings_service import SettingsSnapshot, get_settings

logger = logging.getLogger(__name__)


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


def _translations_from_data(translations_data: list[dict]) -> list[RecipeTranslation]:
    return [
        RecipeTranslation(
            language=t["language"],
            title=t["title"],
            description=t.get("description", ""),
            ingredients=t.get("ingredients", []),
            steps=t.get("steps", []),
            tips=t.get("tips", []),
        )
        for t in translations_data
    ]


def _finish_import(
    job: ImportJob, translations_data: list[dict], stored_images: list[str], db: Session
) -> None:
    if not translations_data:
        raise RecipeExtractionError("Claude returned no translations")

    # Validate/construct before touching the DB: if this raises partway (e.g. a malformed
    # translation entry), nothing has been added to the session yet, so the caller's `except`
    # blocks can safely commit just the job status without leaving an orphan Recipe row behind.
    translations = _translations_from_data(translations_data)

    # An admin already explicitly approved importing this exact URL (see
    # POST /imports/{id}/approve), so a successful import publishes immediately rather than
    # landing as a second, separate `unapproved` moderation step.
    recipe = Recipe(
        category_id=job.category_id,
        images=stored_images,
        source_url=job.source,
        status=RecipeStatus.APPROVED,
        approved_at=datetime.now(timezone.utc),
        translations=translations,
    )
    db.add(recipe)
    db.flush()  # assigns recipe.id, needed below, without committing yet

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
        if job.type == ImportJobType.INSTAGRAM:
            post = fetch_instagram_post(job.source, app_settings.scrape_timeout_seconds)
            job.status = ImportJobStatus.PROCESSING
            db.commit()

            # Same "cap what's sent to Claude" cost control as the HTML path's max_html_chars
            # below — the setting name predates this second fetch path but the concept (and the
            # config knob) is the same one, so it's reused rather than adding a near-duplicate.
            source_text = post.text[: app_settings.max_html_chars]
            extracted = parse_recipe_from_text(
                source_text, app_settings.supported_languages_list, app_settings.anthropic_api_key
            )
            # Already resolved by fetch_instagram_post — nothing for Claude to find here, unlike
            # the HTML path where image URLs come out of the extraction itself.
            image_urls = [post.image_url] if post.image_url else []
        else:
            html = fetch_page(job.source, app_settings)
            job.status = ImportJobStatus.PROCESSING
            db.commit()

            extracted = extract_recipe(
                html, app_settings.supported_languages_list, app_settings.anthropic_api_key
            )
            image_urls = [urljoin(job.source, image) for image in extracted.get("images", [])]

        stored_images = process_images(image_urls, app_settings)
        _finish_import(job, extracted.get("translations", []), stored_images, db)
    except InstagramFetchError as exc:
        job.status = ImportJobStatus.FAILED
        job.error = str(exc)
        db.commit()
    except ScrapeDisallowedError as exc:
        job.status = ImportJobStatus.FAILED
        job.error = str(exc)
        db.commit()
    except httpx.HTTPError as exc:
        job.status = ImportJobStatus.FAILED
        job.error = f"failed to fetch page: {exc}"
        db.commit()
    except RecipeExtractionError as exc:
        job.status = ImportJobStatus.FAILED
        job.error = str(exc)
        db.commit()
    except Exception as exc:
        logger.exception("unexpected error handling import job %s", job_id)
        job.status = ImportJobStatus.FAILED
        job.error = f"unexpected error: {exc}"
        db.commit()
