import jwt
from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.config import settings


def test_login_succeeds_with_correct_credentials(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post(
        "/auth/login",
        json={"username": settings.admin_username, "password": settings.admin_password},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"


def test_login_rejects_wrong_password(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post(
        "/auth/login",
        json={"username": settings.admin_username, "password": "wrong"},
    )

    assert response.status_code == 401


def test_login_rejects_wrong_username(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post(
        "/auth/login",
        json={"username": "nobody", "password": settings.admin_password},
    )

    assert response.status_code == 401


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


def test_protected_route_accepts_a_real_token(unauthenticated_client: TestClient) -> None:
    token = create_access_token(settings.admin_username)
    unauthenticated_client.headers["Authorization"] = f"Bearer {token}"

    response = unauthenticated_client.post("/categories", json={"name": "Desserts"})

    assert response.status_code == 201


def test_public_read_routes_work_without_a_token(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.get("/categories")

    assert response.status_code == 200


def test_imports_router_is_fully_protected(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.get("/imports")

    assert response.status_code == 401
