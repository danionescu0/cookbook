from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.models.nutrition_job import NutritionJob, NutritionJobStatus
from app.models.recipe import Recipe
from app.models.recipe_translation import RecipeTranslation
from app.models.translation_sync_job import TranslationSyncJob, TranslationSyncJobStatus
from app.models.user import User
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
    assert body["slug"] == "shredded-zucchini-casserole"


def test_create_recipe_generates_a_unique_slug_on_title_collision(client: TestClient) -> None:
    category_id = _create_category(client)
    first = client.post(
        "/recipes", json={"title": "Lemon Tart", "category_id": category_id, "language": "en"}
    ).json()
    second = client.post(
        "/recipes", json={"title": "Lemon Tart", "category_id": category_id, "language": "en"}
    ).json()

    assert first["slug"] == "lemon-tart"
    assert second["slug"] == "lemon-tart-2"


def test_editing_a_recipes_title_does_not_change_its_existing_slug(client: TestClient) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/recipes", json={"title": "Lemon Tart", "category_id": category_id, "language": "en"}
    ).json()
    assert created["slug"] == "lemon-tart"

    response = client.put(
        f"/recipes/{created['id']}",
        json={"translation": {"title": "Lime Tart"}},
        params={"language": "en"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Lime Tart"
    # Slug is generated once at creation and never auto-regenerated — changing it out from under
    # a published URL would break inbound links/search rankings.
    assert body["slug"] == "lemon-tart"


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


def test_list_recipes_search_matches_title_case_insensitively(client: TestClient) -> None:
    category_id = _create_category(client)
    client.post(
        "/recipes", json={"title": "Chocolate Cake", "category_id": category_id, "language": "en"}
    )
    client.post("/recipes", json={"title": "Beef Stew", "category_id": category_id, "language": "en"})

    response = client.get("/recipes", params={"search": "CHOC", "language": "en"})

    assert response.status_code == 200
    titles = [r["title"] for r in response.json()]
    assert titles == ["Chocolate Cake"]


def test_list_recipes_search_requires_all_words_in_any_order(client: TestClient) -> None:
    category_id = _create_category(client)
    client.post(
        "/recipes", json={"title": "Soup with Chicken", "category_id": category_id, "language": "en"}
    )
    client.post("/recipes", json={"title": "Chicken Wings", "category_id": category_id, "language": "en"})
    client.post("/recipes", json={"title": "Tomato Soup", "category_id": category_id, "language": "en"})

    response = client.get("/recipes", params={"search": "chicken soup", "language": "en"})

    assert response.status_code == 200
    titles = [r["title"] for r in response.json()]
    assert titles == ["Soup with Chicken"]


def test_list_recipes_search_is_scoped_to_the_requested_language(client: TestClient) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/recipes", json={"title": "Chocolate Cake", "category_id": category_id, "language": "en"}
    ).json()
    client.put(
        f"/recipes/{created['id']}",
        json={"translation": {"title": "Prăjitură cu ciocolată"}},
        params={"language": "ro"},
    )

    en_response = client.get("/recipes", params={"search": "choc", "language": "en"})
    ro_response = client.get("/recipes", params={"search": "choc", "language": "ro"})

    assert [r["title"] for r in en_response.json()] == ["Chocolate Cake"]
    assert ro_response.json() == []


def test_list_recipes_search_ignores_diacritics_in_both_directions(client: TestClient) -> None:
    category_id = _create_category(client)
    client.post(
        "/recipes",
        json={
            "title": "Brioșe cu dovleac și glazură",
            "category_id": category_id,
            "language": "ro",
        },
    )
    client.post(
        "/recipes", json={"title": "Tocanita simpla de vinete", "category_id": category_id, "language": "ro"}
    )

    # Plain "briose" (typed without diacritics) matches the accented title...
    without_diacritics = client.get("/recipes", params={"search": "briose", "language": "ro"})
    assert [r["title"] for r in without_diacritics.json()] == ["Brioșe cu dovleac și glazură"]

    # ...and the reverse: a query typed with diacritics still matches a title that has none.
    with_diacritics = client.get("/recipes", params={"search": "tocăniță", "language": "ro"})
    assert [r["title"] for r in with_diacritics.json()] == ["Tocanita simpla de vinete"]


def test_list_recipes_search_rejects_fewer_than_three_characters(client: TestClient) -> None:
    response = client.get("/recipes", params={"search": "ca"})

    assert response.status_code == 422


def test_list_recipes_search_combines_with_category_filter(client: TestClient) -> None:
    desserts_id = _create_category(client, "Desserts")
    mains_id = _create_category(client, "Main Courses")
    client.post("/recipes", json={"title": "Chocolate Cake", "category_id": desserts_id, "language": "en"})
    client.post("/recipes", json={"title": "Chocolate Stew", "category_id": mains_id, "language": "en"})

    response = client.get(
        "/recipes", params={"search": "chocolate", "category_id": desserts_id, "language": "en"}
    )

    assert [r["title"] for r in response.json()] == ["Chocolate Cake"]


def test_list_recipes_search_treats_percent_and_underscore_literally(client: TestClient) -> None:
    category_id = _create_category(client)
    client.post(
        "/recipes", json={"title": "50% Off Pancakes", "category_id": category_id, "language": "en"}
    )
    client.post("/recipes", json={"title": "Waffles", "category_id": category_id, "language": "en"})

    response = client.get("/recipes", params={"search": "50%", "language": "en"})

    assert [r["title"] for r in response.json()] == ["50% Off Pancakes"]


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
    assert body["slug"] == "ciorba"
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


def test_delete_recipe_removes_its_image_files_from_disk(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app_settings, "images_dir", str(tmp_path))
    image_path = tmp_path / "abc123.jpg"
    image_path.write_bytes(b"fake-image-bytes")

    category_id = _create_category(client)
    created = client.post(
        "/recipes",
        json={"title": "Soup", "category_id": category_id, "images": ["/images/abc123.jpg"]},
    ).json()
    assert image_path.exists()

    response = client.delete(f"/recipes/{created['id']}")

    assert response.status_code == 204
    assert not image_path.exists()


def test_delete_recipe_without_images_does_not_error(client: TestClient) -> None:
    category_id = _create_category(client)
    created = client.post("/recipes", json={"title": "Soup", "category_id": category_id}).json()

    response = client.delete(f"/recipes/{created['id']}")

    assert response.status_code == 204


def test_owner_can_delete_their_own_recipe(client: TestClient, user_client: TestClient) -> None:
    category_id = _create_category(client)
    created = user_client.post(
        "/recipes", json={"title": "My soup", "category_id": category_id}
    ).json()

    delete_response = user_client.delete(f"/recipes/{created['id']}")
    get_response = client.get(f"/recipes/{created['id']}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


def test_admin_can_delete_someone_elses_recipe(client: TestClient, user_client: TestClient) -> None:
    category_id = _create_category(client)
    created = user_client.post(
        "/recipes", json={"title": "Their soup", "category_id": category_id}
    ).json()

    response = client.delete(f"/recipes/{created['id']}")

    assert response.status_code == 204


def test_non_owner_non_admin_cannot_delete_a_recipe(
    client: TestClient, user_client: TestClient
) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/recipes", json={"title": "Admin's soup", "category_id": category_id}
    ).json()

    response = user_client.delete(f"/recipes/{created['id']}")

    assert response.status_code == 403
    assert client.get(f"/recipes/{created['id']}").status_code == 200


def test_delete_recipe_requires_login(
    client: TestClient, unauthenticated_client: TestClient
) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/recipes", json={"title": "Soup", "category_id": category_id}
    ).json()

    response = unauthenticated_client.delete(f"/recipes/{created['id']}")

    assert response.status_code == 401


