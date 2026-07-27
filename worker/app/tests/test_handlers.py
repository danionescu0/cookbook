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
from app.models import ImportJob, ImportJobStatus, Recipe, RecipeStatus, RecipeTranslation
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


def _create_job(db: Session, source: str = "https://example.com/recipe") -> ImportJob:
    job = ImportJob(source=source, category_id=1)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


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
    monkeypatch.setattr(handlers, "fetch_page", lambda url, app_settings: "<html>raw</html>")
    monkeypatch.setattr(
        handlers,
        "extract_recipe",
        lambda html, languages, api_key: _TWO_LANGUAGE_EXTRACTION,
    )
    process_images_calls = []
    monkeypatch.setattr(
        handlers,
        "process_images",
        lambda urls, app_settings: process_images_calls.append(urls) or ["/images/stored.jpg"],
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
    assert process_images_calls == [["https://example.com/cake.jpg"]]  # resolved against source_url

    translations = db_session.scalars(select(RecipeTranslation)).all()
    by_language = {t.language: t for t in translations}
    assert set(by_language) == {"ro", "en"}
    assert by_language["ro"].title == "Prăjitură"
    assert by_language["en"].title == "Cake"
    assert by_language["en"].ingredients == ["flour", "sugar"]


def test_handle_import_job_fails_when_robots_disallow(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _create_job(db_session)

    def _raise(url: str, app_settings: object) -> str:
        raise ScrapeDisallowedError("robots.txt on example.com disallows fetching this page")

    monkeypatch.setattr(handlers, "fetch_page", _raise)

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.FAILED
    assert "disallows" in job.error
    assert db_session.scalars(select(Recipe)).first() is None


def test_handle_import_job_fails_on_fetch_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _create_job(db_session)

    def _raise(url: str, app_settings: object) -> str:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(handlers, "fetch_page", _raise)

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.FAILED
    assert "failed to fetch page" in job.error


def test_handle_import_job_fails_on_extraction_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _create_job(db_session)
    monkeypatch.setattr(handlers, "fetch_page", lambda url, app_settings: "<html>raw</html>")

    def _raise(html: str, languages: list[str], api_key: str) -> dict:
        raise RecipeExtractionError("Claude did not return a structured recipe")

    monkeypatch.setattr(handlers, "extract_recipe", _raise)

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.FAILED
    assert job.error == "Claude did not return a structured recipe"
    assert db_session.scalars(select(Recipe)).first() is None


def test_handle_import_job_fails_when_translations_empty(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _create_job(db_session)
    monkeypatch.setattr(handlers, "fetch_page", lambda url, app_settings: "<html>raw</html>")
    monkeypatch.setattr(
        handlers,
        "extract_recipe",
        lambda html, languages, api_key: {"images": [], "translations": []},
    )

    handle_import_job(json.dumps({"job_id": job.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == ImportJobStatus.FAILED
    assert job.error == "Claude returned no translations"
    assert db_session.scalars(select(Recipe)).first() is None


def test_handle_import_job_ignores_unknown_job_id(db_session: Session) -> None:
    handle_import_job(json.dumps({"job_id": 999}).encode(), db_session)
