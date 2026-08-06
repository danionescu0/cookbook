from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.nutrition_job import NutritionJob, NutritionJobStatus
from app.models.recipe import Recipe
from app.models.recipe_ingredient_link import RecipeIngredientLink
from app.schemas.nutrition import NutritionIngredient, NutritionRead, NutritionTotals

router = APIRouter(tags=["nutrition"])


def _get_recipe_or_404(db: Session, recipe_id: int) -> Recipe:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


def _compute_summary(db: Session, recipe: Recipe) -> NutritionRead:
    links = list(
        db.scalars(
            select(RecipeIngredientLink)
            .options(selectinload(RecipeIngredientLink.ingredient))
            .where(RecipeIngredientLink.recipe_id == recipe.id)
            .order_by(RecipeIngredientLink.ingredient_index)
        )
    )
    latest_job = db.scalar(
        select(NutritionJob)
        .where(NutritionJob.recipe_id == recipe.id)
        .order_by(NutritionJob.created_at.desc())
        .limit(1)
    )

    # Totals come from whatever was last successfully resolved, independent of whether a later
    # re-run is in progress or failed — a background re-enrichment attempt shouldn't make
    # previously-good nutrition data disappear from the front office while it runs.
    if links:
        calories = protein_g = carbs_g = sugars_g = fat_g = total_grams = 0.0
        per_ingredient: list[NutritionIngredient] = []
        for link in links:
            factor = link.estimated_grams / 100
            ingredient = link.ingredient
            calories += ingredient.calories_per_100g * factor
            protein_g += ingredient.protein_per_100g * factor
            carbs_g += ingredient.carbs_per_100g * factor
            sugars_g += ingredient.sugars_per_100g * factor
            fat_g += ingredient.fat_per_100g * factor
            total_grams += link.estimated_grams
            per_ingredient.append(
                NutritionIngredient(
                    index=link.ingredient_index,
                    estimated_grams=round(link.estimated_grams, 1),
                    grams_source=link.grams_source,
                )
            )

        totals = NutritionTotals(
            calories=round(calories, 1),
            protein_g=round(protein_g, 1),
            carbs_g=round(carbs_g, 1),
            sugars_g=round(sugars_g, 1),
            fat_g=round(fat_g, 1),
        )
        per_serving = None
        if recipe.estimated_servings and recipe.estimated_servings > 0:
            servings = recipe.estimated_servings
            per_serving = NutritionTotals(
                calories=round(calories / servings, 1),
                protein_g=round(protein_g / servings, 1),
                carbs_g=round(carbs_g / servings, 1),
                sugars_g=round(sugars_g / servings, 1),
                fat_g=round(fat_g / servings, 1),
            )

        status = "done"
        if latest_job is not None and latest_job.status in (
            NutritionJobStatus.QUEUED,
            NutritionJobStatus.PROCESSING,
        ):
            status = latest_job.status.value

        return NutritionRead(
            status=status,
            estimated_servings=recipe.estimated_servings,
            total_grams=round(total_grams, 1),
            totals=totals,
            per_serving=per_serving,
            per_ingredient=per_ingredient,
        )

    if latest_job is None:
        return NutritionRead(status="not_enriched")
    if latest_job.status == NutritionJobStatus.FAILED:
        return NutritionRead(status="failed", error=latest_job.error)
    return NutritionRead(status=latest_job.status.value)


@router.get("/recipes/{recipe_id}/nutrition", response_model=NutritionRead)
def get_nutrition(recipe_id: int, db: Session = Depends(get_db)) -> NutritionRead:
    recipe = _get_recipe_or_404(db, recipe_id)
    return _compute_summary(db, recipe)
