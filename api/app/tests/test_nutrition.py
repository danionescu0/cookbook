import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.ingredient import Ingredient
from app.models.nutrition_job import NutritionJob, NutritionJobStatus
from app.models.recipe import Recipe
from app.models.recipe_ingredient_link import RecipeIngredientLink


def _create_category(client: TestClient, name: str = "Desserts") -> int:
    return client.post("/categories", json={"name": name}).json()["id"]


def _create_recipe(client: TestClient, **overrides: object) -> int:
    category_id = _create_category(client)
    payload: dict[str, object] = {
        "title": "Soup",
        "category_id": category_id,
        "ingredients": ["onion", "garlic"],
    }
    payload.update(overrides)
    return client.post("/recipes", json=payload).json()["id"]


def test_get_nutrition_not_enriched_for_new_recipe(client: TestClient) -> None:
    recipe_id = _create_recipe(client)

    response = client.get(f"/recipes/{recipe_id}/nutrition")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_enriched"
    assert body["totals"] is None
    assert body["per_ingredient"] == []


def test_get_nutrition_unknown_recipe_404(client: TestClient) -> None:
    response = client.get("/recipes/999/nutrition")

    assert response.status_code == 404


def test_get_nutrition_is_public(unauthenticated_client: TestClient) -> None:
    # A 404 (not a 401) proves this route doesn't require auth at all — require_admin would have
    # rejected the request before the handler ever looked the recipe up.
    response = unauthenticated_client.get("/recipes/999/nutrition")

    assert response.status_code == 404


def test_get_nutrition_computes_totals_from_links(
    client: TestClient, db_session: Session
) -> None:
    recipe_id = _create_recipe(client, ingredients=["onion", "olive oil"])

    onion = Ingredient(
        name="onion",
        calories_per_100g=40.0,
        protein_per_100g=1.1,
        carbs_per_100g=9.3,
        sugars_per_100g=4.2,
        fat_per_100g=0.1,
    )
    oil = Ingredient(
        name="olive oil",
        calories_per_100g=884.0,
        protein_per_100g=0.0,
        carbs_per_100g=0.0,
        sugars_per_100g=0.0,
        fat_per_100g=100.0,
    )
    db_session.add_all([onion, oil])
    db_session.commit()
    db_session.add_all(
        [
            RecipeIngredientLink(
                recipe_id=recipe_id,
                ingredient_index=0,
                ingredient_id=onion.id,
                raw_text="onion",
                estimated_grams=110.0,
                grams_source="api_lookup",
            ),
            RecipeIngredientLink(
                recipe_id=recipe_id,
                ingredient_index=1,
                ingredient_id=oil.id,
                raw_text="olive oil",
                estimated_grams=14.0,
                grams_source="claude_estimate",
            ),
        ]
    )
    db_session.commit()

    response = client.get(f"/recipes/{recipe_id}/nutrition")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    # 40*1.10 + 884*0.14 = 44 + 123.76 = 167.76
    assert body["totals"]["calories"] == pytest.approx(167.8, abs=0.05)
    # 0.1*1.10 (onion) + 100*0.14 (oil) = 0.11 + 14.0 = 14.11
    assert body["totals"]["fat_g"] == pytest.approx(14.1, abs=0.05)
    assert body["per_serving"] is None  # no estimated_servings set
    assert body["per_ingredient"] == [
        {"index": 0, "estimated_grams": 110.0, "grams_source": "api_lookup"},
        {"index": 1, "estimated_grams": 14.0, "grams_source": "claude_estimate"},
    ]


def test_get_nutrition_computes_per_serving_when_servings_known(
    client: TestClient, db_session: Session
) -> None:
    recipe_id = _create_recipe(client, ingredients=["onion"])
    onion = Ingredient(
        name="onion",
        calories_per_100g=100.0,
        protein_per_100g=0.0,
        carbs_per_100g=0.0,
        sugars_per_100g=0.0,
        fat_per_100g=0.0,
    )
    db_session.add(onion)
    db_session.commit()
    db_session.add(
        RecipeIngredientLink(
            recipe_id=recipe_id,
            ingredient_index=0,
            ingredient_id=onion.id,
            raw_text="onion",
            estimated_grams=200.0,
            grams_source="claude_estimate",
        )
    )
    recipe = db_session.get(Recipe, recipe_id)
    recipe.estimated_servings = 4
    db_session.commit()

    response = client.get(f"/recipes/{recipe_id}/nutrition")

    body = response.json()
    assert body["estimated_servings"] == 4
    assert body["totals"]["calories"] == 200.0  # 100 * 200/100
    assert body["per_serving"]["calories"] == 50.0


def test_get_nutrition_reports_a_failed_job_when_nothing_ever_succeeded(
    client: TestClient, db_session: Session
) -> None:
    recipe_id = _create_recipe(client)
    db_session.add(NutritionJob(recipe_id=recipe_id, status=NutritionJobStatus.FAILED, error="boom"))
    db_session.commit()

    response = client.get(f"/recipes/{recipe_id}/nutrition")

    body = response.json()
    assert body["status"] == "failed"
    assert body["error"] == "boom"
    assert body["totals"] is None


def test_get_nutrition_keeps_totals_visible_during_a_failed_retry(
    client: TestClient, db_session: Session
) -> None:
    # A failed re-run shouldn't make previously-good nutrition data disappear from the front
    # office while a retry is in flight or after it fails.
    recipe_id = _create_recipe(client, ingredients=["onion"])
    onion = Ingredient(
        name="onion",
        calories_per_100g=50.0,
        protein_per_100g=0.0,
        carbs_per_100g=0.0,
        sugars_per_100g=0.0,
        fat_per_100g=0.0,
    )
    db_session.add(onion)
    db_session.commit()
    db_session.add(
        RecipeIngredientLink(
            recipe_id=recipe_id,
            ingredient_index=0,
            ingredient_id=onion.id,
            raw_text="onion",
            estimated_grams=100.0,
            grams_source="claude_estimate",
        )
    )
    db_session.add(
        NutritionJob(recipe_id=recipe_id, status=NutritionJobStatus.FAILED, error="retry failed")
    )
    db_session.commit()

    response = client.get(f"/recipes/{recipe_id}/nutrition")

    body = response.json()
    assert body["status"] == "done"
    assert body["totals"]["calories"] == 50.0
