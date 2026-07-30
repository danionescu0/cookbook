import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.ingredient_refresh_job import IngredientRefreshJob, IngredientRefreshJobStatus
from app.routers import ingredients as ingredients_router


def test_get_ingredient_refresh_status_requires_admin(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.get("/ingredients/refresh")

    assert response.status_code == 401


def test_create_ingredient_refresh_job_requires_admin(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.post("/ingredients/refresh")

    assert response.status_code == 401


def test_get_ingredient_refresh_status_rejects_a_plain_admin(admin_client: TestClient) -> None:
    # Same Settings subpage as routers/settings.py — gated to super admin, not just admin.
    response = admin_client.get("/ingredients/refresh")

    assert response.status_code == 403


def test_create_ingredient_refresh_job_rejects_a_plain_admin(admin_client: TestClient) -> None:
    response = admin_client.post("/ingredients/refresh")

    assert response.status_code == 403


def test_get_ingredient_refresh_status_never_run(client: TestClient) -> None:
    response = client.get("/ingredients/refresh")

    assert response.status_code == 200
    assert response.json() == {"status": "never_run", "error": None, "ingredients_updated": None}


def test_create_ingredient_refresh_job_queues_and_publishes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    published = []
    monkeypatch.setattr(
        ingredients_router,
        "publish_ingredient_refresh_job",
        lambda job_id: published.append(job_id),
    )

    response = client.post("/ingredients/refresh")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    assert body["error"] is None
    assert body["ingredients_updated"] is None
    assert published == [body["id"]]


def test_get_ingredient_refresh_status_returns_the_latest_job(
    client: TestClient, db_session: Session
) -> None:
    db_session.add(
        IngredientRefreshJob(status=IngredientRefreshJobStatus.DONE, ingredients_updated=3)
    )
    db_session.commit()
    db_session.add(
        IngredientRefreshJob(status=IngredientRefreshJobStatus.FAILED, error="USDA is down")
    )
    db_session.commit()

    response = client.get("/ingredients/refresh")

    assert response.status_code == 200
    assert response.json() == {
        "status": "failed",
        "error": "USDA is down",
        "ingredients_updated": None,
    }
