import json
from collections.abc import Generator

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import handlers
from app.claude_client import RecipeExtractionError
from app.database import Base
from app.handlers import handle_import_job
from app.instagram_client import InstagramFetchError, InstagramPost
from app.models import (
    Category,
    ImportErrorKind,
    ImportJob,
    ImportJobStatus,
    ImportJobType,
    NutritionJob,
    NutritionJobStatus,
    Recipe,
    RecipeStatus,
    RecipeTranslation,
    User,
)
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


def _create_job(
    db: Session,
    source: str = "https://example.com/recipe",
    type: ImportJobType = ImportJobType.SINGLE,
    created_by_user_id: int = 1,
) -> ImportJob:
    # category_id starts null now — the handler resolves it from Claude's own suggestion once
    # extraction succeeds (see _resolve_category_id), rather than the requester picking one up
    # front. See _seed_category for populating the list the handler resolves against.
    job = ImportJob(source=source, type=type, created_by_user_id=created_by_user_id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _seed_category(db: Session, name: str = "Desserts") -> Category:
    category = Category(name=name, slug=name.lower().replace(" ", "-"))
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


_TWO_LANGUAGE_EXTRACTION = {
    "images": ["/cake.jpg"],
    "translations": [
        {
            "language": "ro",
            "title": "Prăjitură",
            "description": "O prăjitură.",
            "ingredients": ["făină", "zahăr"],
            "steps": ["amestecă", "coace"],
            "tips": ["răcește înainte de servire"],
        },
        {
            "language": "en",
            "title": "Cake",
            "description": "A cake.",
            "ingredients": ["flour", "sugar"],
            "steps": ["mix", "bake"],
            "tips": ["cool before serving"],
        },
    ],
}


def test_handle_import_job_inserts_recipe_with_one_translation_per_language(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _create_job(db_session)
    _seed_category(db_session)
    monkeypatch.setattr(handlers, "fetch_page", lambda url, app_settings: "<html>raw</html>")
    monkeypatch.setattr(
        handlers,
        "extract_recipe",
        lambda html, languages, api_key, category_names, **kwargs: _TWO_LANGUAGE_EXTRACTION,
    )
    process_images_calls = []
    monkeypatch.setattr(
        handlers,
        "process_images",
        lambda urls, app_settings: process_images_calls.append(urls) or ["/images/stored.jpg"],
    )
    published = []
    monkeypatch.setattr(
        handlers,
        "publish_nutrition_job",
        lambda job_id, recipe_id: published.append((job_id, recipe_id)),
    )

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.DONE
    assert job.error is None

    recipe = db_session.scalars(select(Recipe)).one()
    assert recipe.category_id == job.category_id
    assert recipe.source_url == job.source
    # An admin already approved importing this URL (see POST /imports/{id}/approve), so a
    # successful import publishes immediately rather than landing as a second unapproved step.
    assert recipe.status == RecipeStatus.APPROVED
    assert recipe.approved_at is not None
    assert recipe.images == ["/images/stored.jpg"]  # what process_images returned
    # Owned by whoever created the import job — imports are never shared, no matter what.
    assert recipe.owner_user_id == job.created_by_user_id
    assert recipe.is_shared is False
    assert process_images_calls == [["https://example.com/cake.jpg"]]  # resolved against source_url

    translations = db_session.scalars(select(RecipeTranslation)).all()
    by_language = {t.language: t for t in translations}
    assert set(by_language) == {"ro", "en"}
    assert by_language["ro"].title == "Prăjitură"
    assert by_language["en"].title == "Cake"
    assert by_language["en"].ingredients == ["flour", "sugar"]

    # A successful import auto-enqueues nutrition enrichment — no more manual "Enrich nutrition"
    # button; see README Design Decisions ("Ingredient nutrition").
    nutrition_job = db_session.scalars(select(NutritionJob)).one()
    assert nutrition_job.recipe_id == recipe.id
    assert nutrition_job.status == NutritionJobStatus.QUEUED
    assert published == [(nutrition_job.id, recipe.id)]


def test_handle_import_job_increments_owners_lifetime_import_count(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = User(id=1, username="tester", imported_recipes_count=4)
    db_session.add(user)
    db_session.commit()

    job = _create_job(db_session, created_by_user_id=user.id)
    _seed_category(db_session)
    monkeypatch.setattr(handlers, "fetch_page", lambda url, app_settings: "<html>raw</html>")
    monkeypatch.setattr(
        handlers, "extract_recipe", lambda html, languages, api_key, category_names, **kwargs: _TWO_LANGUAGE_EXTRACTION
    )
    monkeypatch.setattr(
        handlers, "process_images", lambda urls, app_settings: ["/images/stored.jpg"]
    )
    monkeypatch.setattr(handlers, "publish_nutrition_job", lambda job_id, recipe_id: None)

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.DONE
    db_session.refresh(user)
    assert user.imported_recipes_count == 5


def test_handle_import_job_does_not_increment_count_on_failure(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Only successful imports should count toward the lifetime cap — see
    # app_settings.max_imports_per_user on the API side.
    user = User(id=1, username="tester", imported_recipes_count=4)
    db_session.add(user)
    db_session.commit()

    job = _create_job(db_session, created_by_user_id=user.id)
    _seed_category(db_session)
    monkeypatch.setattr(handlers, "fetch_page", lambda url, app_settings: "<html>raw</html>")

    def _raise(html: str, languages: list[str], api_key: str, category_names: list[str], **kwargs: object) -> dict:
        raise RecipeExtractionError("boom")

    monkeypatch.setattr(handlers, "extract_recipe", _raise)

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.FAILED
    db_session.refresh(user)
    assert user.imported_recipes_count == 4


def test_handle_import_job_marks_nutrition_job_failed_when_publish_fails(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The import itself already succeeded — a broken queue publish for the *follow-up* nutrition
    # job must not turn a successful import into a reported failure.
    job = _create_job(db_session)
    _seed_category(db_session)
    monkeypatch.setattr(handlers, "fetch_page", lambda url, app_settings: "<html>raw</html>")
    monkeypatch.setattr(
        handlers, "extract_recipe", lambda html, languages, api_key, category_names, **kwargs: _TWO_LANGUAGE_EXTRACTION
    )
    monkeypatch.setattr(handlers, "process_images", lambda urls, app_settings: [])

    def _raise_publish(job_id: int, recipe_id: int) -> None:
        raise RuntimeError("rabbitmq unreachable")

    monkeypatch.setattr(handlers, "publish_nutrition_job", _raise_publish)

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.DONE
    assert job.error is None

    nutrition_job = db_session.scalars(select(NutritionJob)).one()
    assert nutrition_job.status == NutritionJobStatus.FAILED
    assert "failed to publish to queue" in nutrition_job.error


def test_handle_import_job_still_succeeds_when_nutrition_enqueue_itself_raises(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _create_job(db_session)
    _seed_category(db_session)
    monkeypatch.setattr(handlers, "fetch_page", lambda url, app_settings: "<html>raw</html>")
    monkeypatch.setattr(
        handlers, "extract_recipe", lambda html, languages, api_key, category_names, **kwargs: _TWO_LANGUAGE_EXTRACTION
    )
    monkeypatch.setattr(handlers, "process_images", lambda urls, app_settings: [])

    def _raise(db: object, recipe_id: int) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(handlers, "_enqueue_nutrition_job", _raise)

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.DONE
    assert job.error is None
    assert db_session.scalars(select(Recipe)).first() is not None


def test_handle_import_job_fails_when_robots_disallow(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _create_job(db_session)
    _seed_category(db_session)

    def _raise(url: str, app_settings: object) -> str:
        raise ScrapeDisallowedError("robots.txt on example.com disallows fetching this page")

    monkeypatch.setattr(handlers, "fetch_page", _raise)

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.FAILED
    assert "disallows" in job.error
    # The one error_kind that isn't TECHNICAL — retrying won't help, so a non-admin viewer gets a
    # distinct, non-actionable message (see api's routers/imports.py _serialize).
    assert job.error_kind == ImportErrorKind.DISALLOWED
    assert db_session.scalars(select(Recipe)).first() is None


def test_handle_import_job_fails_on_fetch_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _create_job(db_session)
    _seed_category(db_session)

    def _raise(url: str, app_settings: object) -> str:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(handlers, "fetch_page", _raise)

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.FAILED
    assert "failed to fetch page" in job.error
    assert job.error_kind == ImportErrorKind.TECHNICAL


def test_handle_import_job_fails_on_extraction_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _create_job(db_session)
    _seed_category(db_session)
    monkeypatch.setattr(handlers, "fetch_page", lambda url, app_settings: "<html>raw</html>")

    def _raise(html: str, languages: list[str], api_key: str, category_names: list[str], **kwargs: object) -> dict:
        raise RecipeExtractionError("Claude did not return a structured recipe")

    monkeypatch.setattr(handlers, "extract_recipe", _raise)

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.FAILED
    assert job.error == "Claude did not return a structured recipe"
    assert job.error_kind == ImportErrorKind.TECHNICAL
    assert db_session.scalars(select(Recipe)).first() is None


def test_handle_import_job_fails_when_translations_empty(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _create_job(db_session)
    _seed_category(db_session)
    monkeypatch.setattr(handlers, "fetch_page", lambda url, app_settings: "<html>raw</html>")
    monkeypatch.setattr(
        handlers,
        "extract_recipe",
        lambda html, languages, api_key, category_names, **kwargs: {"images": [], "translations": []},
    )

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.FAILED
    assert job.error == "Claude returned no translations"
    assert db_session.scalars(select(Recipe)).first() is None


def test_handle_import_job_ignores_unknown_job_id(db_session: Session) -> None:
    handle_import_job(json.dumps({"job_id": 999}).encode(), db_session)


def test_handle_import_job_fails_when_no_categories_exist(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # There's always at least one category in production (see CategoryManager), but a fresh/empty
    # DB has none — must fail cleanly with an actionable message rather than crash trying to pick
    # from an empty list.
    job = _create_job(db_session)
    monkeypatch.setattr(handlers, "fetch_page", lambda url, app_settings: "<html>raw</html>")

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.FAILED
    assert "No categories exist yet" in job.error
    assert db_session.scalars(select(Recipe)).first() is None


def test_handle_import_job_resolves_claudes_suggested_category_by_name(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _create_job(db_session)
    _seed_category(db_session, name="Desserts")
    main_course = _seed_category(db_session, name="Main course")
    monkeypatch.setattr(handlers, "fetch_page", lambda url, app_settings: "<html>raw</html>")
    monkeypatch.setattr(
        handlers,
        "extract_recipe",
        lambda html, languages, api_key, category_names, **kwargs: {
            **_TWO_LANGUAGE_EXTRACTION,
            # A case mismatch against the real "Main course" name — still expected to resolve,
            # since _resolve_category_id compares case-insensitively.
            "category": "main course",
        },
    )
    monkeypatch.setattr(handlers, "process_images", lambda urls, app_settings: [])
    monkeypatch.setattr(handlers, "publish_nutrition_job", lambda job_id, recipe_id: None)

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.DONE
    assert job.category_id == main_course.id
    recipe = db_session.scalars(select(Recipe)).one()
    assert recipe.category_id == main_course.id


def test_handle_import_job_falls_back_to_first_category_when_claudes_suggestion_does_not_match(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _create_job(db_session)
    first_category = _seed_category(db_session, name="Desserts")
    _seed_category(db_session, name="Main course")
    monkeypatch.setattr(handlers, "fetch_page", lambda url, app_settings: "<html>raw</html>")
    monkeypatch.setattr(
        handlers,
        "extract_recipe",
        lambda html, languages, api_key, category_names, **kwargs: {
            **_TWO_LANGUAGE_EXTRACTION,
            "category": "Something Claude made up",
        },
    )
    monkeypatch.setattr(handlers, "process_images", lambda urls, app_settings: [])
    monkeypatch.setattr(handlers, "publish_nutrition_job", lambda job_id, recipe_id: None)

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.DONE
    assert job.category_id == first_category.id


_ONE_LANGUAGE_TEXT_EXTRACTION = {
    "translations": [
        {
            "language": "ro",
            "title": "Batoane cu mere",
            "description": "",
            "ingredients": ["mere", "fulgi de ovaz"],
            "steps": ["amestecă", "coace"],
            "tips": [],
        }
    ]
}


def test_handle_import_job_instagram_inserts_recipe_from_caption_text(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _create_job(
        db_session, source="https://www.instagram.com/p/abc123/", type=ImportJobType.INSTAGRAM
    )
    _seed_category(db_session)
    monkeypatch.setattr(
        handlers,
        "fetch_instagram_post",
        lambda url, timeout_seconds: InstagramPost(
            text="caption + comments", image_url="https://scontent.cdninstagram.com/photo.jpg"
        ),
    )
    monkeypatch.setattr(
        handlers,
        "parse_recipe_from_text",
        lambda text, languages, api_key, category_names, **kwargs: _ONE_LANGUAGE_TEXT_EXTRACTION,
    )
    process_images_calls = []
    monkeypatch.setattr(
        handlers,
        "process_images",
        lambda urls, app_settings: process_images_calls.append(urls) or ["/images/ig.jpg"],
    )
    monkeypatch.setattr(handlers, "publish_nutrition_job", lambda job_id, recipe_id: None)

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.DONE
    assert job.error is None
    # The image comes from what fetch_instagram_post resolved (the post's own og:image), not
    # from anything Claude's text-only extraction returns.
    assert process_images_calls == [["https://scontent.cdninstagram.com/photo.jpg"]]

    recipe = db_session.scalars(select(Recipe)).one()
    assert recipe.source_url == job.source
    assert recipe.images == ["/images/ig.jpg"]
    translation = db_session.scalars(select(RecipeTranslation)).one()
    assert translation.title == "Batoane cu mere"


def test_handle_import_job_instagram_fails_cleanly_when_fetch_raises(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _create_job(
        db_session, source="https://www.instagram.com/p/private/", type=ImportJobType.INSTAGRAM
    )
    _seed_category(db_session)

    def _raise(url: str, timeout_seconds: float) -> InstagramPost:
        raise InstagramFetchError("Instagram asked for a login on this post")

    monkeypatch.setattr(handlers, "fetch_instagram_post", _raise)

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.FAILED
    assert job.error == "Instagram asked for a login on this post"
    assert job.error_kind == ImportErrorKind.TECHNICAL
    assert db_session.scalars(select(Recipe)).first() is None


def test_handle_import_job_instagram_fails_when_no_recipe_in_text(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _create_job(
        db_session, source="https://www.instagram.com/p/norecipe/", type=ImportJobType.INSTAGRAM
    )
    _seed_category(db_session)
    monkeypatch.setattr(
        handlers,
        "fetch_instagram_post",
        lambda url, timeout_seconds: InstagramPost(text="just a selfie, no recipe", image_url=None),
    )
    monkeypatch.setattr(
        handlers, "parse_recipe_from_text", lambda text, languages, api_key, category_names, **kwargs: {"translations": []}
    )

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.FAILED
    assert job.error == "Claude returned no translations"
    assert db_session.scalars(select(Recipe)).first() is None
