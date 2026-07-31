import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.routers.auth as auth_router
from app.auth import create_access_token
from app.models.email_verification_token import EmailVerificationToken
from app.models.user import User

_SIGNUP_PAYLOAD = {
    "username": "newuser",
    "email": "newuser@example.com",
    "password": "supersecret1",
    "turnstile_token": "test-token",
    "terms_accepted": True,
}


def _signup(client: TestClient, monkeypatch, **overrides):
    monkeypatch.setattr(auth_router, "verify_turnstile", lambda token, secret: True)
    monkeypatch.setattr(auth_router, "publish_email_job", lambda *a: None)
    return client.post("/auth/signup", json={**_SIGNUP_PAYLOAD, **overrides})


def test_signup_creates_unverified_user(
    unauthenticated_client: TestClient, monkeypatch, db_session: Session
) -> None:
    response = _signup(unauthenticated_client, monkeypatch)

    assert response.status_code == 201
    user = db_session.query(User).filter_by(username="newuser").one()
    assert user.is_verified is False
    assert user.is_admin is False


def test_signup_records_terms_acceptance(unauthenticated_client: TestClient, monkeypatch, db_session: Session) -> None:
    response = _signup(unauthenticated_client, monkeypatch)

    assert response.status_code == 201
    user = db_session.query(User).filter_by(username="newuser").one()
    assert user.terms_accepted_at is not None
    assert user.terms_version == auth_router.TERMS_VERSION


def test_signup_rejects_terms_not_accepted(unauthenticated_client: TestClient, monkeypatch) -> None:
    response = _signup(unauthenticated_client, monkeypatch, terms_accepted=False)

    assert response.status_code == 400


