import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.recipe import Recipe
from app.models.recipe_translation import RecipeTranslation
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
    client: TestClient, db_session: Session
) -> None:
    category_id = _create_category(client)
    recipe = Recipe(category_id=category_id, source_url="https://example.com/recipe")
    recipe.translations.append(RecipeTranslation(language="en", title="Existing"))
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
