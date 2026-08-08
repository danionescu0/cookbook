from fastapi.testclient import TestClient


def test_get_settings_requires_admin(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.get("/settings")

    assert response.status_code == 401


def test_get_settings_rejects_a_plain_admin(admin_client: TestClient) -> None:
    # Settings holds API keys/SMTP/Turnstile secrets — a regular admin isn't enough, only a
    # super admin (users.is_super_admin) can reach it.
    response = admin_client.get("/settings")

    assert response.status_code == 403


def test_patch_settings_rejects_a_plain_admin(admin_client: TestClient) -> None:
    response = admin_client.patch("/settings", json={"default_language": "en"})

    assert response.status_code == 403


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
    assert body["calorie_ninjas_api_key_is_set"] is False
    assert body["smtp_password_is_set"] is False
    assert body["turnstile_secret_key_is_set"] is False
    assert body["smtp_use_tls"] is True
    assert body["smtp_port"] == 587
    assert body["contact_recipient_email"] == ""
    assert body["preferred_ai_provider"] == "claude"
    assert body["deepseek_api_key_is_set"] is False
    # No raw secret value ever appears in the response body.
    assert "anthropic_api_key" not in body
    assert "calorie_ninjas_api_key" not in body
    assert "smtp_password" not in body
    assert "turnstile_secret_key" not in body
    assert "deepseek_api_key" not in body


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


def test_patch_settings_updates_anthropic_api_key(client: TestClient) -> None:
    before = client.get("/settings").json()
    assert before["anthropic_api_key_is_set"] is False

    response = client.patch("/settings", json={"anthropic_api_key": "sk-ant-test-key"})

    assert response.status_code == 200
    assert response.json()["anthropic_api_key_is_set"] is True


def test_patch_settings_updates_calorie_ninjas_api_key(client: TestClient) -> None:
    before = client.get("/settings").json()
    assert before["calorie_ninjas_api_key_is_set"] is False
    assert "calorie_ninjas_api_key" not in before

    response = client.patch("/settings", json={"calorie_ninjas_api_key": "calorie-ninjas-test-key"})

    assert response.status_code == 200
    assert response.json()["calorie_ninjas_api_key_is_set"] is True


def test_patch_settings_updates_smtp_fields(client: TestClient) -> None:
    response = client.patch(
        "/settings",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_port": 465,
            "smtp_username": "bot@example.com",
            "smtp_from_address": "no-reply@example.com",
            "smtp_password": "smtp-secret",
            "smtp_use_tls": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["smtp_host"] == "smtp.example.com"
    assert body["smtp_port"] == 465
    assert body["smtp_username"] == "bot@example.com"
    assert body["smtp_from_address"] == "no-reply@example.com"
    assert body["smtp_password_is_set"] is True
    assert body["smtp_use_tls"] is False
    assert "smtp_password" not in body


def test_patch_settings_updates_turnstile_and_public_site_url(client: TestClient) -> None:
    response = client.patch(
        "/settings",
        json={
            "turnstile_site_key": "site-key",
            "turnstile_secret_key": "secret-key",
            "public_site_url": "https://cookbook.example.com",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["turnstile_site_key"] == "site-key"
    assert body["turnstile_secret_key_is_set"] is True
    assert body["public_site_url"] == "https://cookbook.example.com"
    assert "turnstile_secret_key" not in body


def test_patch_settings_blank_secret_leaves_current_value_unchanged(client: TestClient) -> None:
    client.patch("/settings", json={"anthropic_api_key": "sk-ant-test-key"})

    response = client.patch("/settings", json={"anthropic_api_key": ""})

    assert response.status_code == 200
    assert response.json()["anthropic_api_key_is_set"] is True


def test_patch_settings_partial_update_leaves_other_fields_untouched(client: TestClient) -> None:
    client.patch("/settings", json={"max_html_chars": 12_345})

    response = client.patch("/settings", json={"image_max_dimension": 900})

    assert response.status_code == 200
    body = response.json()
    assert body["max_html_chars"] == 12_345
    assert body["image_max_dimension"] == 900


def test_patch_settings_updates_backoffice_recipes_page_size(client: TestClient) -> None:
    response = client.patch("/settings", json={"backoffice_recipes_page_size": 25})

    assert response.status_code == 200
    assert response.json()["backoffice_recipes_page_size"] == 25


def test_patch_settings_rejects_non_positive_backoffice_recipes_page_size(client: TestClient) -> None:
    response = client.patch("/settings", json={"backoffice_recipes_page_size": 0})

    assert response.status_code == 422


def test_patch_settings_updates_contact_recipient_email(client: TestClient) -> None:
    response = client.patch("/settings", json={"contact_recipient_email": "owner@example.com"})

    assert response.status_code == 200
    assert response.json()["contact_recipient_email"] == "owner@example.com"


def test_patch_settings_updates_preferred_ai_provider_and_deepseek_api_key(
    client: TestClient,
) -> None:
    before = client.get("/settings").json()
    assert before["deepseek_api_key_is_set"] is False

    response = client.patch(
        "/settings",
        json={"preferred_ai_provider": "deepseek", "deepseek_api_key": "sk-deepseek-test-key"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["preferred_ai_provider"] == "deepseek"
    assert body["deepseek_api_key_is_set"] is True
    assert "deepseek_api_key" not in body


def test_patch_settings_rejects_unknown_ai_provider(client: TestClient) -> None:
    response = client.patch("/settings", json={"preferred_ai_provider": "openai"})

    assert response.status_code == 422


def test_patch_settings_blank_deepseek_api_key_leaves_current_value_unchanged(
    client: TestClient,
) -> None:
    client.patch("/settings", json={"deepseek_api_key": "sk-deepseek-test-key"})

    response = client.patch("/settings", json={"deepseek_api_key": ""})

    assert response.status_code == 200
    assert response.json()["deepseek_api_key_is_set"] is True


def test_public_settings_exposes_turnstile_site_key_without_auth(
    unauthenticated_client: TestClient, client: TestClient
) -> None:
    client.patch("/settings", json={"turnstile_site_key": "site-key"})

    response = unauthenticated_client.get("/settings/public")

    assert response.status_code == 200
    assert response.json() == {
        "turnstile_site_key": "site-key",
        "backoffice_recipes_page_size": 10,
        "max_imports_per_user": 30,
    }
