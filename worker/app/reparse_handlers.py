import json
import logging
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.claude_client import RecipeExtractionError, extract_recipe, parse_recipe_from_text
from app.handlers import _enqueue_nutrition_job
from app.instagram_client import InstagramFetchError, fetch_instagram_post
from app.models import Category, Recipe, RecipeReparseJob, RecipeReparseJobStatus, RecipeTranslation
from app.scraping import ScrapeDisallowedError, fetch_page
from app.settings_service import get_settings
from app.slugify import generate_unique_slug

logger = logging.getLogger(__name__)

# Kept in sync by hand with api/app/routers/imports.py's _detect_job_type — same detection,
# duplicated because worker and api are separate deployable images.
_INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com", "instagr.am"}


def _is_instagram_url(url: str) -> bool:
    return (urlparse(url).hostname or "") in _INSTAGRAM_HOSTS


def _update_translations_in_place(
    db: Session, recipe: Recipe, translations_data: list[dict]
) -> None:
    by_language = {t.language: t for t in recipe.translations}
    for t in translations_data:
        translation = by_language.get(t["language"])
        if translation is None:
            # A language that didn't exist on this recipe before (e.g. supported_languages grew
            # since the original import) — gets a fresh slug, same as any brand-new translation.
            translation = RecipeTranslation(
                recipe_id=recipe.id,
                language=t["language"],
                title=t["title"],
                slug=generate_unique_slug(db, t["language"], t["title"]),
            )
            recipe.translations.append(translation)
            by_language[t["language"]] = translation
        # An existing translation's slug is deliberately left untouched — see
        # RecipeTranslation.slug's docstring (immutable once set, so a reparse never breaks an
        # already-published URL even if the title text comes back slightly different).
        translation.title = t["title"]
        translation.description = t.get("description", "")
        translation.ingredients = t.get("ingredients", [])
        translation.steps = t.get("steps", [])
        translation.tips = t.get("tips", [])


def handle_reparse_job(body: bytes, db: Session) -> None:
    payload = json.loads(body)
    job_id = payload["job_id"]
    recipe_id = payload["recipe_id"]

    job = db.get(RecipeReparseJob, job_id)
    if job is None:
        logger.warning("reparse job %s not found, skipping", job_id)
        return

    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        job.status = RecipeReparseJobStatus.FAILED
        job.error = "recipe not found"
        db.commit()
        return

    if not recipe.source_url:
        job.status = RecipeReparseJobStatus.FAILED
        job.error = "recipe has no source_url to reparse from"
        db.commit()
        return

    app_settings = get_settings(db)

    job.status = RecipeReparseJobStatus.PROCESSING
    db.commit()

    try:
        # Extraction always asks Claude for a category suggestion too (see claude_client.py) —
        # deliberately ignored here. A reparse re-scrapes an *existing* recipe whose category the
        # owner/admin may have already corrected; silently overwriting it on every reparse would
        # be a surprising side effect of what's meant to be a content-quality refresh, not a
        # recategorization. Still needs a real category list to build the prompt, even though the
        # result goes unused.
        category_names = [c.name for c in db.scalars(select(Category).order_by(Category.id))]

        # Images are deliberately left untouched — only the text content (title, description,
        # ingredients, steps, tips) is re-extracted and updated. Re-fetching images would also
        # need to clean up the old files (see api/app/routers/images.py's delete_images, an
        # api-only concern), which is more risk than this feature needs to take on right now.
        if _is_instagram_url(recipe.source_url):
            post = fetch_instagram_post(recipe.source_url, app_settings.scrape_timeout_seconds)
            source_text = post.text[: app_settings.max_html_chars]
            extracted = parse_recipe_from_text(
                source_text,
                app_settings.supported_languages_list,
                app_settings.anthropic_api_key,
                category_names,
            )
        else:
            html = fetch_page(recipe.source_url, app_settings)
            extracted = extract_recipe(
                html,
                app_settings.supported_languages_list,
                app_settings.anthropic_api_key,
                category_names,
            )

        translations_data = extracted.get("translations", [])
        if not translations_data:
            raise RecipeExtractionError("Claude returned no translations")

        _update_translations_in_place(db, recipe, translations_data)

        job.status = RecipeReparseJobStatus.DONE
        db.commit()

        try:
            _enqueue_nutrition_job(db, recipe.id)
        except Exception:
            # The reparse itself already succeeded and committed above — a problem enqueueing
            # the follow-up nutrition re-enrichment must not turn a successful reparse into a
            # reported failure.
            logger.exception(
                "failed to auto-enqueue nutrition job after reparse for recipe %s", recipe.id
            )
            db.rollback()
    except InstagramFetchError as exc:
        db.rollback()
        job.status = RecipeReparseJobStatus.FAILED
        job.error = str(exc)
        db.commit()
    except ScrapeDisallowedError as exc:
        db.rollback()
        job.status = RecipeReparseJobStatus.FAILED
        job.error = str(exc)
        db.commit()
    except httpx.HTTPError as exc:
        db.rollback()
        job.status = RecipeReparseJobStatus.FAILED
        job.error = f"failed to fetch page: {exc}"
        db.commit()
    except RecipeExtractionError as exc:
        db.rollback()
        job.status = RecipeReparseJobStatus.FAILED
        job.error = str(exc)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("unexpected error handling reparse job %s", job_id)
        job.status = RecipeReparseJobStatus.FAILED
        job.error = f"unexpected error: {exc}"
        db.commit()
