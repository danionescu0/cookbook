from fastapi.testclient import TestClient


def _create_category(client: TestClient, name: str = "Desserts") -> int:
    return client.post("/categories", json={"name": name}).json()["id"]


def test_create_recipe_defaults_to_approved(client: TestClient) -> None:
    category_id = _create_category(client)

    response = client.post(
        "/recipes",
        json={
            "title": "Shredded Zucchini Casserole",
            "description": "A simple weeknight bake.",
            "ingredients": ["zucchini", "eggs", "cheese"],
            "steps": ["Grate zucchini", "Mix", "Bake"],
            "tips": ["Squeeze out excess water from the zucchini"],
            "images": [],
            "language": "en",
            "category_id": category_id,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Shredded Zucchini Casserole"
    assert body["status"] == "approved"
    assert body["category_id"] == category_id


def test_create_recipe_defaults_language_to_site_default(client: TestClient) -> None:
    category_id = _create_category(client)

    response = client.post("/recipes", json={"title": "Ciorbă", "category_id": category_id})

    assert response.status_code == 201
    body = response.json()
    assert body["language"] == "ro"
    assert body["available_languages"] == ["ro"]


def test_create_recipe_rejects_url_as_title(client: TestClient) -> None:
    category_id = _create_category(client)

    response = client.post(
        "/recipes",
        json={"title": "https://example.com/some-recipe", "category_id": category_id},
    )

    assert response.status_code == 400
    assert "Import from URL" in response.json()["detail"]


def test_create_recipe_rejects_url_in_ingredients(client: TestClient) -> None:
    category_id = _create_category(client)

    response = client.post(
        "/recipes",
        json={
            "title": "Soup",
            "category_id": category_id,
            "ingredients": ["salt", "https://example.com/some-recipe"],
        },
    )

    assert response.status_code == 400
    assert "Import from URL" in response.json()["detail"]


def test_create_recipe_allows_normal_text_containing_the_word_http(client: TestClient) -> None:
    category_id = _create_category(client)

    response = client.post(
        "/recipes",
        json={
            "title": "Soup",
            "category_id": category_id,
            "description": "See the food blog at example.com for background (not a URL field).",
        },
    )

    assert response.status_code == 201


def test_create_recipe_rejects_unsupported_language(client: TestClient) -> None:
    category_id = _create_category(client)

    response = client.post(
        "/recipes",
        json={"title": "Soupe", "category_id": category_id, "language": "fr"},
    )

    assert response.status_code == 400


def test_get_recipe_falls_back_to_default_language_when_missing(client: TestClient) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/recipes",
        json={"title": "Soup", "category_id": category_id, "language": "en"},
    ).json()

    response = client.get(f"/recipes/{created['id']}", params={"language": "ro"})

    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "en"  # fell back — no "ro" translation exists
    assert body["title"] == "Soup"
    assert body["available_languages"] == ["en"]


def test_get_recipe_returns_requested_language_when_available(client: TestClient) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/recipes",
        json={"title": "Soup", "category_id": category_id, "language": "en"},
    ).json()

    response = client.get(f"/recipes/{created['id']}", params={"language": "en"})

    assert response.status_code == 200
    assert response.json()["language"] == "en"


def test_create_recipe_rejects_unknown_category(client: TestClient) -> None:
    response = client.post(
        "/recipes",
        json={"title": "Ghost Recipe", "category_id": 999},
    )

    assert response.status_code == 400


def test_list_recipes_filtered_by_category(client: TestClient) -> None:
    desserts_id = _create_category(client, "Desserts")
    mains_id = _create_category(client, "Main Courses")
    client.post("/recipes", json={"title": "Cake", "category_id": desserts_id})
    client.post("/recipes", json={"title": "Stew", "category_id": mains_id})

    response = client.get("/recipes", params={"category_id": desserts_id})

    assert response.status_code == 200
    titles = [r["title"] for r in response.json()]
    assert titles == ["Cake"]


def test_update_recipe_status(client: TestClient) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/recipes", json={"title": "Imported Soup", "category_id": category_id}
    ).json()

    response = client.put(f"/recipes/{created['id']}", json={"status": "unapproved"})

    assert response.status_code == 200
    assert response.json()["status"] == "unapproved"


def test_approve_recipe_sets_status_and_approved_at(client: TestClient) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/recipes", json={"title": "Imported Soup", "category_id": category_id}
    ).json()
    client.put(f"/recipes/{created['id']}", json={"status": "unapproved"})

    response = client.post(f"/recipes/{created['id']}/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["approved_at"] is not None


def test_approve_recipe_not_found(client: TestClient) -> None:
    response = client.post("/recipes/999/approve")

    assert response.status_code == 404


def test_delete_recipe(client: TestClient) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/recipes", json={"title": "Soup", "category_id": category_id}
    ).json()

    delete_response = client.delete(f"/recipes/{created['id']}")
    get_response = client.get(f"/recipes/{created['id']}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404
