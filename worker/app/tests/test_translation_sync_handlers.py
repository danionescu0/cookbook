import json
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import translation_sync_handlers
from app.database import Base
from app.models import (
    AppSettings,
    Recipe,
    RecipeTranslation,
    TranslationSyncJob,
    TranslationSyncJobStatus,
)
from app.translation_sync_handlers import handle_translation_sync_job


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


def _seed_app_settings(db: Session, supported_languages: str = "ro,en") -> None:
    db.add(
        AppSettings(
            id=1,
            supported_languages=supported_languages,
            default_language=supported_languages.split(",")[0],
            admin_password="x",
            anthropic_api_key="test-key",
            calorie_ninjas_api_key="",
            default_rate_limit_requests_per_minute=6,
            scrape_timeout_seconds=15.0,
            max_html_chars=200_000,
            image_max_dimension=1600,
            image_max_size_kb=500,
        )
    )
    db.commit()


def _create_recipe(db: Session, ro_ingredients: list[str] | None = None) -> Recipe:
    recipe = Recipe(category_id=1)
    recipe.translations.append(
        RecipeTranslation(language="ro", title="Ciorbă", ingredients=ro_ingredients or ["apă"])
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


def _create_job(
    db: Session, recipe_id: int, source_language: str = "ro"
) -> TranslationSyncJob:
    job = TranslationSyncJob(
        recipe_id=recipe_id,
        source_language=source_language,
        status=TranslationSyncJobStatus.QUEUED,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


_EN_TRANSLATION = {
    "translations": [
        {
            "language": "en",
            "title": "Soup",
            "description": "A soup.",
            "ingredients": ["water", "salt"],
            "steps": ["boil"],
            "tips": [],
        }
    ]
}


def test_handle_translation_sync_job_translates_to_other_languages(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_app_settings(db_session)
    recipe = _create_recipe(db_session, ["apă", "sare"])
    job = _create_job(db_session, recipe.id, source_language="ro")
    received = []
    monkeypatch.setattr(
        translation_sync_handlers,
        "translate_recipe",
        lambda source, targets, api_key: received.append((source, targets, api_key))
        or _EN_TRANSLATION,
    )
    monkeypatch.setattr(
        translation_sync_handlers, "_enqueue_nutrition_job", lambda db, recipe_id: None
    )

    handle_translation_sync_job(
        json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session
    )

    db_session.refresh(job)
    assert job.status == TranslationSyncJobStatus.DONE
    assert job.error is None
    assert received == [
        (
            {"title": "Ciorbă", "description": "", "ingredients": ["apă", "sare"], "steps": [], "tips": []},
            ["en"],
            "test-key",
        )
    ]

    en = db_session.scalars(
        select(RecipeTranslation).where(RecipeTranslation.language == "en")
    ).one()
    assert en.title == "Soup"
    assert en.ingredients == ["water", "salt"]


def test_handle_translation_sync_job_creates_missing_target_language(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_app_settings(db_session)
    recipe = _create_recipe(db_session)  # only "ro" exists yet
    job = _create_job(db_session, recipe.id, source_language="ro")
    monkeypatch.setattr(
        translation_sync_handlers, "translate_recipe", lambda s, t, k: _EN_TRANSLATION
    )
    monkeypatch.setattr(
        translation_sync_handlers, "_enqueue_nutrition_job", lambda db, recipe_id: None
    )

    handle_translation_sync_job(
        json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session
    )

    languages = {t.language for t in db_session.scalars(select(RecipeTranslation)).all()}
    assert languages == {"ro", "en"}


def test_handle_translation_sync_job_enqueues_nutrition_job_after_sync(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_app_settings(db_session)
    recipe = _create_recipe(db_session)
    job = _create_job(db_session, recipe.id)
    monkeypatch.setattr(
        translation_sync_handlers, "translate_recipe", lambda s, t, k: _EN_TRANSLATION
    )
    enqueued = []
    monkeypatch.setattr(
        translation_sync_handlers,
        "_enqueue_nutrition_job",
        lambda db, recipe_id: enqueued.append(recipe_id),
    )

    handle_translation_sync_job(
        json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session
    )

    assert enqueued == [recipe.id]


def test_handle_translation_sync_job_skips_claude_call_when_no_other_languages(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_app_settings(db_session, supported_languages="ro")  # single-language site
    recipe = _create_recipe(db_session)
    job = _create_job(db_session, recipe.id)

    def _fail(*args: object, **kwargs: object) -> dict:
        raise AssertionError("translate_recipe should not be called with no other languages")

    monkeypatch.setattr(translation_sync_handlers, "translate_recipe", _fail)
    enqueued = []
    monkeypatch.setattr(
        translation_sync_handlers,
        "_enqueue_nutrition_job",
        lambda db, recipe_id: enqueued.append(recipe_id),
    )

    handle_translation_sync_job(
        json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session
    )

    db_session.refresh(job)
    assert job.status == TranslationSyncJobStatus.DONE
    assert enqueued == [recipe.id]


def test_handle_translation_sync_job_fails_when_source_translation_missing(
    db_session: Session,
) -> None:
    _seed_app_settings(db_session)
    recipe = _create_recipe(db_session)  # only "ro" exists
    job = _create_job(db_session, recipe.id, source_language="en")  # "en" doesn't exist yet

    handle_translation_sync_job(
        json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session
    )

    db_session.refresh(job)
    assert job.status == TranslationSyncJobStatus.FAILED
    assert "source translation" in job.error


def test_handle_translation_sync_job_fails_when_recipe_not_found(db_session: Session) -> None:
    job = TranslationSyncJob(
        recipe_id=999, source_language="ro", status=TranslationSyncJobStatus.QUEUED
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    handle_translation_sync_job(
        json.dumps({"job_id": job.id, "recipe_id": 999}).encode(), db_session
    )

    db_session.refresh(job)
    assert job.status == TranslationSyncJobStatus.FAILED
    assert job.error == "recipe not found"


def test_handle_translation_sync_job_ignores_unknown_job_id(db_session: Session) -> None:
    handle_translation_sync_job(json.dumps({"job_id": 999, "recipe_id": 1}).encode(), db_session)


def test_handle_translation_sync_job_still_succeeds_when_nutrition_enqueue_raises(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_app_settings(db_session)
    recipe = _create_recipe(db_session)
    job = _create_job(db_session, recipe.id)
    monkeypatch.setattr(
        translation_sync_handlers, "translate_recipe", lambda s, t, k: _EN_TRANSLATION
    )

    def _raise(db: object, recipe_id: int) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(translation_sync_handlers, "_enqueue_nutrition_job", _raise)

    handle_translation_sync_job(
        json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session
    )

    db_session.refresh(job)
    assert job.status == TranslationSyncJobStatus.DONE
    assert job.error is None
