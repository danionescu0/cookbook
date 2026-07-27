import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ingredient, IngredientRefreshJob, IngredientRefreshJobStatus
from app.nutrition_api_client import extract_nutrients_per_100g, lookup_nutrition
from app.settings_service import get_settings

logger = logging.getLogger(__name__)


class IngredientRefreshError(Exception):
    pass


def _refresh_one(ingredient: Ingredient, api_key: str) -> bool:
    """Re-fetches nutrition data for one ingredient, in place. Returns True if it was updated."""
    item = lookup_nutrition(f"100g {ingredient.name}", api_key)
    if item is None:
        return False

    nutrients = extract_nutrients_per_100g(item)
    ingredient.calories_per_100g = nutrients["calories_per_100g"]
    ingredient.protein_per_100g = nutrients["protein_per_100g"]
    ingredient.carbs_per_100g = nutrients["carbs_per_100g"]
    ingredient.sugars_per_100g = nutrients["sugars_per_100g"]
    ingredient.fat_per_100g = nutrients["fat_per_100g"]
    return True


def handle_ingredient_refresh_job(body: bytes, db: Session) -> None:
    payload = json.loads(body)
    job_id = payload["job_id"]

    job = db.get(IngredientRefreshJob, job_id)
    if job is None:
        logger.warning("ingredient refresh job %s not found, skipping", job_id)
        return

    app_settings = get_settings(db)

    job.status = IngredientRefreshJobStatus.PROCESSING
    db.commit()

    try:
        if not app_settings.calorie_ninjas_api_key:
            raise IngredientRefreshError(
                "No CalorieNinjas API key configured — set one in Backoffice > Settings first."
            )

        updated = 0
        for ingredient in db.scalars(select(Ingredient)):
            try:
                if _refresh_one(ingredient, app_settings.calorie_ninjas_api_key):
                    updated += 1
            except Exception:
                # One ingredient's lookup failing (rate limit, network hiccup, ...) shouldn't
                # sink the whole batch — same "skip, don't fail the batch" pattern used elsewhere
                # in this worker (see images.process_images, nutrition_handlers).
                logger.warning("failed to refresh ingredient %r", ingredient.name, exc_info=True)
                continue

        job.status = IngredientRefreshJobStatus.DONE
        job.ingredients_updated = updated
        db.commit()
    except IngredientRefreshError as exc:
        db.rollback()
        job.status = IngredientRefreshJobStatus.FAILED
        job.error = str(exc)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("unexpected error handling ingredient refresh job %s", job_id)
        job.status = IngredientRefreshJobStatus.FAILED
        job.error = f"unexpected error: {exc}"
        db.commit()
