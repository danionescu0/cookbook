import json
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import contact_handlers
from app.contact_handlers import handle_contact_message_job
from app.database import Base
from app.models import AppSettings, ContactMessage, ContactMessageStatus


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


def _seed_app_settings(db: Session, contact_recipient_email: str = "owner@example.com") -> None:
    db.add(
        AppSettings(
            id=1,
            supported_languages="ro,en",
            default_language="ro",
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="bot@example.com",
            smtp_password="smtp-secret",
            smtp_from_address="no-reply@example.com",
            smtp_use_tls=True,
            turnstile_site_key="",
            turnstile_secret_key="",
            public_site_url="https://cookbook.example.com",
            anthropic_api_key="",
            calorie_ninjas_api_key="",
            default_rate_limit_requests_per_minute=6,
            scrape_timeout_seconds=15.0,
            max_html_chars=200_000,
            image_max_dimension=1600,
            image_max_size_kb=500,
            contact_recipient_email=contact_recipient_email,
        )
    )
    db.commit()


def _create_message(
    db: Session,
    name: str = "Ana",
    email: str | None = "ana@example.com",
    phone: str | None = None,
    message: str = "x" * 50,
) -> ContactMessage:
    row = ContactMessage(
        name=name, email=email, phone=phone, message=message, status=ContactMessageStatus.QUEUED
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


class _FakeSmtp:
    instances: list["_FakeSmtp"] = []

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.started_tls = False
        self.login_args: tuple[str, str] | None = None
        self.sent_messages: list[object] = []
        _FakeSmtp.instances.append(self)

    def __enter__(self) -> "_FakeSmtp":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    def send_message(self, message: object) -> None:
        self.sent_messages.append(message)


@pytest.fixture(autouse=True)
def _fake_smtp(monkeypatch: pytest.MonkeyPatch) -> Generator[list[_FakeSmtp], None, None]:
    _FakeSmtp.instances = []
    monkeypatch.setattr(contact_handlers.smtplib, "SMTP", _FakeSmtp)
    yield _FakeSmtp.instances


def test_handle_contact_message_job_sends_email_to_the_configured_recipient(
    db_session: Session, _fake_smtp
) -> None:
    _seed_app_settings(db_session)
    row = _create_message(db_session, name="Ana", email="ana@example.com", phone="555-1234")

    handle_contact_message_job(json.dumps({"job_id": row.id}).encode(), db_session)

    db_session.refresh(row)
    assert row.status == ContactMessageStatus.DONE
    assert row.error is None
    assert len(_fake_smtp) == 1
    smtp = _fake_smtp[0]
    assert smtp.started_tls is True
    assert smtp.login_args == ("bot@example.com", "smtp-secret")
    message = smtp.sent_messages[0]
    assert message["To"] == "owner@example.com"
    assert message["From"] == "no-reply@example.com"
    # No Reply-To pointing at the visitor — see the comment in contact_handlers.py's
    # _send_contact_email for why (a real SMTP provider silently rejects the whole send when it's
    # present). The visitor's email is in the body instead, for a manual reply.
    assert "Reply-To" not in message
    body = message.get_content()
    assert "Ana" in body
    assert "ana@example.com" in body
    assert "555-1234" in body
    assert row.message in body


def test_handle_contact_message_job_fails_cleanly_when_no_recipient_configured(
    db_session: Session, _fake_smtp
) -> None:
    _seed_app_settings(db_session, contact_recipient_email="")
    row = _create_message(db_session)

    handle_contact_message_job(json.dumps({"job_id": row.id}).encode(), db_session)

    db_session.refresh(row)
    assert row.status == ContactMessageStatus.FAILED
    assert "contact_recipient_email" in row.error
    assert len(_fake_smtp) == 0


def test_handle_contact_message_job_fails_cleanly_on_smtp_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_app_settings(db_session)
    row = _create_message(db_session)

    def _raise(*args: object, **kwargs: object) -> None:
        raise OSError("connection refused")

    monkeypatch.setattr(contact_handlers.smtplib, "SMTP", _raise)

    handle_contact_message_job(json.dumps({"job_id": row.id}).encode(), db_session)

    db_session.refresh(row)
    assert row.status == ContactMessageStatus.FAILED
    assert "connection refused" in row.error


def test_handle_contact_message_job_ignores_unknown_job_id(db_session: Session) -> None:
    handle_contact_message_job(json.dumps({"job_id": 999}).encode(), db_session)