def test_update_recipe_removes_files_for_images_dropped_from_the_list(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app_settings, "images_dir", str(tmp_path))
    kept_path = tmp_path / "kept.jpg"
    removed_path = tmp_path / "removed.jpg"
    kept_path.write_bytes(b"kept")
    removed_path.write_bytes(b"removed")

    category_id = _create_category(client)
    created = client.post(
        "/recipes",
        json={
            "title": "Soup",
            "category_id": category_id,
            "images": ["/images/kept.jpg", "/images/removed.jpg"],
        },
    ).json()

    response = client.put(f"/recipes/{created['id']}", json={"images": ["/images/kept.jpg"]})

    assert response.status_code == 200
    assert not removed_path.exists()
    assert kept_path.exists()


def test_update_recipe_without_touching_images_does_not_delete_any_files(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app_settings, "images_dir", str(tmp_path))
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"photo")

    category_id = _create_category(client)
    created = client.post(
        "/recipes",
        json={"title": "Soup", "category_id": category_id, "images": ["/images/photo.jpg"]},
    ).json()

    response = client.put(f"/recipes/{created['id']}", json={"status": "unapproved"})

    assert response.status_code == 200
    assert image_path.exists()


def test_reparse_recipe_rejects_a_recipe_without_a_source_url(client: TestClient) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/recipes", json={"title": "Soup", "category_id": category_id}
    ).json()

    response = client.post(f"/recipes/{created['id']}/reparse")

    assert response.status_code == 400


