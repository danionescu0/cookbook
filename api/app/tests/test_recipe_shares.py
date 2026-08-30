from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.config import settings as app_settings
from app.main import app
from app.models.ingredient import Ingredient
from app.models.recipe_ingredient_link import RecipeIngredientLink
from app.models.recipe_share import RecipeShare
from app.models.user import User


def _create_category(client: TestClient, name: str = "Desserts") -> int:
    return client.post("/categories", json={"name": name}).json()["id"]


def _create_recipe(client: TestClient, **overrides: object) -> dict:
    # Category creation is admin-only (see categories.py) — skip it when the caller already
    # passed a category_id (e.g. one created via the admin `client`, for a recipe created by a
    # non-admin `user_client`/`other_client`).
    payload: dict[str, object] = {
        "title": "Lemon Tart",
        "description": "A bright, buttery tart.",
        "ingredients": ["lemon", "butter"],
        "steps": ["Mix", "Bake"],
        "images": ["/images/original.jpg"],
    }
    if "category_id" not in overrides:
        payload["category_id"] = _create_category(client)
    payload.update(overrides)
    return client.post("/recipes", json=payload).json()


def _create_share(client: TestClient, recipe_id: int) -> dict:
    return client.post(f"/recipes/{recipe_id}/shares").json()


# A second, distinct non-admin identity — the existing `client`/`user_client` conftest fixtures
# only give one owner + one non-owner; the "two different recipients copy independently"
# multi-use test needs a third.
@pytest.fixture()
def other_user(db_session: Session) -> User:
    user = User(email="other@example.com", password_hash="x", is_admin=False, is_verified=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def other_client(unauthenticated_client: TestClient, other_user: User) -> Generator[TestClient, None, None]:
    token = create_access_token(other_user)
    with TestClient(app) as authed_client:
        authed_client.headers["Authorization"] = f"Bearer {token}"
        yield authed_client


# --- create -------------------------------------------------------------------------------


def test_create_share_returns_a_token_expiring_in_24_hours(client: TestClient) -> None:
    recipe = _create_recipe(client)

    response = client.post(f"/recipes/{recipe['id']}/shares")

    assert response.status_code == 201
    body = response.json()
    assert body["token"]
    assert body["revoked_at"] is None
    expires_at = datetime.fromisoformat(body["expires_at"])
    created_at = datetime.fromisoformat(body["created_at"])
    assert timedelta(hours=23, minutes=59) < (expires_at - created_at) < timedelta(hours=24, minutes=1)


def test_create_share_requires_login(unauthenticated_client: TestClient, client: TestClient) -> None:
    recipe = _create_recipe(client)

    response = unauthenticated_client.post(f"/recipes/{recipe['id']}/shares")

    assert response.status_code == 401


def test_non_owner_non_admin_cannot_create_a_share(client: TestClient, user_client: TestClient) -> None:
    recipe = _create_recipe(client)

    response = user_client.post(f"/recipes/{recipe['id']}/shares")

    assert response.status_code == 403


def test_admin_can_create_a_share_for_someone_elses_recipe(
    client: TestClient, user_client: TestClient
) -> None:
    # Category creation is admin-only — create it via `client`, the recipe itself via `user_client`.
    category_id = _create_category(client)
    recipe = _create_recipe(user_client, category_id=category_id)

    response = client.post(f"/recipes/{recipe['id']}/shares")

    assert response.status_code == 201


# --- lookup ---------------------------------------------------------------------------------


def test_get_share_unknown_token_404(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.get("/recipe-shares/does-not-exist")

    assert response.status_code == 404


def test_get_share_unauthenticated_returns_teaser_but_not_recipe_or_sender(
    client: TestClient, unauthenticated_client: TestClient
) -> None:
    recipe = _create_recipe(client, description="x" * 200)
    share = _create_share(client, recipe["id"])

    response = unauthenticated_client.get(f"/recipe-shares/{share['token']}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert body["teaser"]["title"] == "Lemon Tart"
    assert body["teaser"]["image"] == "/images/original.jpg"
    # Truncated to 160 chars + ellipsis, not the full 200-char description — a real teaser, not a
    # way to read the whole recipe pre-auth.
    assert body["teaser"]["description"].endswith("…")
    assert len(body["teaser"]["description"]) == 161
    assert body["recipe"] is None
    assert body["shared_by_email"] is None


def test_get_share_authenticated_returns_full_recipe_and_sender(
    client: TestClient, user_client: TestClient
) -> None:
    recipe = _create_recipe(client)
    share = _create_share(client, recipe["id"])

    response = user_client.get(f"/recipe-shares/{share['token']}")

    assert response.status_code == 200
    body = response.json()
    assert body["recipe"]["id"] == recipe["id"]
    assert body["recipe"]["ingredients"] == ["lemon", "butter"]
    assert body["shared_by_email"] == "admin@example.com"


def test_get_share_expired_hides_teaser_and_recipe(
    client: TestClient, user_client: TestClient, db_session: Session
) -> None:
    recipe = _create_recipe(client)
    share = _create_share(client, recipe["id"])
    row = db_session.query(RecipeShare).filter_by(token=share["token"]).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    response = user_client.get(f"/recipe-shares/{share['token']}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "expired"
    assert body["teaser"] is None
    assert body["recipe"] is None


def test_get_share_revoked_hides_teaser_and_recipe(
    client: TestClient, user_client: TestClient, db_session: Session
) -> None:
    recipe = _create_recipe(client)
    share = _create_share(client, recipe["id"])
    row = db_session.query(RecipeShare).filter_by(token=share["token"]).one()
    row.revoked_at = datetime.now(timezone.utc)
    db_session.commit()

    response = user_client.get(f"/recipe-shares/{share['token']}")

    assert response.status_code == 200
    assert response.json()["status"] == "revoked"


# --- copy -----------------------------------------------------------------------------------


def test_copy_share_requires_login(unauthenticated_client: TestClient, client: TestClient) -> None:
    recipe = _create_recipe(client)
    share = _create_share(client, recipe["id"])

    response = unauthenticated_client.post(f"/recipe-shares/{share['token']}/copy")

    assert response.status_code == 401


def test_copy_share_rejects_an_expired_link(
    client: TestClient, user_client: TestClient, db_session: Session
) -> None:
    recipe = _create_recipe(client)
    share = _create_share(client, recipe["id"])
    row = db_session.query(RecipeShare).filter_by(token=share["token"]).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    response = user_client.post(f"/recipe-shares/{share['token']}/copy")

    assert response.status_code == 410


def test_copy_share_rejects_a_revoked_link(
    client: TestClient, user_client: TestClient, db_session: Session
) -> None:
    recipe = _create_recipe(client)
    share = _create_share(client, recipe["id"])
    row = db_session.query(RecipeShare).filter_by(token=share["token"]).one()
    row.revoked_at = datetime.now(timezone.utc)
    db_session.commit()

    response = user_client.post(f"/recipe-shares/{share['token']}/copy")

    assert response.status_code == 410


def test_copy_share_creates_an_independent_recipe_owned_by_the_recipient(
    client: TestClient, user_client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app_settings, "images_dir", str(tmp_path))
    original_image = tmp_path / "original.jpg"
    original_image.write_bytes(b"original-bytes")

    recipe = _create_recipe(client, images=["/images/original.jpg"])
    share = _create_share(client, recipe["id"])

    response = user_client.post(f"/recipe-shares/{share['token']}/copy")

    assert response.status_code == 201
    copy = response.json()
    assert copy["id"] != recipe["id"]
    assert copy["slug"] != recipe["slug"]
    assert copy["title"] == "Lemon Tart"
    assert copy["ingredients"] == ["lemon", "butter"]
    assert copy["is_shared"] is False
    assert copy["status"] == "approved"
    assert copy["shared_from_recipe_id"] == recipe["id"]

    # Images are physically duplicated under a new filename, not the same URL — see
    # images.py's copy_images docstring for why (a shared filename would let deleting the
    # original break the copy's photo).
    assert copy["images"] != ["/images/original.jpg"]
    copied_filename = Path(copy["images"][0]).name
    assert (tmp_path / copied_filename).exists()

    # Owned by the recipient now, visible to them directly (not just via the share link) — and to
    # the admin who sent it, since an admin can see everything.
    assert user_client.get(f"/recipes/{copy['id']}").status_code == 200
    assert client.get(f"/recipes/{copy['id']}").status_code == 200

    # Deleting the *original* must not break the copy's photo.
    delete_response = client.delete(f"/recipes/{recipe['id']}")
    assert delete_response.status_code == 204
    assert (tmp_path / copied_filename).exists()
    assert user_client.get(f"/recipes/{copy['id']}").json()["images"] == copy["images"]


def test_copy_share_carries_over_nutrition_links(
    client: TestClient, user_client: TestClient, db_session: Session
) -> None:
    recipe = _create_recipe(client, ingredients=["onion"])
    onion = Ingredient(
        name="onion",
        calories_per_100g=40.0,
        protein_per_100g=1.1,
        carbs_per_100g=9.3,
        sugars_per_100g=4.2,
        fat_per_100g=0.1,
    )
    db_session.add(onion)
    db_session.commit()
    db_session.add(
        RecipeIngredientLink(
            recipe_id=recipe["id"],
            ingredient_index=0,
            ingredient_id=onion.id,
            raw_text="onion",
            estimated_grams=110.0,
            grams_source="api_lookup",
        )
    )
    db_session.commit()
    share = _create_share(client, recipe["id"])

    copy_response = user_client.post(f"/recipe-shares/{share['token']}/copy")
    copy_id = copy_response.json()["id"]

    nutrition = user_client.get(f"/recipes/{copy_id}/nutrition").json()
    assert nutrition["status"] != "not_enriched"
    assert nutrition["per_ingredient"] == [{"index": 0, "estimated_grams": 110.0, "grams_source": "api_lookup"}]


def test_copy_share_is_multi_use_two_different_recipients_each_get_their_own_copy(
    client: TestClient, user_client: TestClient, other_client: TestClient
) -> None:
    recipe = _create_recipe(client)
    share = _create_share(client, recipe["id"])

    first_copy = user_client.post(f"/recipe-shares/{share['token']}/copy").json()
    second_copy = other_client.post(f"/recipe-shares/{share['token']}/copy").json()

    assert first_copy["id"] != second_copy["id"]
    assert user_client.get(f"/recipes/{first_copy['id']}").status_code == 200
    assert other_client.get(f"/recipes/{second_copy['id']}").status_code == 200
    # Each recipient only owns their own copy, not the other's.
    assert other_client.get(f"/recipes/{first_copy['id']}").status_code == 404


# --- list / revoke ----------------------------------------------------------------------------


def test_list_shares_owner_or_admin_only(client: TestClient, user_client: TestClient) -> None:
    recipe = _create_recipe(client)
    _create_share(client, recipe["id"])

    assert len(client.get(f"/recipes/{recipe['id']}/shares").json()) == 1
    assert user_client.get(f"/recipes/{recipe['id']}/shares").status_code == 403


def test_revoke_share_makes_it_unusable(client: TestClient, user_client: TestClient) -> None:
    recipe = _create_recipe(client)
    share = _create_share(client, recipe["id"])

    revoke_response = client.delete(f"/recipes/{recipe['id']}/shares/{share['id']}")
    assert revoke_response.status_code == 204

    lookup = user_client.get(f"/recipe-shares/{share['token']}").json()
    assert lookup["status"] == "revoked"
    assert user_client.post(f"/recipe-shares/{share['token']}/copy").status_code == 410


def test_revoke_share_is_idempotent(client: TestClient) -> None:
    recipe = _create_recipe(client)
    share = _create_share(client, recipe["id"])

    assert client.delete(f"/recipes/{recipe['id']}/shares/{share['id']}").status_code == 204
    assert client.delete(f"/recipes/{recipe['id']}/shares/{share['id']}").status_code == 204


def test_non_owner_non_admin_cannot_revoke_a_share(client: TestClient, user_client: TestClient) -> None:
    recipe = _create_recipe(client)
    share = _create_share(client, recipe["id"])

    response = user_client.delete(f"/recipes/{recipe['id']}/shares/{share['id']}")

    assert response.status_code == 403
