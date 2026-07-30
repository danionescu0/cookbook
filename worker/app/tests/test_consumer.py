import json
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import consumer
from app.database import Base
from app.models import (
    EmailJob,
    EmailJobStatus,
    ImportJob,
    ImportJobStatus,
    TranslationSyncJob,
    TranslationSyncJobStatus,
)


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


def test_on_message_delegates_to_handle_import_job_and_acks(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _create_job(db_session)
    monkeypatch.setattr(consumer, "SessionLocal", lambda: db_session)
    calls = []
    monkeypatch.setattr(consumer, "handle_import_job", lambda body, db: calls.append((body, db)))

    channel = MagicMock()
    method = MagicMock(delivery_tag=7)
    body = json.dumps({"job_id": job.id}).encode()

    consumer._on_message(channel, method, None, body)

    assert calls == [(body, db_session)]
    channel.basic_ack.assert_called_once_with(delivery_tag=7)


def test_on_message_marks_job_failed_when_handle_import_job_raises_unexpectedly(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression test: a job must never be left silently stuck at whatever status it had —
    # this is exactly how a past enum-drift bug looked (worker crashed on db.get() itself,
    # before handle_import_job's own try/except could run, and the message got acked anyway).
    job = _create_job(db_session)
    job_id = job.id  # captured before _on_message's db.close() detaches `job`
    monkeypatch.setattr(consumer, "SessionLocal", lambda: db_session)

    def _raise(body: bytes, db: Session) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(consumer, "handle_import_job", _raise)

    channel = MagicMock()
    method = MagicMock(delivery_tag=1)

    consumer._on_message(channel, method, None, json.dumps({"job_id": job_id}).encode())

    # _on_message's `finally: db.close()` expunges `job` from the session, so re-fetch it
    # rather than refresh()ing the now-detached reference.
    reloaded = db_session.get(ImportJob, job_id)
    assert reloaded is not None
    assert reloaded.status == ImportJobStatus.FAILED
    assert reloaded.error == "worker crashed while processing: boom"
    channel.basic_ack.assert_called_once_with(delivery_tag=1)


def test_on_message_acks_even_if_job_id_is_unrecoverable(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(consumer, "SessionLocal", lambda: db_session)

    def _raise(body: bytes, db: Session) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(consumer, "handle_import_job", _raise)

    channel = MagicMock()
    method = MagicMock(delivery_tag=2)

    # Malformed body: no recoverable job_id, so the failure can't be recorded anywhere —
    # must not raise, and must still ack (no infinite redelivery of an unparseable message).
    consumer._on_message(channel, method, None, b"not json")

    channel.basic_ack.assert_called_once_with(delivery_tag=2)


def test_on_translation_sync_message_delegates_and_acks(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = TranslationSyncJob(
        recipe_id=1, source_language="ro", status=TranslationSyncJobStatus.QUEUED
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    monkeypatch.setattr(consumer, "SessionLocal", lambda: db_session)
    calls = []
    monkeypatch.setattr(
        consumer, "handle_translation_sync_job", lambda body, db: calls.append((body, db))
    )

    channel = MagicMock()
    method = MagicMock(delivery_tag=9)
    body = json.dumps({"job_id": job.id, "recipe_id": 1}).encode()

    consumer._on_translation_sync_message(channel, method, None, body)

    assert calls == [(body, db_session)]
    channel.basic_ack.assert_called_once_with(delivery_tag=9)


def test_on_translation_sync_message_marks_job_failed_when_handler_raises_unexpectedly(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = TranslationSyncJob(
        recipe_id=1, source_language="ro", status=TranslationSyncJobStatus.QUEUED
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    job_id = job.id
    monkeypatch.setattr(consumer, "SessionLocal", lambda: db_session)

    def _raise(body: bytes, db: Session) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(consumer, "handle_translation_sync_job", _raise)

    channel = MagicMock()
    method = MagicMock(delivery_tag=10)

    consumer._on_translation_sync_message(
        channel, method, None, json.dumps({"job_id": job_id, "recipe_id": 1}).encode()
    )

    reloaded = db_session.get(TranslationSyncJob, job_id)
    assert reloaded is not None
    assert reloaded.status == TranslationSyncJobStatus.FAILED
    assert reloaded.error == "worker crashed while processing: boom"
    channel.basic_ack.assert_called_once_with(delivery_tag=10)


def test_on_email_message_delegates_and_acks(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = EmailJob(user_id=1, kind="verification", status=EmailJobStatus.QUEUED)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    monkeypatch.setattr(consumer, "SessionLocal", lambda: db_session)
    calls = []
    monkeypatch.setattr(consumer, "handle_email_job", lambda body, db: calls.append((body, db)))

    channel = MagicMock()
    method = MagicMock(delivery_tag=11)
    body = json.dumps({"job_id": job.id, "user_id": 1}).encode()

    consumer._on_email_message(channel, method, None, body)

    assert calls == [(body, db_session)]
    channel.basic_ack.assert_called_once_with(delivery_tag=11)


def test_on_email_message_marks_job_failed_when_handler_raises_unexpectedly(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = EmailJob(user_id=1, kind="verification", status=EmailJobStatus.QUEUED)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    job_id = job.id
    monkeypatch.setattr(consumer, "SessionLocal", lambda: db_session)

    def _raise(body: bytes, db: Session) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(consumer, "handle_email_job", _raise)

    channel = MagicMock()
    method = MagicMock(delivery_tag=12)

    consumer._on_email_message(
        channel, method, None, json.dumps({"job_id": job_id, "user_id": 1}).encode()
    )

    reloaded = db_session.get(EmailJob, job_id)
    assert reloaded is not None
    assert reloaded.status == EmailJobStatus.FAILED
    assert reloaded.error == "worker crashed while processing: boom"
    channel.basic_ack.assert_called_once_with(delivery_tag=12)