def test_reparse_recipe_not_found(client: TestClient) -> None:
    response = client.post("/recipes/999/reparse")

    assert response.status_code == 404


def test_reparse_recipe_requires_admin(user_client: TestClient) -> None:
    response = user_client.post("/recipes/1/reparse")

    assert response.status_code == 403


def test_reparse_recipe_marks_job_failed_when_publish_raises(
    client: TestClient, db_session: Session, admin_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    category_id = _create_category(client)
    recipe = Recipe(
        category_id=category_id,
        source_url="https://example.com/recipe",
        owner_user_id=admin_user.id,
    )
    recipe.translations.append(RecipeTranslation(language="en", title="Soup", slug="soup"))
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(recipe)

    def _raise(job_id: int, recipe_id: int) -> None:
        raise RuntimeError("connection refused")

    monkeypatch.setattr(recipes_router, "publish_reparse_job", _raise)

    response = client.post(f"/recipes/{recipe.id}/reparse")

    assert response.status_code == 202
    job_id = response.json()["job_id"]
    job = db_session.get(recipes_router.RecipeReparseJob, job_id)
    assert job.status == recipes_router.RecipeReparseJobStatus.FAILED
    assert "connection refused" in job.error


def test_reparse_all_imported_recipes_only_queues_recipes_with_a_source_url(
    client: TestClient, db_session: Session, admin_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    category_id = _create_category(client)
    imported = Recipe(
        category_id=category_id,
        source_url="https://example.com/recipe",
        owner_user_id=admin_user.id,
    )
    imported.translations.append(RecipeTranslation(language="en", title="Imported", slug="imported"))
    manual = Recipe(category_id=category_id, owner_user_id=admin_user.id)
    manual.translations.append(RecipeTranslation(language="en", title="Manual", slug="manual"))
    db_session.add_all([imported, manual])
    db_session.commit()

    queued: list[int] = []
    monkeypatch.setattr(
        recipes_router, "publish_reparse_job", lambda job_id, recipe_id: queued.append(recipe_id)
    )

    response = client.post("/recipes/reparse-all-imported")

    assert response.status_code == 202
    assert response.json()["queued"] == 1
    assert queued == [imported.id]


def test_reparse_all_imported_recipes_requires_admin(user_client: TestClient) -> None:
    response = user_client.post("/recipes/reparse-all-imported")

    assert response.status_code == 403


def test_get_recipe_shows_reparsing_status_while_a_reparse_job_is_active(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/recipes", json={"title": "Soup", "category_id": category_id}
    ).json()
    monkeypatch.setattr(recipes_router, "publish_reparse_job", lambda *args: None)
    # Give it a source_url directly (the create endpoint never sets one) so /reparse accepts it.
    recipe = db_session.get(Recipe, created["id"])
    recipe.source_url = "https://example.com/soup"
    db_session.commit()

    client.post(f"/recipes/{created['id']}/reparse")

    response = client.get(f"/recipes/{created['id']}")

    assert response.json()["processing_status"] == "reparsing"


def test_create_recipe_requires_login(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post(
        "/recipes", json={"title": "Soup", "category_id": 1, "ingredients": ["water"]}
    )

    assert response.status_code == 401


def test_non_admin_private_submission_is_approved_immediately(
    client: TestClient, user_client: TestClient, regular_user: User
) -> None:
    # Default (no is_shared) is private — only the owner will ever see it, so there's nothing to
    # moderate.
    category_id = _create_category(client)

    response = user_client.post(
        "/recipes",
        json={"title": "Soup", "category_id": category_id, "ingredients": ["water"]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "approved"
    assert body["is_shared"] is False
    assert body["owner_user_id"] == regular_user.id


def test_non_admin_shared_submission_is_unapproved_and_tracks_owner(
    client: TestClient, user_client: TestClient, regular_user: User
) -> None:
    category_id = _create_category(client)

    response = user_client.post(
        "/recipes",
        json={
            "title": "Soup",
            "category_id": category_id,
            "ingredients": ["water"],
            "is_shared": True,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "unapproved"
    assert body["is_shared"] is True
    assert body["owner_user_id"] == regular_user.id


def test_admin_created_recipe_is_private_by_default_and_owned_by_the_admin(
    client: TestClient, admin_user: User
) -> None:
    category_id = _create_category(client)

    response = client.post(
        "/recipes", json={"title": "Soup", "category_id": category_id, "ingredients": ["water"]}
    )

    body = response.json()
    assert body["owner_user_id"] == admin_user.id
    assert body["is_shared"] is False


def test_admin_can_share_a_recipe_immediately_without_moderation(client: TestClient) -> None:
    category_id = _create_category(client)

    response = client.post(
        "/recipes",
        json={
            "title": "Soup",
            "category_id": category_id,
            "ingredients": ["water"],
            "is_shared": True,
        },
    )

    body = response.json()
    assert body["is_shared"] is True
    assert body["status"] == "approved"


def test_non_admin_can_view_their_own_submission_but_not_approve_it(
    client: TestClient, user_client: TestClient
) -> None:
    category_id = _create_category(client)
    recipe_id = user_client.post(
        "/recipes",
        json={
            "title": "Soup",
            "category_id": category_id,
            "ingredients": ["water"],
            "is_shared": True,
        },
    ).json()["id"]

    approve_response = user_client.post(f"/recipes/{recipe_id}/approve")
    assert approve_response.status_code == 403

    submissions = user_client.get("/users/me/submissions").json()
    assert [r["id"] for r in submissions] == [recipe_id]


def test_favorite_and_unfavorite_a_recipe(client: TestClient, user_client: TestClient) -> None:
    category_id = _create_category(client)
    recipe_id = client.post(
        "/recipes",
        json={
            "title": "Soup",
            "category_id": category_id,
            "ingredients": ["water"],
            "is_shared": True,
        },
    ).json()["id"]

    add_response = user_client.post(f"/recipes/{recipe_id}/favorite")
    assert add_response.status_code == 204
    assert [r["id"] for r in user_client.get("/users/me/favorites").json()] == [recipe_id]

    # Favoriting again is a no-op, not an error (idempotent).
    assert user_client.post(f"/recipes/{recipe_id}/favorite").status_code == 204

    remove_response = user_client.delete(f"/recipes/{recipe_id}/favorite")
    assert remove_response.status_code == 204
    assert user_client.get("/users/me/favorites").json() == []

    # Removing again (already absent) is also a no-op.
    assert user_client.delete(f"/recipes/{recipe_id}/favorite").status_code == 204


def test_favoriting_a_private_recipe_you_dont_own_404s(
    client: TestClient, user_client: TestClient
) -> None:
    category_id = _create_category(client)
    recipe_id = client.post(
        "/recipes", json={"title": "Soup", "category_id": category_id, "ingredients": ["water"]}
    ).json()["id"]

    response = user_client.post(f"/recipes/{recipe_id}/favorite")

    assert response.status_code == 404


def test_favorite_requires_login(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post("/recipes/1/favorite")

    assert response.status_code == 401
