import json
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import reparse_handlers
from app.database import Base
from app.instagram_client import InstagramFetchError, InstagramPost
from app.models import AppSettings, Recipe, RecipeReparseJob, RecipeReparseJobStatus, RecipeTranslation
from app.reparse_handlers import handle_reparse_job
from app.scraping import ScrapeDisallowedError


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


def _seed_app_settings(db: Session) -> None:
    db.add(
        AppSettings(
            id=1,
            supported_languages="en,ro",
            default_language="en",
            smtp_host="",
            smtp_port=587,
            smtp_username="",
            smtp_password="",
            smtp_from_address="",
            smtp_use_tls=True,
            turnstile_site_key="",
            turnstile_secret_key="",
            public_site_url="",
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


def _create_recipe(db: Session, source_url: str | None = "https://example.com/soup") -> Recipe:
    recipe = Recipe(category_id=1, owner_user_id=1, source_url=source_url, images=[])
    recipe.translations.append(
        RecipeTranslation(language="en", title="Soup", slug="soup", ingredients=["water"])
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


def _create_job(db: Session, recipe_id: int) -> RecipeReparseJob:
    job = RecipeReparseJob(recipe_id=recipe_id, status=RecipeReparseJobStatus.QUEUED)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


_EXTRACTED = {
    "images": ["https://example.com/soup.jpg"],
    "translations": [
        {
            "language": "en",
            "title": "Soup Deluxe",
            "description": "An even better soup.",
            "ingredients": ["### For the broth", "water", "salt"],
            "steps": ["Boil"],
            "tips": [],
        }
    ],
}


def test_handle_reparse_job_updates_existing_translation_in_place(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_app_settings(db_session)
    recipe = _create_recipe(db_session)
    job = _create_job(db_session, recipe.id)
    monkeypatch.setattr(reparse_handlers, "fetch_page", lambda url, settings: "<html></html>")
    monkeypatch.setattr(
        reparse_handlers, "extract_recipe", lambda html, langs, key, category_names, **kwargs: _EXTRACTED
    )
    monkeypatch.setattr(reparse_handlers, "_enqueue_nutrition_job", lambda db, recipe_id: None)

    handle_reparse_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == RecipeReparseJobStatus.DONE
    assert job.error is None

    translation = db_session.scalars(
        select(RecipeTranslation).where(RecipeTranslation.recipe_id == recipe.id)
    ).one()
    assert translation.title == "Soup Deluxe"
    assert translation.ingredients == ["### For the broth", "water", "salt"]
    # Slug is immutable once set — a reparse must never change it, even though the title did.
    assert translation.slug == "soup"

    # Recipe id, owner, and images are untouched — only the translation content changed.
    db_session.refresh(recipe)
    assert recipe.id == job.recipe_id
    assert recipe.images == []


def test_handle_reparse_job_gives_a_new_language_a_fresh_slug(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_app_settings(db_session)
    recipe = _create_recipe(db_session)
    job = _create_job(db_session, recipe.id)
    extracted_with_new_language = {
        "images": [],
        "translations": [
            *_EXTRACTED["translations"],
            {
                "language": "ro",
                "title": "Supă Deluxe",
                "description": "",
                "ingredients": ["apă"],
                "steps": [],
                "tips": [],
            },
        ],
    }
    monkeypatch.setattr(reparse_handlers, "fetch_page", lambda url, settings: "<html></html>")
    monkeypatch.setattr(
        reparse_handlers, "extract_recipe", lambda html, langs, key, category_names, **kwargs: extracted_with_new_language
    )
    monkeypatch.setattr(reparse_handlers, "_enqueue_nutrition_job", lambda db, recipe_id: None)

    handle_reparse_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    ro = db_session.scalars(
        select(RecipeTranslation).where(RecipeTranslation.language == "ro")
    ).one()
    assert ro.title == "Supă Deluxe"
    assert ro.slug == "supa-deluxe"


def test_handle_reparse_job_enqueues_nutrition_job_after_success(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_app_settings(db_session)
    recipe = _create_recipe(db_session)
    job = _create_job(db_session, recipe.id)
    monkeypatch.setattr(reparse_handlers, "fetch_page", lambda url, settings: "<html></html>")
    monkeypatch.setattr(
        reparse_handlers, "extract_recipe", lambda html, langs, key, category_names, **kwargs: _EXTRACTED
    )
    enqueued = []
    monkeypatch.setattr(
        reparse_handlers, "_enqueue_nutrition_job", lambda db, recipe_id: enqueued.append(recipe_id)
    )

    handle_reparse_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    assert enqueued == [recipe.id]


def test_handle_reparse_job_routes_instagram_urls_through_the_text_extraction_path(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_app_settings(db_session)
    recipe = _create_recipe(db_session, source_url="https://www.instagram.com/p/abc123/")
    job = _create_job(db_session, recipe.id)

    def _fail_fetch_page(*args: object, **kwargs: object) -> str:
        raise AssertionError("fetch_page should not be called for an Instagram URL")

    monkeypatch.setattr(reparse_handlers, "fetch_page", _fail_fetch_page)
    monkeypatch.setattr(
        reparse_handlers,
        "fetch_instagram_post",
        lambda url, timeout: InstagramPost(text="caption text", image_url=None),
    )
    monkeypatch.setattr(
        reparse_handlers, "parse_recipe_from_text", lambda text, langs, key, category_names, **kwargs: _EXTRACTED
    )
    monkeypatch.setattr(reparse_handlers, "_enqueue_nutrition_job", lambda db, recipe_id: None)

    handle_reparse_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == RecipeReparseJobStatus.DONE


def test_handle_reparse_job_fails_when_recipe_has_no_source_url(db_session: Session) -> None:
    recipe = _create_recipe(db_session, source_url=None)
    job = _create_job(db_session, recipe.id)

    handle_reparse_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == RecipeReparseJobStatus.FAILED
    assert "source_url" in job.error


def test_handle_reparse_job_fails_when_recipe_not_found(db_session: Session) -> None:
    job = RecipeReparseJob(recipe_id=999, status=RecipeReparseJobStatus.QUEUED)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    handle_reparse_job(json.dumps({"job_id": job.id, "recipe_id": 999}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == RecipeReparseJobStatus.FAILED
    assert job.error == "recipe not found"


def test_handle_reparse_job_ignores_unknown_job_id(db_session: Session) -> None:
    handle_reparse_job(json.dumps({"job_id": 999, "recipe_id": 1}).encode(), db_session)


def test_handle_reparse_job_fails_cleanly_on_scrape_disallowed(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_app_settings(db_session)
    recipe = _create_recipe(db_session)
    job = _create_job(db_session, recipe.id)

    def _raise(*args: object, **kwargs: object) -> str:
        raise ScrapeDisallowedError("robots.txt disallows this path")

    monkeypatch.setattr(reparse_handlers, "fetch_page", _raise)

    handle_reparse_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == RecipeReparseJobStatus.FAILED
    assert job.error == "robots.txt disallows this path"


def test_handle_reparse_job_fails_cleanly_on_instagram_fetch_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_app_settings(db_session)
    recipe = _create_recipe(db_session, source_url="https://www.instagram.com/p/abc123/")
    job = _create_job(db_session, recipe.id)

    def _raise(*args: object, **kwargs: object) -> InstagramPost:
        raise InstagramFetchError("could not load the post")

    monkeypatch.setattr(reparse_handlers, "fetch_instagram_post", _raise)

    handle_reparse_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == RecipeReparseJobStatus.FAILED
    assert job.error == "could not load the post"


def test_handle_reparse_job_still_succeeds_when_nutrition_enqueue_raises(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_app_settings(db_session)
    recipe = _create_recipe(db_session)
    job = _create_job(db_session, recipe.id)
    monkeypatch.setattr(reparse_handlers, "fetch_page", lambda url, settings: "<html></html>")
    monkeypatch.setattr(
        reparse_handlers, "extract_recipe", lambda html, langs, key, category_names, **kwargs: _EXTRACTED
    )

    def _raise(db: object, recipe_id: int) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(reparse_handlers, "_enqueue_nutrition_job", _raise)

    handle_reparse_job(json.dumps({"job_id": job.id, "recipe_id": recipe.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == RecipeReparseJobStatus.DONE
    assert job.error is None
