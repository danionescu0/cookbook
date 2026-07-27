from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import AppSettings
from app.settings_service import get_settings


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


def test_get_settings_falls_back_to_defaults_when_row_missing(db_session: Session) -> None:
    snapshot = get_settings(db_session)

    assert snapshot.supported_languages_list == ["ro", "en"]
    assert snapshot.default_language == "ro"
    assert snapshot.default_rate_limit_requests_per_minute == 6


def test_get_settings_reads_current_row(db_session: Session) -> None:
    db_session.add(
        AppSettings(
            id=1,
            supported_languages="ro,en,fr",
            default_language="en",
            admin_password="secret",
            anthropic_api_key="sk-ant-test",
            default_rate_limit_requests_per_minute=12,
            scrape_timeout_seconds=20.0,
            max_html_chars=50_000,
            image_max_dimension=800,
            image_max_size_kb=250,
        )
    )
    db_session.commit()

    snapshot = get_settings(db_session)

    assert snapshot.supported_languages_list == ["ro", "en", "fr"]
    assert snapshot.default_language == "en"
    assert snapshot.anthropic_api_key == "sk-ant-test"
    assert snapshot.default_rate_limit_requests_per_minute == 12
    assert snapshot.scrape_timeout_seconds == 20.0
    assert snapshot.max_html_chars == 50_000
    assert snapshot.image_max_dimension == 800
    assert snapshot.image_max_size_kb == 250


def test_get_settings_reflects_a_row_update_on_the_next_call(db_session: Session) -> None:
    # No cache: a change an admin applies must be visible to the very next job, not just new
    # instances/processes.
    db_session.add(
        AppSettings(
            id=1,
            supported_languages="ro,en",
            default_language="ro",
            admin_password="secret",
            anthropic_api_key="",
            default_rate_limit_requests_per_minute=6,
            scrape_timeout_seconds=15.0,
            max_html_chars=200_000,
            image_max_dimension=1600,
            image_max_size_kb=500,
        )
    )
    db_session.commit()

    assert get_settings(db_session).default_rate_limit_requests_per_minute == 6

    row = db_session.get(AppSettings, 1)
    row.default_rate_limit_requests_per_minute = 30
    db_session.commit()

    assert get_settings(db_session).default_rate_limit_requests_per_minute == 30
