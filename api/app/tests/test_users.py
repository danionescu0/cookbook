import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models.category import Category
from app.models.recipe import Recipe
from app.models.user import User


def test_read_profile(client: TestClient) -> None:
    response = client.get("/users/me")

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "admin@example.com"
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


def test_list_users_requires_login(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.get("/users")

    assert response.status_code == 401


def test_list_users_rejects_a_plain_admin(admin_client: TestClient) -> None:
    # Same stricter tier as Settings — see users.is_super_admin.
    response = admin_client.get("/users")

    assert response.status_code == 403


def test_list_users_reports_recipe_counts_per_user(
    client: TestClient, db_session: Session, regular_user: User
) -> None:
    category = Category(name="Desserts", slug="desserts")
    db_session.add(category)
    db_session.commit()

    # One manually-added shared recipe, one manually-added private recipe, one imported recipe
    # (source_url set — imports never get is_shared, see recipe.py) — owned=3, shared=1,
    # imported (lifetime counter) set independently below.
    db_session.add_all(
        [
            Recipe(category_id=category.id, owner_user_id=regular_user.id, is_shared=True),
            Recipe(category_id=category.id, owner_user_id=regular_user.id, is_shared=False),
            Recipe(
                category_id=category.id,
                owner_user_id=regular_user.id,
                is_shared=False,
                source_url="https://example.com/imported",
            ),
        ]
    )
    regular_user.imported_recipes_count = 5
    db_session.commit()

    response = client.get("/users")

    assert response.status_code == 200
    entry = next(row for row in response.json() if row["email"] == "regular@example.com")
    assert entry["owned_recipes_count"] == 3
    assert entry["shared_recipes_count"] == 1
    assert entry["imported_recipes_count"] == 5
    assert entry["is_verified"] is True
    assert entry["last_login_at"] is None


def test_list_users_includes_a_user_with_no_recipes(client: TestClient, regular_user: User) -> None:
    response = client.get("/users")

    assert response.status_code == 200
    entry = next(row for row in response.json() if row["email"] == "regular@example.com")
    assert entry["owned_recipes_count"] == 0
    assert entry["shared_recipes_count"] == 0


def test_login_stamps_last_login_at(unauthenticated_client: TestClient, db_session: Session) -> None:
    user = User(
        email="loginstamp@example.com",
        password_hash=bcrypt.hashpw(b"a-password", bcrypt.gensalt()).decode(),
        is_admin=False,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    assert user.last_login_at is None

    response = unauthenticated_client.post(
        "/auth/login", json={"email": "loginstamp@example.com", "password": "a-password"}
    )

    assert response.status_code == 200
    db_session.refresh(user)
    assert user.last_login_at is not None


def test_change_password_succeeds_and_old_password_stops_working(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    user = User(
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
        "/auth/login", json={"email": "pwtest@example.com", "password": "old-password"}
    )
    assert old_login.status_code == 401

    new_login = unauthenticated_client.post(
        "/auth/login", json={"email": "pwtest@example.com", "password": "new-password"}
    )
    assert new_login.status_code == 200


def test_change_password_rejects_wrong_current_password(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    user = User(
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
