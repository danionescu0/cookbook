from fastapi.testclient import TestClient

from app.config import settings


def test_get_settings_requires_admin(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.get("/settings")

    assert response.status_code == 401


def test_get_settings_returns_defaults_and_masks_secrets(client: TestClient) -> None:
    response = client.get("/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["supported_languages"] == "ro,en"
    assert body["default_language"] == "ro"
    assert body["default_rate_limit_requests_per_minute"] == 6
    assert body["scrape_timeout_seconds"] == 15.0
    assert body["max_html_chars"] == 200_000
    assert body["image_max_dimension"] == 1600
    assert body["image_max_size_kb"] == 500
    assert body["admin_password_is_set"] is True
    # No raw secret value ever appears in the response body.
    assert "admin_password" not in body
    assert "anthropic_api_key" not in body


def test_patch_settings_requires_admin(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.patch("/settings", json={"default_language": "en"})

    assert response.status_code == 401


def test_patch_settings_updates_numeric_fields(client: TestClient) -> None:
    response = client.patch(
        "/settings",
        json={
            "default_rate_limit_requests_per_minute": 30,
            "scrape_timeout_seconds": 5.5,
            "max_html_chars": 50_000,
            "image_max_dimension": 800,
            "image_max_size_kb": 250,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["default_rate_limit_requests_per_minute"] == 30
    assert body["scrape_timeout_seconds"] == 5.5
    assert body["max_html_chars"] == 50_000
    assert body["image_max_dimension"] == 800
    assert body["image_max_size_kb"] == 250


def test_patch_settings_rejects_non_positive_numbers(client: TestClient) -> None:
    response = client.patch("/settings", json={"default_rate_limit_requests_per_minute": 0})

    assert response.status_code == 422


def test_patch_settings_updates_supported_languages_and_default(client: TestClient) -> None:
    response = client.patch(
        "/settings", json={"supported_languages": "ro, en, FR", "default_language": "fr"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["supported_languages"] == "ro,en,fr"
    assert body["default_language"] == "fr"


def test_patch_settings_rejects_invalid_language_code(client: TestClient) -> None:
    response = client.patch("/settings", json={"supported_languages": "ro,not-a-code"})

    assert response.status_code == 400


def test_patch_settings_rejects_empty_supported_languages(client: TestClient) -> None:
    response = client.patch("/settings", json={"supported_languages": "  , "})

    assert response.status_code == 400


def test_patch_settings_rejects_default_language_not_in_supported_list(
    client: TestClient,
) -> None:
    response = client.patch("/settings", json={"default_language": "de"})

    assert response.status_code == 400


def test_patch_settings_changes_admin_password_and_login_reflects_it(
    client: TestClient, unauthenticated_client: TestClient
) -> None:
    response = client.patch("/settings", json={"admin_password": "new-secret-password"})
    assert response.status_code == 200
    assert response.json()["admin_password_is_set"] is True

    old_login = unauthenticated_client.post(
        "/auth/login",
        json={"username": settings.admin_username, "password": settings.admin_password},
    )
    assert old_login.status_code == 401

    new_login = unauthenticated_client.post(
        "/auth/login",
        json={"username": settings.admin_username, "password": "new-secret-password"},
    )
    assert new_login.status_code == 200


def test_patch_settings_blank_secret_leaves_current_value_unchanged(
    client: TestClient, unauthenticated_client: TestClient
) -> None:
    response = client.patch("/settings", json={"admin_password": ""})
    assert response.status_code == 200

    login = unauthenticated_client.post(
        "/auth/login",
        json={"username": settings.admin_username, "password": settings.admin_password},
    )
    assert login.status_code == 200


def test_patch_settings_updates_anthropic_api_key(client: TestClient) -> None:
    before = client.get("/settings").json()
    assert before["anthropic_api_key_is_set"] is False

    response = client.patch("/settings", json={"anthropic_api_key": "sk-ant-test-key"})

    assert response.status_code == 200
    assert response.json()["anthropic_api_key_is_set"] is True


def test_patch_settings_partial_update_leaves_other_fields_untouched(client: TestClient) -> None:
    client.patch("/settings", json={"max_html_chars": 12_345})

    response = client.patch("/settings", json={"image_max_dimension": 900})

    assert response.status_code == 200
    body = response.json()
    assert body["max_html_chars"] == 12_345
    assert body["image_max_dimension"] == 900
