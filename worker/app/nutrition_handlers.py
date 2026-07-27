import json
import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.claude_client import IngredientParseError, parse_ingredients_for_nutrition
from app.models import Ingredient, NutritionJob, NutritionJobStatus, Recipe, RecipeIngredientLink
from app.nutrition_api_client import extract_nutrients_per_100g, lookup_nutrition
from app.settings_service import SettingsSnapshot, get_settings

logger = logging.getLogger(__name__)


def _get_ingredient_lines(recipe: Recipe, default_language: str) -> list[str]:
    # Any translation works for parsing — Claude normalizes the food name to English regardless
    # of the source language — so this just prefers the site's default language for a stable,
    # predictable choice, falling back to whatever translation exists.
    by_language = {t.language: t for t in recipe.translations}
    translation = by_language.get(default_language) or next(iter(recipe.translations), None)
    return translation.ingredients if translation else []


def _get_or_create_ingredient(db: Session, food_name: str, api_key: str) -> Ingredient:
    normalized = food_name.strip().lower()

    existing = db.scalar(select(Ingredient).where(Ingredient.name == normalized))
    if existing is not None:
        return existing

    nutrients = {
        "calories_per_100g": 0.0,
        "protein_per_100g": 0.0,
        "carbs_per_100g": 0.0,
        "sugars_per_100g": 0.0,
        "fat_per_100g": 0.0,
    }
    if api_key:
        try:
            # Explicitly asking for "100g <food>" gives a clean, directly-comparable per-100g
            # baseline regardless of what quantity a specific recipe line happens to use.
            item = lookup_nutrition(f"100g {normalized}", api_key)
            if item is not None:
                nutrients = extract_nutrients_per_100g(item)
        except Exception:
            logger.warning("nutrition lookup failed for %r", normalized, exc_info=True)
    # No match (no API key, bad query, or the lookup itself failed): store a zeroed-out
    # placeholder rather than skipping the line or failing the whole recipe — its contribution
    # to the totals is 0 until someone re-runs the job with better data, instead of silently
    # under-counting with no trace of why.

    ingredient = Ingredient(name=normalized, **nutrients)
    db.add(ingredient)
    db.flush()  # assigns ingredient.id without committing the transaction yet
    return ingredient


def _quantity_for_query(quantity: object) -> str:
    # CalorieNinjas' NLP has a real, confirmed bug with decimal quantities: it strips the decimal
    # point rather than parsing the number, so "5.5 medium tomato" comes back as if it were "55
    # medium tomato" (serving_size_g off by ~10x). Rounding to the nearest whole number before
    # querying trades a little precision for avoiding that order-of-magnitude error — see README
    # Design Decisions ("Ingredient nutrition").
    try:
        value = float(quantity)
    except (TypeError, ValueError):
        return ""
    return str(max(1, round(value)))


# CalorieNinjas' NLP has another confirmed bug, worse than the decimal-quantity one above: when it
# doesn't recognize the unit word at all (confirmed for "ml" and the "gr" abbreviation, and there's
# no way to enumerate every unit word Claude might emit across recipe languages), it silently falls
# back to treating the quantity as a count of that food's default "cup" serving instead of raising
# an error — e.g. "250 ml vegetable broth" returns serving_size_g=55000 (250 x the 220g/cup default
# for vegetable broth), not an error we could detect and handle. A genuine API correction of
# Claude's own estimate is normally within a small factor (portion data correcting a rough guess);
# an order-of-magnitude-plus divergence is this bug, not a correction, so it's discarded in favor
# of Claude's estimate rather than trusted.
_IMPLAUSIBLE_GRAMS_RATIO = 8.0


def _resolve_grams(item: dict, api_key: str) -> tuple[float, str]:
    claude_grams = float(item.get("estimated_grams") or 0) or 1.0

    quantity_str = _quantity_for_query(item.get("quantity"))
    unit = str(item.get("unit") or "").strip()
    food_name = str(item.get("food_name") or "")
    query = " ".join(part for part in (quantity_str, unit, food_name) if part)

    if api_key and query:
        try:
            # A second, line-specific lookup: the exact quantity phrase (e.g. "1 medium onion")
            # resolves its own serving_size_g, which is a real-world weight rather than an LLM
            # guess — used as the primary source, with Claude's estimate only as a fallback.
            lookup_item = lookup_nutrition(query, api_key)
            grams = lookup_item.get("serving_size_g") if lookup_item else None
            if grams:
                ratio = grams / claude_grams
                if 1 / _IMPLAUSIBLE_GRAMS_RATIO <= ratio <= _IMPLAUSIBLE_GRAMS_RATIO:
                    return float(grams), "api_lookup"
                logger.warning(
                    "discarding implausible CalorieNinjas grams for %r: api=%sg vs claude=%sg",
                    query, grams, claude_grams,
                )
        except Exception:
            logger.warning("grams lookup failed for %r", query, exc_info=True)

    return claude_grams, "claude_estimate"


def handle_nutrition_job(body: bytes, db: Session) -> None:
    payload = json.loads(body)
    job_id = payload["job_id"]
    recipe_id = payload["recipe_id"]

    job = db.get(NutritionJob, job_id)
    if job is None:
        logger.warning("nutrition job %s not found, skipping", job_id)
        return

    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        job.status = NutritionJobStatus.FAILED
        job.error = "recipe not found"
        db.commit()
        return

    app_settings: SettingsSnapshot = get_settings(db)

    job.status = NutritionJobStatus.PROCESSING
    db.commit()

    try:
        ingredient_lines = _get_ingredient_lines(recipe, app_settings.default_language)
        if not ingredient_lines:
            raise IngredientParseError("recipe has no ingredients to parse")

        parsed = parse_ingredients_for_nutrition(ingredient_lines, app_settings.anthropic_api_key)
        items = parsed.get("items", [])
        if not items:
            raise IngredientParseError("Claude returned no parsed ingredients")

        estimated_servings = parsed.get("estimated_servings")
        if estimated_servings:
            recipe.estimated_servings = int(estimated_servings)

        # Replace any links from a previous run rather than accumulating stale rows.
        db.execute(delete(RecipeIngredientLink).where(RecipeIngredientLink.recipe_id == recipe.id))

        for item in items:
            try:
                line_index = int(item["line_index"])
                ingredient = _get_or_create_ingredient(
                    db, item["food_name"], app_settings.calorie_ninjas_api_key
                )
                grams, grams_source = _resolve_grams(item, app_settings.calorie_ninjas_api_key)
                raw_text = (
                    ingredient_lines[line_index]
                    if 0 <= line_index < len(ingredient_lines)
                    else item["food_name"]
                )
                db.add(
                    RecipeIngredientLink(
                        recipe_id=recipe.id,
                        ingredient_index=line_index,
                        ingredient_id=ingredient.id,
                        raw_text=raw_text,
                        estimated_grams=grams,
                        grams_source=grams_source,
                    )
                )
            except Exception:
                # One bad ingredient line shouldn't sink the whole recipe's nutrition data — same
                # "skip, don't fail the batch" pattern as images.process_images.
                logger.warning(
                    "failed to resolve ingredient item %r for recipe %s", item, recipe.id,
                    exc_info=True,
                )
                continue

        job.status = NutritionJobStatus.DONE
        db.commit()
    except IngredientParseError as exc:
        db.rollback()
        job.status = NutritionJobStatus.FAILED
        job.error = str(exc)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("unexpected error handling nutrition job %s", job_id)
        job.status = NutritionJobStatus.FAILED
        job.error = f"unexpected error: {exc}"
        db.commit()
