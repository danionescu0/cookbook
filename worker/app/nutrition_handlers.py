import json
import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.claude_client import IngredientParseError, parse_ingredients_for_nutrition
from app.models import Category, Ingredient, NutritionJob, NutritionJobStatus, Recipe, RecipeIngredientLink
from app.nutrition_api_client import extract_nutrients_per_100g, lookup_nutrition
from app.recipe_sections import is_section_header
from app.settings_service import SettingsSnapshot, get_settings

logger = logging.getLogger(__name__)

# See the comment where this is used, in handle_nutrition_job, for the sourcing. This is the
# fallback for any category not in _PORTION_GRAMS_BY_CATEGORY below, and the only value used
# before that per-category table existed.
STANDARD_PORTION_GRAMS = 475

# A dessert or a soup isn't eaten in a main-course-sized portion — a muffin/cake slice weighs a
# fraction of a bowl of stew, so reusing STANDARD_PORTION_GRAMS for every category understated
# desserts' serving counts by 3-4x (found via a real muffin-and-frosting recipe whose 1170g total
# came back as "2 servings" at ~585g each). Matched case-insensitively against the recipe's actual
# category name, the same way handlers.py's _resolve_category_id matches Claude's suggested
# category — an admin can rename/add categories at will (CategoryManager), so any name not listed
# here just falls back to STANDARD_PORTION_GRAMS rather than erroring or silently misfiring. See
# README Design Decisions, "Estimated servings".
_PORTION_GRAMS_BY_CATEGORY = {
    "desserts": 110,  # a muffin / cake slice / a couple of cookies, not a meal-sized bowl
    "supe": 350,  # a bowl of soup — between the FDA's 245g soup RACC and a full main-course portion
}


def _portion_grams_for(category_name: str | None) -> float:
    if category_name is None:
        return STANDARD_PORTION_GRAMS
    return _PORTION_GRAMS_BY_CATEGORY.get(category_name.strip().lower(), STANDARD_PORTION_GRAMS)


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
# doesn't recognize the unit word at all, it silently falls back to treating the quantity as a
# count of that food's default "cup" serving instead of raising an error — e.g. "250 ml vegetable
# broth" returns serving_size_g=55000 (250 x the 220g/cup default for vegetable broth), not an
# error we could detect and handle. Confirmed for "ml", the "gr" abbreviation, and — found while
# investigating why a soup's water line came back as 711g instead of ~2650g for "3 liters water"
# (711 / 3 ≈ 237g, almost exactly one cup) — "liter(s)"/"litre(s)"/"l" too. There's no way to
# enumerate every unit word Claude might emit across recipe languages, so this is a denylist of
# specifically confirmed offenders, not a general fix: for these, skip the CalorieNinjas
# refinement entirely and trust Claude's own estimate, since a divergence here isn't a real
# correction (see README Design Decisions, "Ingredient nutrition").
_UNRELIABLE_UNITS = {
    "ml", "milliliter", "milliliters", "millilitre", "millilitres",
    "gr",
    "l", "liter", "liters", "litre", "litres",
}

# A genuine API correction of Claude's own estimate is normally within a small factor (portion
# data correcting a rough guess); an order-of-magnitude-plus divergence is the same class of bug
# as _UNRELIABLE_UNITS above (an unrecognized query silently falling back to a "cup" default) for
# a unit word not yet confirmed/denylisted, so it's discarded in favor of Claude's estimate rather
# than trusted.
_IMPLAUSIBLE_GRAMS_RATIO = 8.0


def _resolve_grams(item: dict, api_key: str) -> tuple[float, str]:
    claude_grams = float(item.get("estimated_grams") or 0) or 1.0

    quantity_str = _quantity_for_query(item.get("quantity"))
    unit = str(item.get("unit") or "").strip()
    food_name = str(item.get("food_name") or "")
    query = " ".join(part for part in (quantity_str, unit, food_name) if part)

    if api_key and query and unit.lower() not in _UNRELIABLE_UNITS:
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

        parsed = parse_ingredients_for_nutrition(
            ingredient_lines, app_settings.ai_api_key, provider=app_settings.preferred_ai_provider
        )
        items = parsed.get("items", [])
        if not items:
            raise IngredientParseError("Claude returned no parsed ingredients")

        # Replace any links from a previous run rather than accumulating stale rows.
        db.execute(delete(RecipeIngredientLink).where(RecipeIngredientLink.recipe_id == recipe.id))

        total_grams = 0.0
        for item in items:
            try:
                line_index = int(item["line_index"])
                # Defense-in-depth regardless of prompt compliance — a sub-group label (e.g.
                # "### For the cake") is never a real ingredient, so it must never get a
                # nutrition estimate/link, even if Claude's nutrition-parsing call didn't skip it.
                if 0 <= line_index < len(ingredient_lines) and is_section_header(
                    ingredient_lines[line_index]
                ):
                    continue
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
                total_grams += grams
            except Exception:
                # One bad ingredient line shouldn't sink the whole recipe's nutrition data — same
                # "skip, don't fail the batch" pattern as images.process_images.
                logger.warning(
                    "failed to resolve ingredient item %r for recipe %s", item, recipe.id,
                    exc_info=True,
                )
                continue

        # Servings used to be a separate Claude guess, disconnected from the actual ingredient
        # weights — it visibly broke on recipes with a large stated liquid volume (a soup using
        # 2.5-2.8L of water guessed at 4 servings, implying a ~1kg bowl). Computed instead, from
        # the finished dish's total weight divided by a source-backed average portion weight —
        # STANDARD_PORTION_GRAMS (475g, the midpoint of the ~400-550g a full one-adult main-course
        # portion weighs — https://www.foodspring.co.uk/magazine/serving-size, cross-checked
        # against https://www.thedonutwhole.com/how-many-pounds-is-the-average-meal/) by default,
        # or a smaller category-specific weight from _PORTION_GRAMS_BY_CATEGORY when the recipe's
        # category has one (see that table's comment for why desserts/soups need their own figure).
        if total_grams > 0:
            category = db.get(Category, recipe.category_id)
            portion_grams = _portion_grams_for(category.name if category else None)
            recipe.estimated_servings = max(1, round(total_grams / portion_grams))

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
