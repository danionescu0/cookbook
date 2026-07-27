import json
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import ingredient_refresh_handlers
from app.database import Base
from app.ingredient_refresh_handlers import handle_ingredient_refresh_job
from app.models import AppSettings, Ingredient, IngredientRefreshJob, IngredientRefreshJobStatus


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


def _seed_app_settings(db: Session, calorie_ninjas_api_key: str = "") -> None:
    db.add(
        AppSettings(
            id=1,
            supported_languages="ro,en",
            default_language="ro",
            admin_password="x",
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


def _create_job(db: Session) -> IngredientRefreshJob:
    job = IngredientRefreshJob(status=IngredientRefreshJobStatus.QUEUED)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _lookup_item(**overrides: object) -> dict:
    item = {
        "calories": 40.0,
        "protein_g": 1.1,
        "carbohydrates_total_g": 9.3,
        "sugar_g": 4.2,
        "fat_total_g": 0.1,
        "serving_size_g": 100.0,
    }
    item.update(overrides)
    return item


def _zeroed_ingredient(name: str) -> Ingredient:
    return Ingredient(
        name=name,
        calories_per_100g=0,
        protein_per_100g=0,
        carbs_per_100g=0,
        sugars_per_100g=0,
        fat_per_100g=0,
    )


def test_refreshes_an_ingredient_via_a_100g_lookup(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_app_settings(db_session, calorie_ninjas_api_key="test-key")
    ingredient = _zeroed_ingredient("onion")
    db_session.add(ingredient)
    db_session.commit()
    job = _create_job(db_session)

    queries_seen: list[str] = []

    def _fake_lookup(query: str, key: str) -> dict:
        queries_seen.append(query)
        return _lookup_item()

    monkeypatch.setattr(ingredient_refresh_handlers, "lookup_nutrition", _fake_lookup)

    handle_ingredient_refresh_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == IngredientRefreshJobStatus.DONE
    assert job.ingredients_updated == 1
    assert queries_seen == ["100g onion"]

    db_session.refresh(ingredient)
    assert ingredient.calories_per_100g == 40.0
    assert ingredient.protein_per_100g == 1.1


def test_leaves_an_ingredient_untouched_when_nothing_matches(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_app_settings(db_session, calorie_ninjas_api_key="test-key")
    ingredient = _zeroed_ingredient("a very obscure ingredient")
    db_session.add(ingredient)
    db_session.commit()
    job = _create_job(db_session)

    monkeypatch.setattr(ingredient_refresh_handlers, "lookup_nutrition", lambda query, key: None)

    handle_ingredient_refresh_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == IngredientRefreshJobStatus.DONE
    assert job.ingredients_updated == 0


def test_one_ingredients_lookup_failure_does_not_sink_the_others(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_app_settings(db_session, calorie_ninjas_api_key="test-key")
    broken = _zeroed_ingredient("broken")
    fine = _zeroed_ingredient("fine")
    db_session.add_all([broken, fine])
    db_session.commit()
    job = _create_job(db_session)

    def _fake_lookup(query: str, key: str) -> dict:
        if query == "100g broken":
            raise RuntimeError("simulated outage")
        return _lookup_item()

    monkeypatch.setattr(ingredient_refresh_handlers, "lookup_nutrition", _fake_lookup)

    handle_ingredient_refresh_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == IngredientRefreshJobStatus.DONE
    assert job.ingredients_updated == 1

    db_session.refresh(fine)
    assert fine.calories_per_100g == 40.0
    db_session.refresh(broken)
    assert broken.calories_per_100g == 0  # left untouched after its lookup failed


def test_fails_cleanly_when_no_api_key_is_configured(db_session: Session) -> None:
    _seed_app_settings(db_session, calorie_ninjas_api_key="")
    db_session.add(_zeroed_ingredient("onion"))
    db_session.commit()
    job = _create_job(db_session)

    handle_ingredient_refresh_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == IngredientRefreshJobStatus.FAILED
    assert "No CalorieNinjas API key configured" in job.error
    assert job.ingredients_updated is None


def test_ignores_unknown_job_id(db_session: Session) -> None:
    handle_ingredient_refresh_job(json.dumps({"job_id": 999}).encode(), db_session)

    assert db_session.scalars(select(IngredientRefreshJob)).first() is None