def test_signup_rejects_failed_captcha(unauthenticated_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(auth_router, "verify_turnstile", lambda token, secret: False)

    response = unauthenticated_client.post("/auth/signup", json=_SIGNUP_PAYLOAD)

    assert response.status_code == 400


def test_signup_rejects_duplicate_username(
    unauthenticated_client: TestClient, monkeypatch, admin_user: User
) -> None:
    response = _signup(unauthenticated_client, monkeypatch, username=admin_user.username)

    assert response.status_code == 400


def test_signup_rejects_duplicate_email(
    unauthenticated_client: TestClient, monkeypatch, admin_user: User
) -> None:
    response = _signup(unauthenticated_client, monkeypatch, email=admin_user.email)

    assert response.status_code == 400


def test_signup_with_existing_unverified_email_resends_instead_of_erroring(
    unauthenticated_client: TestClient, monkeypatch, db_session: Session
) -> None:
    _signup(unauthenticated_client, monkeypatch)
    first_token = db_session.query(EmailVerificationToken).one().token

    response = _signup(unauthenticated_client, monkeypatch, username="a-different-username")

    assert response.status_code == 201
    assert "already exists but hasn't been verified" in response.json()["detail"]
    # Recovered the existing account rather than creating a second row under the new username.
    existing = db_session.query(User).filter_by(email="newuser@example.com").one()
    assert existing.username == "newuser"
    # A fresh token was issued alongside the original (both remain individually valid/checkable).
    tokens = db_session.query(EmailVerificationToken).all()
    assert len(tokens) == 2
    assert first_token in {t.token for t in tokens}


def test_signup_with_existing_unverified_email_does_not_change_the_password(
    unauthenticated_client: TestClient, monkeypatch, db_session: Session
) -> None:
    _signup(unauthenticated_client, monkeypatch)
    original_hash = db_session.query(User).filter_by(username="newuser").one().password_hash

    _signup(unauthenticated_client, monkeypatch, username="someone-else", password="a-totally-different-pw")

    assert db_session.query(User).filter_by(email="newuser@example.com").one().password_hash == original_hash


def test_resend_verification_requires_captcha(unauthenticated_client: TestClient, monkeypatch) -> None:
    _signup(unauthenticated_client, monkeypatch)
    monkeypatch.setattr(auth_router, "verify_turnstile", lambda token, secret: False)

    response = unauthenticated_client.post(
        "/auth/resend-verification", json={"username": "newuser", "turnstile_token": "bad"}
    )

    assert response.status_code == 400


def test_resend_verification_rejects_unknown_username(unauthenticated_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(auth_router, "verify_turnstile", lambda token, secret: True)

    response = unauthenticated_client.post(
        "/auth/resend-verification", json={"username": "nobody", "turnstile_token": "test-token"}
    )

    assert response.status_code == 404


def test_resend_verification_sends_a_new_token_for_an_unverified_user(
    unauthenticated_client: TestClient, monkeypatch, db_session: Session
) -> None:
    _signup(unauthenticated_client, monkeypatch)
    first_token = db_session.query(EmailVerificationToken).one().token
    monkeypatch.setattr(auth_router, "verify_turnstile", lambda token, secret: True)

    response = unauthenticated_client.post(
        "/auth/resend-verification", json={"username": "newuser", "turnstile_token": "test-token"}
    )

    assert response.status_code == 200
    tokens = db_session.query(EmailVerificationToken).all()
    assert len(tokens) == 2
    new_token = next(t for t in tokens if t.token != first_token)

    # The freshly issued token actually verifies the account.
    verify_response = unauthenticated_client.post("/auth/verify-email", json={"token": new_token.token})
    assert verify_response.status_code == 200


def test_resend_verification_is_a_no_op_for_an_already_verified_user(
    unauthenticated_client: TestClient, monkeypatch, db_session: Session
) -> None:
    _signup(unauthenticated_client, monkeypatch)
    token_row = db_session.query(EmailVerificationToken).one()
    unauthenticated_client.post("/auth/verify-email", json={"token": token_row.token})
    monkeypatch.setattr(auth_router, "verify_turnstile", lambda token, secret: True)

    response = unauthenticated_client.post(
        "/auth/resend-verification", json={"username": "newuser", "turnstile_token": "test-token"}
    )

    assert response.status_code == 200
    assert "already verified" in response.json()["detail"]
    # No new token was issued.
    assert db_session.query(EmailVerificationToken).count() == 1


def test_login_rejects_unverified_user(unauthenticated_client: TestClient, monkeypatch) -> None:
    _signup(unauthenticated_client, monkeypatch)

    response = unauthenticated_client.post(
        "/auth/login", json={"username": "newuser", "password": "supersecret1"}
    )

    assert response.status_code == 401


def test_verify_email_then_login_succeeds(
    unauthenticated_client: TestClient, monkeypatch, db_session: Session
) -> None:
    _signup(unauthenticated_client, monkeypatch)
    token_row = db_session.query(EmailVerificationToken).one()

    verify_response = unauthenticated_client.post("/auth/verify-email", json={"token": token_row.token})
    assert verify_response.status_code == 200

    login_response = unauthenticated_client.post(
        "/auth/login", json={"username": "newuser", "password": "supersecret1"}
    )
    assert login_response.status_code == 200
    body = login_response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"] == {
        "id": token_row.user_id,
        "username": "newuser",
        "is_admin": False,
        "is_super_admin": False,
    }


def test_login_rejects_wrong_password_once_verified(
    unauthenticated_client: TestClient, monkeypatch, db_session: Session
) -> None:
    _signup(unauthenticated_client, monkeypatch)
    token_row = db_session.query(EmailVerificationToken).one()
    unauthenticated_client.post("/auth/verify-email", json={"token": token_row.token})

    response = unauthenticated_client.post(
        "/auth/login", json={"username": "newuser", "password": "wrong"}
    )

    assert response.status_code == 401


def test_verify_email_rejects_invalid_token(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post("/auth/verify-email", json={"token": "not-a-real-token"})

    assert response.status_code == 400


def test_verify_email_rejects_reused_token(
    unauthenticated_client: TestClient, monkeypatch, db_session: Session
) -> None:
    _signup(unauthenticated_client, monkeypatch)
    token_row = db_session.query(EmailVerificationToken).one()
    unauthenticated_client.post("/auth/verify-email", json={"token": token_row.token})

    response = unauthenticated_client.post("/auth/verify-email", json={"token": token_row.token})

    assert response.status_code == 400


def test_protected_route_rejects_missing_token(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post("/categories", json={"name": "Desserts"})

    assert response.status_code == 401


def test_protected_route_rejects_malformed_token(unauthenticated_client: TestClient) -> None:
    unauthenticated_client.headers["Authorization"] = "Bearer not-a-real-token"

    response = unauthenticated_client.post("/categories", json={"name": "Desserts"})

    assert response.status_code == 401


def test_protected_route_rejects_token_for_a_different_secret(
    unauthenticated_client: TestClient,
) -> None:
    bad_token = jwt.encode({"sub": "admin"}, "a-completely-different-secret", algorithm="HS256")
    unauthenticated_client.headers["Authorization"] = f"Bearer {bad_token}"

    response = unauthenticated_client.post("/categories", json={"name": "Desserts"})

    assert response.status_code == 401


def test_protected_route_accepts_a_real_admin_token(
    unauthenticated_client: TestClient, admin_user: User
) -> None:
    token = create_access_token(admin_user)
    unauthenticated_client.headers["Authorization"] = f"Bearer {token}"

    response = unauthenticated_client.post("/categories", json={"name": "Desserts"})

    assert response.status_code == 201


def test_protected_route_rejects_a_verified_non_admin_user(
    unauthenticated_client: TestClient, regular_user: User
) -> None:
    # require_admin now checks the token's is_admin claim, not just "is this a validly signed
    # token" — a real, unexpired token for a non-admin user must still be rejected here.
    token = create_access_token(regular_user)
    unauthenticated_client.headers["Authorization"] = f"Bearer {token}"

    response = unauthenticated_client.post("/categories", json={"name": "Desserts"})

    assert response.status_code == 403


def test_public_read_routes_work_without_a_token(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.get("/categories")

    assert response.status_code == 200


def test_imports_router_is_fully_protected(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.get("/imports")

    assert response.status_code == 401
