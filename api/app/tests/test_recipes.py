import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.nutrition_job import NutritionJob, NutritionJobStatus
from app.models.translation_sync_job import TranslationSyncJob, TranslationSyncJobStatus
from app.routers import recipes as recipes_router


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


def test_update_recipe_edits_the_current_translation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(recipes_router, "publish_translation_sync_job", lambda *a: None)
    category_id = _create_category(client)
    created = client.post(
        "/recipes",
        json={
            "title": "Soup",
            "category_id": category_id,
            "language": "en",
            "ingredients": ["water"],
        },
    ).json()

    response = client.put(
        f"/recipes/{created['id']}",
        json={
            "images": ["/images/new.jpg"],
            "translation": {
                "title": "Better Soup",
                "description": "Now with more flavor.",
                "ingredients": ["water", "salt"],
                "steps": ["boil", "serve"],
            },
        },
        params={"language": "en"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Better Soup"
    assert body["description"] == "Now with more flavor."
    assert body["ingredients"] == ["water", "salt"]
    assert body["steps"] == ["boil", "serve"]
    assert body["images"] == ["/images/new.jpg"]
    # tips wasn't included in the update — left untouched, not wiped to [].
    assert body["tips"] == []


def test_update_recipe_translation_partial_fields_leave_others_untouched(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(recipes_router, "publish_translation_sync_job", lambda *a: None)
    category_id = _create_category(client)
    created = client.post(
        "/recipes",
        json={
            "title": "Soup",
            "category_id": category_id,
            "language": "en",
            "description": "Original description.",
            "ingredients": ["water"],
        },
    ).json()

    response = client.put(
        f"/recipes/{created['id']}",
        json={"translation": {"title": "Renamed Soup"}},
        params={"language": "en"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Renamed Soup"
    assert body["description"] == "Original description."
    assert body["ingredients"] == ["water"]


def test_update_recipe_translation_creates_a_missing_language(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(recipes_router, "publish_translation_sync_job", lambda *a: None)
    category_id = _create_category(client)
    created = client.post(
        "/recipes", json={"title": "Soup", "category_id": category_id, "language": "en"}
    ).json()

    response = client.put(
        f"/recipes/{created['id']}",
        json={"translation": {"title": "Ciorbă", "ingredients": ["apă"]}},
        params={"language": "ro"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "ro"
    assert body["title"] == "Ciorbă"
    assert sorted(body["available_languages"]) == ["en", "ro"]


def test_update_recipe_translation_edit_enqueues_translation_sync_job(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/recipes",
        json={
            "title": "Ciorbă",
            "category_id": category_id,
            "language": "ro",
            "ingredients": ["apă"],
        },
    ).json()
    published = []
    monkeypatch.setattr(
        recipes_router,
        "publish_translation_sync_job",
        lambda job_id, recipe_id: published.append((job_id, recipe_id)),
    )

    response = client.put(
        f"/recipes/{created['id']}",
        json={"translation": {"ingredients": ["apă", "sare"]}},
        params={"language": "ro"},
    )

    assert response.status_code == 200
    assert len(published) == 1
    assert published[0][1] == created["id"]


def test_update_recipe_title_only_edit_also_enqueues_translation_sync_job(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Not just ingredients — title/description/steps/tips need to stay in sync across
    # languages too, so any edited field triggers propagation.
    category_id = _create_category(client)
    created = client.post(
        "/recipes",
        json={"title": "Ciorbă", "category_id": category_id, "language": "ro", "ingredients": ["apă"]},
    ).json()
    published = []
    monkeypatch.setattr(
        recipes_router,
        "publish_translation_sync_job",
        lambda job_id, recipe_id: published.append((job_id, recipe_id)),
    )

    response = client.put(
        f"/recipes/{created['id']}",
        json={"translation": {"title": "Ciorbă de legume"}},
        params={"language": "ro"},
    )

    assert response.status_code == 200
    assert len(published) == 1


def test_update_recipe_editing_non_default_language_enqueues_sync_from_that_language(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Editing "en" (not the site default "ro") must still propagate — sourced *from* the
    # language actually edited, not always from the default.
    category_id = _create_category(client)
    created = client.post(
        "/recipes",
        json={"title": "Soup", "category_id": category_id, "language": "en", "ingredients": ["water"]},
    ).json()
    published = []
    monkeypatch.setattr(
        recipes_router,
        "publish_translation_sync_job",
        lambda job_id, recipe_id: published.append((job_id, recipe_id)),
    )

    response = client.put(
        f"/recipes/{created['id']}",
        json={"translation": {"ingredients": ["water", "salt"]}},
        params={"language": "en"},
    )

    assert response.status_code == 200
    assert len(published) == 1


def test_update_recipe_response_shows_translating_status_right_after_edit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(recipes_router, "publish_translation_sync_job", lambda *a: None)
    category_id = _create_category(client)
    created = client.post(
        "/recipes",
        json={"title": "Ciorbă", "category_id": category_id, "language": "ro", "ingredients": ["apă"]},
    ).json()
    assert created["processing_status"] is None

    response = client.put(
        f"/recipes/{created['id']}",
        json={"translation": {"ingredients": ["apă", "sare"]}},
        params={"language": "ro"},
    )

    assert response.json()["processing_status"] == "translating"


def test_list_recipes_shows_processing_status_from_active_jobs(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(recipes_router, "publish_translation_sync_job", lambda *a: None)
    category_id = _create_category(client)
    idle = client.post(
        "/recipes", json={"title": "Idle Soup", "category_id": category_id, "language": "ro"}
    ).json()
    busy = client.post(
        "/recipes", json={"title": "Busy Soup", "category_id": category_id, "language": "ro"}
    ).json()
    client.put(
        f"/recipes/{busy['id']}",
        json={"translation": {"title": "Busy Soup 2"}},
        params={"language": "ro"},
    )

    response = client.get("/recipes")

    statuses = {r["id"]: r["processing_status"] for r in response.json()}
    assert statuses[idle["id"]] is None
    assert statuses[busy["id"]] == "translating"


def test_get_recipe_shows_recalculating_nutrition_status(
    client: TestClient, db_session: Session
) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/recipes", json={"title": "Soup", "category_id": category_id, "language": "ro"}
    ).json()
    db_session.add(NutritionJob(recipe_id=created["id"], status=NutritionJobStatus.QUEUED))
    db_session.commit()

    response = client.get(f"/recipes/{created['id']}")

    assert response.json()["processing_status"] == "recalculating_nutrition"


def test_processing_status_prioritizes_translating_over_nutrition(
    client: TestClient, db_session: Session
) -> None:
    # Both active at once shouldn't normally happen mid-pipeline (nutrition only starts once
    # translating finishes), but if it ever does, "translating" is the earlier phase and should
    # win rather than flicker between the two on repeated polls.
    category_id = _create_category(client)
    created = client.post(
        "/recipes", json={"title": "Soup", "category_id": category_id, "language": "ro"}
    ).json()
    db_session.add(NutritionJob(recipe_id=created["id"], status=NutritionJobStatus.PROCESSING))
    db_session.add(
        TranslationSyncJob(
            recipe_id=created["id"], source_language="ro", status=TranslationSyncJobStatus.PROCESSING
        )
    )
    db_session.commit()

    response = client.get(f"/recipes/{created['id']}")

    assert response.json()["processing_status"] == "translating"


def test_update_recipe_without_translation_does_not_enqueue_sync_job(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    category_id = _create_category(client)
    other_category_id = _create_category(client, "Mains")
    created = client.post(
        "/recipes",
        json={"title": "Ciorbă", "category_id": category_id, "language": "ro", "ingredients": ["apă"]},
    ).json()
    published = []
    monkeypatch.setattr(
        recipes_router,
        "publish_translation_sync_job",
        lambda job_id, recipe_id: published.append((job_id, recipe_id)),
    )

    response = client.put(f"/recipes/{created['id']}", json={"category_id": other_category_id})

    assert response.status_code == 200
    assert published == []


def test_delete_recipe(client: TestClient) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/recipes", json={"title": "Soup", "category_id": category_id}
    ).json()

    delete_response = client.delete(f"/recipes/{created['id']}")
    get_response = client.get(f"/recipes/{created['id']}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404
