import json
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import nutrition_handlers
from app.database import Base
from app.models import (
    AppSettings,
    Ingredient,
    NutritionJob,
    NutritionJobStatus,
    Recipe,
    RecipeIngredientLink,
    RecipeTranslation,
)
from app.nutrition_handlers import handle_nutrition_job


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _create_recipe(db: Session, ingredients: list[str]) -> Recipe:
    recipe = Recipe(category_id=1, owner_user_id=1)
    recipe.translations.append(
        RecipeTranslation(language="ro", title="Rețetă", slug="reteta", ingredients=ingredients)
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


def _create_job(db: Session, recipe_id: int) -> NutritionJob:
    job = NutritionJob(recipe_id=recipe_id, status=NutritionJobStatus.QUEUED)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _seed_app_settings(db: Session, calorie_ninjas_api_key: str = "") -> None:
    # get_settings() falls back to calorie_ninjas_api_key="" when no row exists (see
    # settings_service.py), which short-circuits the lookup entirely — tests that need
    # lookup_nutrition to actually run must seed a real key here.
    db.add(
        AppSettings(
            id=1,
            supported_languages="ro,en",
            default_language="ro",
            smtp_host="",
            smtp_port=587,
            smtp_username="",
            smtp_password="",
            smtp_from_address="",
            smtp_use_tls=True,
            turnstile_site_key="",
            turnstile_secret_key="",
            public_site_url="",
            anthropic_api_key="",
            calorie_ninjas_api_key=calorie_ninjas_api_key,
            default_rate_limit_requests_per_minute=6,
            scrape_timeout_seconds=15.0,
            max_html_chars=200_000,
            image_max_dimension=1600,
            image_max_size_kb=500,
        )
    )
    db.commit()


def _lookup_item(**overrides: object) -> dict:
    item = {
        "calories": 44.0,
        "protein_g": 1.1,
        "carbohydrates_total_g": 9.3,
        "sugar_g": 4.2,
        "fat_total_g": 0.1,
        "serving_size_g": 100.0,
    }
    item.update(overrides)
    return item


_ONE_ITEM_PARSE = {
    "estimated_servings": 4,
    "items": [
        {
            "line_index": 0,
            "food_name": "onion",
            "quantity": 1,
            "unit": "medium",
            "estimated_grams": 90,
        }
    ],
}


@pytest.mark.parametrize(
    ("quantity", "expected"),
    [
        (1, "1"),
        (5, "5"),
        (5.5, "6"),
        (2.5, "2"),  # banker's rounding — acceptable, avoids the decimal-stripping bug either way
        (0.5, "1"),  # rounds to 0, then floored up to 1 so the query never carries a bare "0"
        (0.2, "1"),
        (None, ""),
    ],
)
def test_quantity_for_query_rounds_to_avoid_calorie_ninjas_decimal_bug(
    quantity: object, expected: str
) -> None:
    assert nutrition_handlers._quantity_for_query(quantity) == expected


def test_handle_nutrition_job_rounds_decimal_quantity_before_the_grams_lookup(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression test for a real CalorieNinjas bug: it strips the decimal point from a quantity
    # in the query string, so "5.5 medium tomato" is parsed as "55 medium tomato" and returns a
    # serving size ~10x too large. Rounding the quantity to an integer before querying avoids it.
    _seed_app_settings(db_session, calorie_ninjas_api_key="test-key")
    recipe = _create_recipe(db_session, ["5.5 medium tomato"])
    job = _create_job(db_session, recipe.id)
    parse_result = {
        "estimated_servings": 4,
        "items": [
            {
                "line_index": 0,
                "food_name": "tomato",
                "quantity": 5.5,
                "unit": "medium",
                "estimated_grams": 676,
            }
        ],
    }
    monkeypatch.setattr(
        nutrition_handlers, "parse_ingredients_for_nutrition", lambda lines, key: parse_result
    )

    queries_seen: list[str] = []

    def _fake_lookup(query: str, key: str) -> dict | None:
        queries_seen.append(query)
        if query == "100g tomato":
            return _lookup_item(serving_size_g=100.0)
        if query == "6 medium tomato":
            return _lookup_item(serving_size_g=738.0)
        raise AssertionError(f"unexpected query: {query!r}")

    monkeypatch.setattr(nutrition_handlers, "lookup_nutrition", _fake_lookup)

    handle_nutrition_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    assert "6 medium tomato" in queries_seen
    link = db_session.scalars(select(RecipeIngredientLink)).one()
    assert link.estimated_grams == 738.0
    assert link.grams_source == "api_lookup"


@pytest.mark.parametrize(
    ("api_grams", "claude_grams", "expect_api"),
    [
        (55000.0, 250.0, False),  # "250 ml vegetable broth" bug: unit not recognized, API
        # silently applies a 220g/cup default x quantity instead of erroring — 220x claude's guess
        (700.0, 50.0, False),  # "50 ml oil" bug: 14g/tbsp default x 50 = 700g, 14x claude's guess
        (110.0, 90.0, True),  # a genuine, modest API correction — must not be discarded
        (2000.0, 250.0, True),  # exactly at the boundary (8x) is still trusted (inclusive)
        (2000.1, 250.0, False),  # just past the boundary is discarded
    ],
)
def test_resolve_grams_discards_implausible_api_values(
    api_grams: float, claude_grams: float, expect_api: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    item = {
        "food_name": "vegetable broth",
        "quantity": 250,
        "unit": "ml",
        "estimated_grams": claude_grams,
    }
    monkeypatch.setattr(
        nutrition_handlers, "lookup_nutrition", lambda query, key: _lookup_item(serving_size_g=api_grams)
    )

    grams, source = nutrition_handlers._resolve_grams(item, "test-key")

    if expect_api:
        assert grams == api_grams
        assert source == "api_lookup"
    else:
        assert grams == claude_grams
        assert source == "claude_estimate"


def test_handle_nutrition_job_discards_implausible_ml_grams_and_uses_claude_estimate(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression test for the recipe-20 bug report: "250 ml supă de legume" resolved to 55000g
    # because CalorieNinjas doesn't recognize "ml" as a unit and silently falls back to a per-cup
    # default multiplied by the quantity, instead of erroring.
    _seed_app_settings(db_session, calorie_ninjas_api_key="test-key")
    recipe = _create_recipe(db_session, ["250 ml supă de legume"])
    job = _create_job(db_session, recipe.id)
    parse_result = {
        "estimated_servings": 2,
        "items": [
            {
                "line_index": 0,
                "food_name": "vegetable broth",
                "quantity": 250,
                "unit": "ml",
                "estimated_grams": 250,
            }
        ],
    }
    monkeypatch.setattr(
        nutrition_handlers, "parse_ingredients_for_nutrition", lambda lines, key: parse_result
    )

    def _fake_lookup(query: str, key: str) -> dict | None:
        if query == "100g vegetable broth":
            return _lookup_item(serving_size_g=100.0)
        if query == "250 ml vegetable broth":
            return _lookup_item(serving_size_g=55000.0)
        raise AssertionError(f"unexpected query: {query!r}")

    monkeypatch.setattr(nutrition_handlers, "lookup_nutrition", _fake_lookup)

    handle_nutrition_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    link = db_session.scalars(select(RecipeIngredientLink)).one()
    assert link.estimated_grams == 250.0
    assert link.grams_source == "claude_estimate"


def test_handle_nutrition_job_success_creates_ingredient_and_link(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_app_settings(db_session, calorie_ninjas_api_key="test-key")
    recipe = _create_recipe(db_session, ["1 medium onion"])
    job = _create_job(db_session, recipe.id)
    monkeypatch.setattr(
        nutrition_handlers, "parse_ingredients_for_nutrition", lambda lines, key: _ONE_ITEM_PARSE
    )

    def _fake_lookup(query: str, key: str) -> dict | None:
        if query == "100g onion":
            return _lookup_item(serving_size_g=100.0)
        if query == "1 medium onion":
            return _lookup_item(serving_size_g=110.0)
        return None

    monkeypatch.setattr(nutrition_handlers, "lookup_nutrition", _fake_lookup)

    handle_nutrition_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == NutritionJobStatus.DONE
    assert job.error is None

    db_session.refresh(recipe)
    assert recipe.estimated_servings == 4

    ingredient = db_session.scalars(select(Ingredient)).one()
    assert ingredient.name == "onion"
    assert ingredient.calories_per_100g == 44.0

    link = db_session.scalars(select(RecipeIngredientLink)).one()
    assert link.recipe_id == recipe.id
    assert link.ingredient_index == 0
    assert link.ingredient_id == ingredient.id
    # The line-specific lookup resolved 110g, not Claude's own 90g guess.
    assert link.estimated_grams == 110.0
    assert link.grams_source == "api_lookup"


def test_handle_nutrition_job_skips_a_section_header_line_even_if_claude_returns_an_item_for_it(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    recipe = _create_recipe(db_session, ["### For the cake", "1 medium onion"])
    job = _create_job(db_session, recipe.id)
    # Simulates the nutrition-parsing prompt not being perfectly obeyed — it returns an item for
    # the header anyway (line_index 0). handle_nutrition_job must still discard it: see
    # app.recipe_sections.is_section_header, checked directly against the stored line text rather
    # than trusted on Claude's say-so.
    parsed = {
        "estimated_servings": 4,
        "items": [
            {
                "line_index": 0,
                "food_name": "section header",
                "quantity": 1,
                "unit": "",
                "estimated_grams": 1,
            },
            {
                "line_index": 1,
                "food_name": "onion",
                "quantity": 1,
                "unit": "medium",
                "estimated_grams": 90,
            },
        ],
    }
    monkeypatch.setattr(nutrition_handlers, "parse_ingredients_for_nutrition", lambda lines, key: parsed)
    monkeypatch.setattr(nutrition_handlers, "lookup_nutrition", lambda query, key: None)

    handle_nutrition_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    links = db_session.scalars(select(RecipeIngredientLink)).all()
    assert len(links) == 1
    assert links[0].ingredient_index == 1
    ingredient = db_session.get(Ingredient, links[0].ingredient_id)
    assert ingredient.name == "onion"


def test_handle_nutrition_job_falls_back_to_claude_estimate_without_api_match(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    recipe = _create_recipe(db_session, ["1 medium onion"])
    job = _create_job(db_session, recipe.id)
    monkeypatch.setattr(
        nutrition_handlers, "parse_ingredients_for_nutrition", lambda lines, key: _ONE_ITEM_PARSE
    )
    monkeypatch.setattr(nutrition_handlers, "lookup_nutrition", lambda query, key: None)

    handle_nutrition_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    link = db_session.scalars(select(RecipeIngredientLink)).one()
    assert link.estimated_grams == 90.0
    assert link.grams_source == "claude_estimate"

    ingredient = db_session.scalars(select(Ingredient)).one()
    assert ingredient.calories_per_100g == 0.0  # zeroed placeholder, not skipped


def test_handle_nutrition_job_reuses_existing_ingredient_by_name(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = Ingredient(
        name="onion",
        calories_per_100g=40.0,
        protein_per_100g=1.1,
        carbs_per_100g=9.3,
        sugars_per_100g=4.2,
        fat_per_100g=0.1,
    )
    db_session.add(existing)
    db_session.commit()
    _seed_app_settings(db_session, calorie_ninjas_api_key="test-key")

    recipe = _create_recipe(db_session, ["1 medium onion"])
    job = _create_job(db_session, recipe.id)
    monkeypatch.setattr(
        nutrition_handlers, "parse_ingredients_for_nutrition", lambda lines, key: _ONE_ITEM_PARSE
    )

    queries_seen: list[str] = []

    def _fake_lookup(query: str, key: str) -> dict | None:
        queries_seen.append(query)
        if query == "100g onion":
            raise AssertionError("should not re-query an ingredient that already exists by name")
        return _lookup_item(serving_size_g=110.0)

    monkeypatch.setattr(nutrition_handlers, "lookup_nutrition", _fake_lookup)

    handle_nutrition_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == NutritionJobStatus.DONE
    assert db_session.scalars(select(Ingredient)).all() == [existing]
    # Only the line-specific grams lookup happened — no redundant ingredient-cache lookup.
    assert queries_seen == ["1 medium onion"]


def test_handle_nutrition_job_skips_one_bad_item_without_failing_the_rest(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A malformed item (missing required keys) raises inside the per-item loop — this should be
    # skipped rather than failing the whole job, same "skip, don't fail the batch" pattern as
    # images.process_images.
    malformed_parse = {
        "estimated_servings": 2,
        "items": [
            {
                "line_index": 0,
                "food_name": "onion",
                "quantity": 1,
                "unit": "medium",
                "estimated_grams": 90,
            },
            {"line_index": 1},  # missing food_name/quantity/unit/estimated_grams
        ],
    }
    recipe = _create_recipe(db_session, ["1 medium onion", "2 cloves garlic"])
    job = _create_job(db_session, recipe.id)
    monkeypatch.setattr(
        nutrition_handlers, "parse_ingredients_for_nutrition", lambda lines, key: malformed_parse
    )
    monkeypatch.setattr(nutrition_handlers, "lookup_nutrition", lambda query, key: None)

    handle_nutrition_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == NutritionJobStatus.DONE
    links = db_session.scalars(select(RecipeIngredientLink)).all()
    assert len(links) == 1
    assert links[0].ingredient_index == 0


def test_handle_nutrition_job_fails_when_recipe_has_no_ingredients(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    recipe = _create_recipe(db_session, [])
    job = _create_job(db_session, recipe.id)

    handle_nutrition_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == NutritionJobStatus.FAILED
    assert "no ingredients" in job.error


def test_handle_nutrition_job_fails_when_claude_returns_no_items(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    recipe = _create_recipe(db_session, ["1 medium onion"])
    job = _create_job(db_session, recipe.id)
    monkeypatch.setattr(
        nutrition_handlers,
        "parse_ingredients_for_nutrition",
        lambda lines, key: {"estimated_servings": 1, "items": []},
    )

    handle_nutrition_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == NutritionJobStatus.FAILED
    assert db_session.scalars(select(RecipeIngredientLink)).first() is None


def test_handle_nutrition_job_fails_on_unexpected_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    recipe = _create_recipe(db_session, ["1 medium onion"])
    job = _create_job(db_session, recipe.id)

    def _raise(lines: list[str], key: str) -> dict:
        raise RuntimeError("boom")

    monkeypatch.setattr(nutrition_handlers, "parse_ingredients_for_nutrition", _raise)

    handle_nutrition_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == NutritionJobStatus.FAILED
    assert "unexpected error" in job.error


def test_handle_nutrition_job_ignores_unknown_job_id(db_session: Session) -> None:
    handle_nutrition_job(json.dumps({"job_id": 999, "recipe_id": 1}).encode(), db_session)


def test_handle_nutrition_job_fails_when_recipe_not_found(db_session: Session) -> None:
    job = NutritionJob(recipe_id=999, status=NutritionJobStatus.QUEUED)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    handle_nutrition_job(json.dumps({"job_id": job.id, "recipe_id": 999}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == NutritionJobStatus.FAILED
    assert job.error == "recipe not found"


def test_handle_nutrition_job_replaces_links_from_a_previous_run(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    recipe = _create_recipe(db_session, ["1 medium onion"])
    stale_ingredient = Ingredient(
        name="stale",
        calories_per_100g=0,
        protein_per_100g=0,
        carbs_per_100g=0,
        sugars_per_100g=0,
        fat_per_100g=0,
    )
    db_session.add(stale_ingredient)
    db_session.commit()
    db_session.add(
        RecipeIngredientLink(
            recipe_id=recipe.id,
            ingredient_index=0,
            ingredient_id=stale_ingredient.id,
            raw_text="stale link from a previous run",
            estimated_grams=1.0,
            grams_source="claude_estimate",
        )
    )
    db_session.commit()

    job = _create_job(db_session, recipe.id)
    monkeypatch.setattr(
        nutrition_handlers, "parse_ingredients_for_nutrition", lambda lines, key: _ONE_ITEM_PARSE
    )
    monkeypatch.setattr(nutrition_handlers, "lookup_nutrition", lambda query, key: None)

    handle_nutrition_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    links = db_session.scalars(select(RecipeIngredientLink)).all()
    assert len(links) == 1
    assert links[0].raw_text == "1 medium onion"
