import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models.user import User


def test_read_profile(client: TestClient) -> None:
    response = client.get("/users/me")

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert body["is_admin"] is True
    assert body["is_super_admin"] is True


def test_read_profile_for_a_plain_admin_shows_not_super_admin(admin_client: TestClient) -> None:
    response = admin_client.get("/users/me")

    assert response.status_code == 200
    body = response.json()
    assert body["is_admin"] is True
    assert body["is_super_admin"] is False


def test_read_profile_exposes_lifetime_import_count(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    admin_user.imported_recipes_count = 7
    db_session.commit()

    response = client.get("/users/me")

    assert response.status_code == 200
    assert response.json()["imported_recipes_count"] == 7


def test_read_profile_requires_login(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.get("/users/me")

    assert response.status_code == 401


def test_change_password_succeeds_and_old_password_stops_working(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    user = User(
        username="pwtest",
        email="pwtest@example.com",
        password_hash=bcrypt.hashpw(b"old-password", bcrypt.gensalt()).decode(),
        is_admin=False,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()

    unauthenticated_client.headers["Authorization"] = f"Bearer {create_access_token(user)}"

    response = unauthenticated_client.patch(
        "/users/me/password", json={"current_password": "old-password", "new_password": "new-password"}
    )
    assert response.status_code == 204

    old_login = unauthenticated_client.post(
        "/auth/login", json={"username": "pwtest", "password": "old-password"}
    )
    assert old_login.status_code == 401

    new_login = unauthenticated_client.post(
        "/auth/login", json={"username": "pwtest", "password": "new-password"}
    )
    assert new_login.status_code == 200


def test_change_password_rejects_wrong_current_password(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    user = User(
        username="pwtest2",
        email="pwtest2@example.com",
        password_hash=bcrypt.hashpw(b"old-password", bcrypt.gensalt()).decode(),
        is_admin=False,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()

    unauthenticated_client.headers["Authorization"] = f"Bearer {create_access_token(user)}"

    response = unauthenticated_client.patch(
        "/users/me/password", json={"current_password": "wrong", "new_password": "new-password"}
    )

    assert response.status_code == 401
