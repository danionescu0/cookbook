import json
from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import email_handlers
from app.database import Base
from app.email_handlers import handle_email_job
from app.models import AppSettings, EmailJob, EmailJobStatus, EmailVerificationToken, User


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
        )
    )
    db.commit()


def _create_user(db: Session, email: str | None = "someone@example.com") -> User:
    user = User(username="someone", email=email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_token(db: Session, user_id: int, used: bool = False) -> EmailVerificationToken:
    token = EmailVerificationToken(
        user_id=user_id,
        token="a-token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        used_at=datetime.now(timezone.utc) if used else None,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def _create_job(db: Session, user_id: int, kind: str = "verification") -> EmailJob:
    job = EmailJob(user_id=user_id, kind=kind, status=EmailJobStatus.QUEUED)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


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
    monkeypatch.setattr(email_handlers.smtplib, "SMTP", _FakeSmtp)
    yield _FakeSmtp.instances


def test_handle_email_job_sends_verification_email(db_session: Session, _fake_smtp) -> None:
    _seed_app_settings(db_session)
    user = _create_user(db_session)
    token = _create_token(db_session, user.id)
    job = _create_job(db_session, user.id)

    handle_email_job(json.dumps({"job_id": job.id, "user_id": user.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == EmailJobStatus.DONE
    assert job.error is None
    assert len(_fake_smtp) == 1
    smtp = _fake_smtp[0]
    assert smtp.host == "smtp.example.com"
    assert smtp.started_tls is True
    assert smtp.login_args == ("bot@example.com", "smtp-secret")
    assert len(smtp.sent_messages) == 1
    body = smtp.sent_messages[0].get_content()
    assert f"https://cookbook.example.com/verify-email?token={token.token}" in body


def test_handle_email_job_skips_login_when_no_smtp_username(
    db_session: Session, _fake_smtp
) -> None:
    _seed_app_settings(db_session)
    row = db_session.get(AppSettings, 1)
    row.smtp_username = ""
    db_session.commit()
    user = _create_user(db_session)
    _create_token(db_session, user.id)
    job = _create_job(db_session, user.id)

    handle_email_job(json.dumps({"job_id": job.id, "user_id": user.id}).encode(), db_session)

    assert _fake_smtp[0].login_args is None


def test_handle_email_job_fails_when_user_has_no_email(db_session: Session) -> None:
    _seed_app_settings(db_session)
    user = _create_user(db_session, email=None)
    job = _create_job(db_session, user.id)

    handle_email_job(json.dumps({"job_id": job.id, "user_id": user.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == EmailJobStatus.FAILED
    assert "no email" in job.error


def test_handle_email_job_fails_when_no_unused_token_exists(db_session: Session) -> None:
    _seed_app_settings(db_session)
    user = _create_user(db_session)
    _create_token(db_session, user.id, used=True)
    job = _create_job(db_session, user.id)

    handle_email_job(json.dumps({"job_id": job.id, "user_id": user.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == EmailJobStatus.FAILED
    assert "no unused verification token" in job.error


def test_handle_email_job_fails_for_unknown_kind(db_session: Session) -> None:
    _seed_app_settings(db_session)
    user = _create_user(db_session)
    _create_token(db_session, user.id)
    job = _create_job(db_session, user.id, kind="password_reset")

    handle_email_job(json.dumps({"job_id": job.id, "user_id": user.id}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == EmailJobStatus.FAILED
    assert "unknown email job kind" in job.error


def test_handle_email_job_fails_when_user_not_found(db_session: Session) -> None:
    job = EmailJob(user_id=999, kind="verification", status=EmailJobStatus.QUEUED)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    handle_email_job(json.dumps({"job_id": job.id, "user_id": 999}).encode(), db_session)

    db_session.refresh(job)
    assert job.status == EmailJobStatus.FAILED
    assert job.error == "user not found"


def test_handle_email_job_ignores_unknown_job_id(db_session: Session) -> None:
    handle_email_job(json.dumps({"job_id": 999, "user_id": 1}).encode(), db_session)
