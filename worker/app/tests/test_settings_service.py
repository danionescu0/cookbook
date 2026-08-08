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
    assert snapshot.preferred_ai_provider == "claude"
    assert snapshot.ai_api_key == ""


def test_get_settings_reads_current_row(db_session: Session) -> None:
    db_session.add(
        AppSettings(
            id=1,
            supported_languages="ro,en,fr",
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
            anthropic_api_key="sk-ant-test",
            calorie_ninjas_api_key="calorie-ninjas-test-key",
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
    # Not set on this row — falls back to the SQLAlchemy column default, same as any other
    # unset-in-the-fixture field above.
    assert snapshot.preferred_ai_provider == "claude"
    assert snapshot.ai_api_key == "sk-ant-test"


def test_ai_api_key_resolves_to_deepseek_key_when_that_provider_is_preferred(
    db_session: Session,
) -> None:
    db_session.add(
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
            anthropic_api_key="sk-ant-test",
            calorie_ninjas_api_key="",
            default_rate_limit_requests_per_minute=6,
            scrape_timeout_seconds=15.0,
            max_html_chars=200_000,
            image_max_dimension=1600,
            image_max_size_kb=500,
            preferred_ai_provider="deepseek",
            deepseek_api_key="sk-deepseek-test",
        )
    )
    db_session.commit()

    snapshot = get_settings(db_session)

    assert snapshot.preferred_ai_provider == "deepseek"
    # The Anthropic key is still readable on the snapshot, but claude_client calls must use the
    # resolved ai_api_key — not anthropic_api_key directly — so a provider switch doesn't need
    # every call site to re-derive which key applies.
    assert snapshot.anthropic_api_key == "sk-ant-test"
    assert snapshot.ai_api_key == "sk-deepseek-test"


def test_get_settings_reflects_a_row_update_on_the_next_call(db_session: Session) -> None:
    # No cache: a change an admin applies must be visible to the very next job, not just new
    # instances/processes.
    db_session.add(
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
            calorie_ninjas_api_key="",
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
