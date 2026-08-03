import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.import_job import ImportJob
from app.models.recipe import Recipe
from app.models.recipe_translation import RecipeTranslation
from app.models.user import User
from app.routers import imports as imports_router


def _create_category(client: TestClient, name: str = "Desserts") -> int:
    return client.post("/categories", json={"name": name}).json()["id"]


def test_create_import_job_stays_pending_and_does_not_publish(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    category_id = _create_category(client)
    published = []
    monkeypatch.setattr(
        imports_router,
        "publish_import_job",
        lambda job_id, job_type, source: published.append((job_id, job_type, source)),
    )

    response = client.post(
        "/imports", json={"source": "https://example.com/recipe", "category_id": category_id}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source"] == "https://example.com/recipe"
    assert body["category_id"] == category_id
    assert body["type"] == "single"
    assert body["status"] == "pending"
    assert published == []  # not published until approved


@pytest.mark.parametrize(
    ("source", "expected_type"),
    [
        ("https://www.instagram.com/p/DPa1bP5DZhP/", "instagram"),
        ("https://instagram.com/reel/DPa1bP5DZhP/", "instagram"),
        ("https://instagr.am/p/DPa1bP5DZhP/", "instagram"),
        ("https://example.com/some-recipe", "single"),
        # A different site with "instagram" somewhere in the path/host must not false-positive.
        ("https://not-instagram.com/p/DPa1bP5DZhP/", "single"),
    ],
)
def test_create_import_job_detects_instagram_urls(
    client: TestClient, source: str, expected_type: str
) -> None:
    category_id = _create_category(client)

    response = client.post("/imports", json={"source": source, "category_id": category_id})

    assert response.status_code == 201
    assert response.json()["type"] == expected_type


def test_create_import_job_rejects_unknown_category(client: TestClient) -> None:
    response = client.post(
        "/imports", json={"source": "https://example.com/recipe", "category_id": 999}
    )

    assert response.status_code == 400


def test_create_import_job_rejects_url_already_imported_as_a_recipe(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    category_id = _create_category(client)
    recipe = Recipe(
        category_id=category_id, source_url="https://example.com/recipe", owner_user_id=admin_user.id
    )
    recipe.translations.append(RecipeTranslation(language="en", title="Existing", slug="existing"))
    db_session.add(recipe)
    db_session.commit()

    response = client.post(
        "/imports", json={"source": "https://example.com/recipe", "category_id": category_id}
    )

    assert response.status_code == 409


def test_create_import_job_rejects_url_already_in_the_queue(client: TestClient) -> None:
    category_id = _create_category(client)
    client.post(
        "/imports", json={"source": "https://example.com/recipe", "category_id": category_id}
    )

    response = client.post(
        "/imports", json={"source": "https://example.com/recipe", "category_id": category_id}
    )

    assert response.status_code == 409


def test_create_import_job_allows_resubmission_after_deleting_previous_job(
    client: TestClient,
) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/imports", json={"source": "https://example.com/recipe", "category_id": category_id}
    ).json()
    client.delete(f"/imports/{created['id']}")

    response = client.post(
        "/imports", json={"source": "https://example.com/recipe", "category_id": category_id}
    )

    assert response.status_code == 201


def test_create_import_job_rejects_when_lifetime_limit_reached(
    user_client: TestClient, client: TestClient, db_session: Session, regular_user: User
) -> None:
    category_id = _create_category(client)
    client.patch("/settings", json={"max_imports_per_user": 2})
    regular_user.imported_recipes_count = 2
    db_session.commit()

    response = user_client.post(
        "/imports", json={"source": "https://example.com/recipe", "category_id": category_id}
    )

    assert response.status_code == 403
    assert "2/2" in response.json()["detail"]


def test_create_import_job_allows_up_to_but_not_over_the_limit(
    user_client: TestClient, client: TestClient, db_session: Session, regular_user: User
) -> None:
    category_id = _create_category(client)
    client.patch("/settings", json={"max_imports_per_user": 2})
    regular_user.imported_recipes_count = 1
    db_session.commit()

    response = user_client.post(
        "/imports", json={"source": "https://example.com/recipe", "category_id": category_id}
    )

    assert response.status_code == 201


def test_create_import_job_exempts_admins_from_the_limit(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    category_id = _create_category(client)
    client.patch("/settings", json={"max_imports_per_user": 1})
    admin_user.imported_recipes_count = 50
    db_session.commit()

    response = client.post(
        "/imports", json={"source": "https://example.com/recipe", "category_id": category_id}
    )

    assert response.status_code == 201


def test_import_limit_counter_is_unaffected_by_recipe_deletion(
    client: TestClient, db_session: Session, regular_user: User
) -> None:
    # The whole point of a lifetime counter: deleting the recipe an import produced must not
    # free up quota. This doesn't exercise the worker's increment (see
    # worker/app/handlers.py::_finish_import) — it just confirms nothing in the recipe-delete
    # path touches imported_recipes_count.
    category_id = _create_category(client)
    recipe = Recipe(
        category_id=category_id,
        source_url="https://example.com/recipe",
        owner_user_id=regular_user.id,
    )
    recipe.translations.append(RecipeTranslation(language="en", title="Gone", slug="gone"))
    db_session.add(recipe)
    regular_user.imported_recipes_count = 5
    db_session.commit()
    recipe_id = recipe.id

    response = client.delete(f"/recipes/{recipe_id}")
    assert response.status_code == 204

    db_session.refresh(regular_user)
    assert regular_user.imported_recipes_count == 5


def test_approve_import_job_publishes_and_marks_queued(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/imports", json={"source": "https://example.com/recipe", "category_id": category_id}
    ).json()
    published = []
    monkeypatch.setattr(
        imports_router,
        "publish_import_job",
        lambda job_id, job_type, source: published.append((job_id, job_type, source)),
    )

    response = client.post(f"/imports/{created['id']}/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert published == [(created["id"], "single", "https://example.com/recipe")]


def test_approve_import_job_marks_failed_when_publish_raises(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/imports", json={"source": "https://example.com/recipe", "category_id": category_id}
    ).json()

    def _raise(job_id: int, job_type: str, source: str) -> None:
        raise RuntimeError("connection refused")

    monkeypatch.setattr(imports_router, "publish_import_job", _raise)

    response = client.post(f"/imports/{created['id']}/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert "connection refused" in body["error"]


def test_approve_import_job_can_retry_a_failed_job(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/imports", json={"source": "https://example.com/recipe", "category_id": category_id}
    ).json()
    monkeypatch.setattr(
        imports_router,
        "publish_import_job",
        lambda *args: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    client.post(f"/imports/{created['id']}/approve")  # first attempt fails

    monkeypatch.setattr(imports_router, "publish_import_job", lambda *args: None)
    response = client.post(f"/imports/{created['id']}/approve")  # retry succeeds

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["error"] is None


def test_approve_import_job_rejects_already_queued_job(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/imports", json={"source": "https://example.com/recipe", "category_id": category_id}
    ).json()
    monkeypatch.setattr(imports_router, "publish_import_job", lambda *args: None)
    client.post(f"/imports/{created['id']}/approve")

    response = client.post(f"/imports/{created['id']}/approve")

    assert response.status_code == 400


def test_approve_import_job_not_found(client: TestClient) -> None:
    response = client.post("/imports/999/approve")

    assert response.status_code == 404


def test_delete_import_job(client: TestClient) -> None:
    category_id = _create_category(client)
    created = client.post(
        "/imports", json={"source": "https://example.com/recipe", "category_id": category_id}
    ).json()

    delete_response = client.delete(f"/imports/{created['id']}")
    get_response = client.get(f"/imports/{created['id']}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


def test_list_import_jobs(client: TestClient) -> None:
    category_id = _create_category(client)

    client.post("/imports", json={"source": "https://example.com/a", "category_id": category_id})
    client.post("/imports", json={"source": "https://example.com/b", "category_id": category_id})

    response = client.get("/imports")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_import_job_not_found(client: TestClient) -> None:
    response = client.get("/imports/999")

    assert response.status_code == 404


def test_create_import_job_shows_the_creators_username(client: TestClient) -> None:
    category_id = _create_category(client)

    response = client.post(
        "/imports", json={"source": "https://example.com/recipe", "category_id": category_id}
    )

    assert response.json()["created_by_username"] == "admin"


def test_non_admin_import_queues_and_publishes_immediately(
    client: TestClient, user_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No public-exposure review is needed for a private import — unlike an admin's own job,
    # which stays "pending" until explicitly approved.
    category_id = _create_category(client)
    published = []
    monkeypatch.setattr(
        imports_router,
        "publish_import_job",
        lambda job_id, job_type, source: published.append((job_id, job_type, source)),
    )

    response = user_client.post(
        "/imports", json={"source": "https://example.com/recipe", "category_id": category_id}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    assert body["created_by_username"] == "regular"
    assert published == [(body["id"], "single", "https://example.com/recipe")]


def test_two_different_users_can_import_the_same_url(
    client: TestClient, user_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Imports are private per owner now, so this isn't a duplicate — each gets their own copy.
    category_id = _create_category(client)
    monkeypatch.setattr(imports_router, "publish_import_job", lambda *args: None)

    first = client.post(
        "/imports", json={"source": "https://example.com/shared-recipe", "category_id": category_id}
    )
    second = user_client.post(
        "/imports", json={"source": "https://example.com/shared-recipe", "category_id": category_id}
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


def test_non_admin_only_sees_their_own_import_jobs(
    client: TestClient, user_client: TestClient
) -> None:
    category_id = _create_category(client)
    client.post("/imports", json={"source": "https://example.com/admins", "category_id": category_id})
    mine = user_client.post(
        "/imports", json={"source": "https://example.com/mine", "category_id": category_id}
    ).json()

    response = user_client.get("/imports")

    assert [job["id"] for job in response.json()] == [mine["id"]]


def test_admin_sees_every_users_import_jobs(client: TestClient, user_client: TestClient) -> None:
    category_id = _create_category(client)
    client.post("/imports", json={"source": "https://example.com/admins", "category_id": category_id})
    user_client.post(
        "/imports", json={"source": "https://example.com/mine", "category_id": category_id}
    )

    response = client.get("/imports")

    assert len(response.json()) == 2


def test_non_admin_cannot_see_or_modify_someone_elses_import_job(
    client: TestClient, user_client: TestClient
) -> None:
    category_id = _create_category(client)
    admins_job = client.post(
        "/imports", json={"source": "https://example.com/admins-only", "category_id": category_id}
    ).json()

    assert user_client.get(f"/imports/{admins_job['id']}").status_code == 404
    assert user_client.post(f"/imports/{admins_job['id']}/approve").status_code == 404
    assert user_client.delete(f"/imports/{admins_job['id']}").status_code == 404


def test_non_admin_can_retry_their_own_failed_job(
    client: TestClient, user_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    category_id = _create_category(client)
    monkeypatch.setattr(
        imports_router, "publish_import_job", lambda *args: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    created = user_client.post(
        "/imports", json={"source": "https://example.com/retry-me", "category_id": category_id}
    ).json()
    assert created["status"] == "failed"  # the immediate publish attempt failed

    monkeypatch.setattr(imports_router, "publish_import_job", lambda *args: None)
    response = user_client.post(f"/imports/{created['id']}/approve")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"


def test_admin_can_see_a_non_admins_import_job(
    client: TestClient, db_session: Session, regular_user: User
) -> None:
    # An admin isn't limited by the ownership check that applies to everyone else.
    category_id = _create_category(client)
    job = ImportJob(
        source="https://example.com/x", category_id=category_id, created_by_user_id=regular_user.id
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    response = client.get(f"/imports/{job.id}")

    assert response.status_code == 200
