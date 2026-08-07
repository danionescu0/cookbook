from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.routers.contact as contact_router
from app.models.contact_message import ContactMessage, ContactMessageStatus

_LONG_ENOUGH_MESSAGE = "x" * 50


def _mock_captcha(monkeypatch, *, valid: bool) -> None:
    monkeypatch.setattr(contact_router, "verify_turnstile", lambda token, secret: valid)


def _mock_publish(monkeypatch, *, raises: bool = False) -> list:
    published: list = []

    def _publish(job_id: int) -> None:
        if raises:
            raise RuntimeError("connection refused")
        published.append(job_id)

    monkeypatch.setattr(contact_router, "publish_contact_message_job", _publish)
    return published


def test_create_contact_message_requires_captcha_when_anonymous(
    unauthenticated_client: TestClient, monkeypatch
) -> None:
    _mock_publish(monkeypatch)

    response = unauthenticated_client.post(
        "/contact",
        json={"name": "Ana", "email": "ana@example.com", "message": _LONG_ENOUGH_MESSAGE},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "CAPTCHA verification failed"


def test_create_contact_message_rejects_an_invalid_captcha(
    unauthenticated_client: TestClient, monkeypatch
) -> None:
    _mock_captcha(monkeypatch, valid=False)
    _mock_publish(monkeypatch)

    response = unauthenticated_client.post(
        "/contact",
        json={
            "name": "Ana",
            "email": "ana@example.com",
            "message": _LONG_ENOUGH_MESSAGE,
            "turnstile_token": "bad-token",
        },
    )

    assert response.status_code == 400


def test_create_contact_message_succeeds_anonymous_with_a_valid_captcha(
    unauthenticated_client: TestClient, monkeypatch, db_session: Session
) -> None:
    _mock_captcha(monkeypatch, valid=True)
    published = _mock_publish(monkeypatch)

    response = unauthenticated_client.post(
        "/contact",
        json={
            "name": "Ana",
            "email": "ana@example.com",
            "message": _LONG_ENOUGH_MESSAGE,
            "turnstile_token": "good-token",
        },
    )

    assert response.status_code == 201
    message = db_session.get(ContactMessage, response.json()["id"])
    assert message is not None
    assert message.name == "Ana"
    assert message.email == "ana@example.com"
    assert message.submitted_by_user_id is None
    assert message.status == ContactMessageStatus.QUEUED
    assert published == [message.id]


def test_create_contact_message_skips_captcha_when_logged_in(
    user_client: TestClient, monkeypatch, db_session: Session, regular_user
) -> None:
    # No turnstile_token in the payload at all — an authenticated caller doesn't need one.
    _mock_publish(monkeypatch)

    response = user_client.post(
        "/contact", json={"name": "Ana", "phone": "555-1234", "message": _LONG_ENOUGH_MESSAGE}
    )

    assert response.status_code == 201
    message = db_session.get(ContactMessage, response.json()["id"])
    assert message is not None
    assert message.submitted_by_user_id == regular_user.id


def test_create_contact_message_requires_email_or_phone(
    user_client: TestClient, monkeypatch
) -> None:
    _mock_publish(monkeypatch)

    response = user_client.post("/contact", json={"name": "Ana", "message": _LONG_ENOUGH_MESSAGE})

    assert response.status_code == 422


def test_create_contact_message_succeeds_with_only_phone(
    user_client: TestClient, monkeypatch, db_session: Session
) -> None:
    _mock_publish(monkeypatch)

    response = user_client.post(
        "/contact", json={"name": "Ana", "phone": "555-1234", "message": _LONG_ENOUGH_MESSAGE}
    )

    assert response.status_code == 201
    message = db_session.get(ContactMessage, response.json()["id"])
    assert message.email is None
    assert message.phone == "555-1234"


def test_create_contact_message_succeeds_with_only_email(
    user_client: TestClient, monkeypatch, db_session: Session
) -> None:
    _mock_publish(monkeypatch)

    response = user_client.post(
        "/contact", json={"name": "Ana", "email": "ana@example.com", "message": _LONG_ENOUGH_MESSAGE}
    )

    assert response.status_code == 201
    message = db_session.get(ContactMessage, response.json()["id"])
    assert message.phone is None
    assert message.email == "ana@example.com"


def test_create_contact_message_rejects_a_too_short_message(
    user_client: TestClient, monkeypatch
) -> None:
    _mock_publish(monkeypatch)

    response = user_client.post(
        "/contact", json={"name": "Ana", "email": "ana@example.com", "message": "too short"}
    )

    assert response.status_code == 422


def test_create_contact_message_rejects_a_blank_name(user_client: TestClient, monkeypatch) -> None:
    _mock_publish(monkeypatch)

    response = user_client.post(
        "/contact", json={"name": "", "email": "ana@example.com", "message": _LONG_ENOUGH_MESSAGE}
    )

    assert response.status_code == 422


def test_create_contact_message_marks_failed_when_publish_raises(
    user_client: TestClient, monkeypatch, db_session: Session
) -> None:
    _mock_publish(monkeypatch, raises=True)

    response = user_client.post(
        "/contact", json={"name": "Ana", "email": "ana@example.com", "message": _LONG_ENOUGH_MESSAGE}
    )

    # The submission itself still succeeds — a broken queue publish must not turn a durably
    # recorded message into a user-facing error, matching every other job type's pattern.
    assert response.status_code == 201
    message = db_session.get(ContactMessage, response.json()["id"])
    assert message.status == ContactMessageStatus.FAILED
    assert "failed to publish to queue" in message.error
