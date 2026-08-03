import json
import logging

from sqlalchemy.orm import Session

from app.claude_client import RecipeExtractionError, translate_recipe
from app.handlers import _enqueue_nutrition_job
from app.models import Recipe, RecipeTranslation, TranslationSyncJob, TranslationSyncJobStatus
from app.settings_service import get_settings
from app.slugify import generate_unique_slug

logger = logging.getLogger(__name__)


def _translation_dict(translation: RecipeTranslation) -> dict:
    return {
        "title": translation.title,
        "description": translation.description,
        "ingredients": translation.ingredients,
        "steps": translation.steps,
        "tips": translation.tips,
    }


def handle_translation_sync_job(body: bytes, db: Session) -> None:
    payload = json.loads(body)
    job_id = payload["job_id"]

    job = db.get(TranslationSyncJob, job_id)
    if job is None:
        logger.warning("translation sync job %s not found, skipping", job_id)
        return

    recipe = db.get(Recipe, job.recipe_id)
    if recipe is None:
        job.status = TranslationSyncJobStatus.FAILED
        job.error = "recipe not found"
        db.commit()
        return

    app_settings = get_settings(db)

    job.status = TranslationSyncJobStatus.PROCESSING
    db.commit()

    try:
        by_language = {t.language: t for t in recipe.translations}
        source = by_language.get(job.source_language)
        if source is None:
            raise RecipeExtractionError(
                f"source translation {job.source_language!r} not found on recipe {recipe.id}"
            )

        # Every other supported language needs to match what was just hand-edited — a language
        # not yet on the recipe at all gets created here too, same outcome as a fresh import.
        target_languages = [
            lang for lang in app_settings.supported_languages_list if lang != job.source_language
        ]
        if target_languages:
            translated = translate_recipe(
                _translation_dict(source), target_languages, app_settings.anthropic_api_key
            )
            for t in translated.get("translations", []):
                translation = by_language.get(t["language"])
                is_new_translation = translation is None
                if translation is None:
                    translation = RecipeTranslation(
                        recipe_id=recipe.id, language=t["language"], title="", slug=""
                    )
                    recipe.translations.append(translation)
                    by_language[t["language"]] = translation
                translation.title = t["title"]
                translation.description = t.get("description", "")
                translation.ingredients = t.get("ingredients", [])
                translation.steps = t.get("steps", [])
                translation.tips = t.get("tips", [])
                if is_new_translation:
                    # Generated once, here, and never auto-regenerated on later syncs — same
                    # reasoning as api/app/models/recipe_translation.py's slug docstring.
                    translation.slug = generate_unique_slug(db, t["language"], translation.title)

        job.status = TranslationSyncJobStatus.DONE
        db.commit()

        try:
            _enqueue_nutrition_job(db, recipe.id)
        except Exception:
            # The sync itself already succeeded and committed above — a problem enqueueing the
            # follow-up nutrition job must not turn a successful sync into a reported failure.
            logger.exception(
                "failed to auto-enqueue nutrition job after translation sync for recipe %s",
                recipe.id,
            )
            db.rollback()
    except RecipeExtractionError as exc:
        db.rollback()
        job.status = TranslationSyncJobStatus.FAILED
        job.error = str(exc)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("unexpected error handling translation sync job %s", job_id)
        job.status = TranslationSyncJobStatus.FAILED
        job.error = f"unexpected error: {exc}"
        db.commit()
