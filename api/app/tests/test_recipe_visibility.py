from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.recipe import Recipe
from app.models.recipe_translation import RecipeTranslation
from app.models.user import User


def _create_category(client: TestClient, name: str = "Desserts") -> int:
    return client.post("/categories", json={"name": name}).json()["id"]


def _create_recipe(client: TestClient, category_id: int, **overrides) -> dict:
    payload = {"title": "Soup", "category_id": category_id, "ingredients": ["water"]}
    payload.update(overrides)
    return client.post("/recipes", json=payload).json()


class TestListVisibility:
    def test_anonymous_only_sees_shared_and_approved_recipes(
        self, client: TestClient, unauthenticated_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        _create_recipe(client, category_id, title="Private admin recipe")
        shared = _create_recipe(client, category_id, title="Shared admin recipe", is_shared=True)

        response = unauthenticated_client.get("/recipes")

        assert response.status_code == 200
        titles = [r["title"] for r in response.json()]
        assert titles == ["Shared admin recipe"]
        assert response.json()[0]["id"] == shared["id"]

    def test_regular_user_sees_own_recipes_plus_others_shared_ones(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        mine = _create_recipe(user_client, category_id, title="My private recipe")
        _create_recipe(client, category_id, title="Someone else's private recipe")
        shared = _create_recipe(client, category_id, title="Someone else's shared recipe", is_shared=True)

        response = user_client.get("/recipes")

        titles = {r["title"] for r in response.json()}
        assert titles == {"My private recipe", "Someone else's shared recipe"}
        assert {r["id"] for r in response.json()} == {mine["id"], shared["id"]}

    def test_admin_sees_everything_regardless_of_owner_or_sharing(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        _create_recipe(user_client, category_id, title="A private user recipe")
        _create_recipe(client, category_id, title="A private admin recipe")

        response = client.get("/recipes")

        titles = {r["title"] for r in response.json()}
        assert {"A private user recipe", "A private admin recipe"}.issubset(titles)


class TestDetailVisibility:
    def test_anonymous_gets_404_for_a_private_recipe(
        self, client: TestClient, unauthenticated_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        recipe = _create_recipe(client, category_id)

        response = unauthenticated_client.get(f"/recipes/{recipe['id']}")

        assert response.status_code == 404

    def test_non_owner_gets_404_for_a_private_recipe(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        recipe = _create_recipe(client, category_id)

        response = user_client.get(f"/recipes/{recipe['id']}")

        assert response.status_code == 404

    def test_owner_can_always_see_their_own_recipe(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        recipe = _create_recipe(user_client, category_id)

        response = user_client.get(f"/recipes/{recipe['id']}")

        assert response.status_code == 200

    def test_anonymous_can_see_a_shared_approved_recipe(
        self, client: TestClient, unauthenticated_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        recipe = _create_recipe(client, category_id, is_shared=True)

        response = unauthenticated_client.get(f"/recipes/{recipe['id']}")

        assert response.status_code == 200

    def test_anonymous_cannot_see_a_shared_but_not_yet_approved_recipe(
        self, client: TestClient, user_client: TestClient, unauthenticated_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        recipe = _create_recipe(user_client, category_id, is_shared=True)
        assert recipe["status"] == "unapproved"

        response = unauthenticated_client.get(f"/recipes/{recipe['id']}")

        assert response.status_code == 404


class TestShareEndpoint:
    def test_owner_can_share_their_own_private_recipe(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        recipe = _create_recipe(user_client, category_id)

        response = user_client.patch(f"/recipes/{recipe['id']}/share", json={"is_shared": True})

        assert response.status_code == 200
        body = response.json()
        assert body["is_shared"] is True
        # A non-admin's share request always goes through moderation, even though the recipe was
        # already (privately) approved.
        assert body["status"] == "unapproved"

    def test_admin_sharing_their_own_recipe_skips_moderation(self, client: TestClient) -> None:
        category_id = _create_category(client)
        recipe = _create_recipe(client, category_id)

        response = client.patch(f"/recipes/{recipe['id']}/share", json={"is_shared": True})

        body = response.json()
        assert body["is_shared"] is True
        assert body["status"] == "approved"

    def test_admin_can_toggle_sharing_on_someone_elses_recipe(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        recipe = _create_recipe(user_client, category_id)

        response = client.patch(f"/recipes/{recipe['id']}/share", json={"is_shared": True})

        assert response.status_code == 200
        assert response.json()["is_shared"] is True

    def test_non_owner_non_admin_cannot_change_sharing(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        recipe = _create_recipe(client, category_id)

        response = user_client.patch(f"/recipes/{recipe['id']}/share", json={"is_shared": True})

        assert response.status_code == 403

    def test_unsharing_never_needs_moderation(self, client: TestClient, user_client: TestClient) -> None:
        category_id = _create_category(client)
        recipe = _create_recipe(user_client, category_id, is_shared=True)
        assert recipe["status"] == "unapproved"

        response = user_client.patch(f"/recipes/{recipe['id']}/share", json={"is_shared": False})

        assert response.status_code == 200
        assert response.json()["is_shared"] is False

    def test_imported_recipes_cannot_be_shared(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        category_id = _create_category(client)
        recipe = Recipe(
            category_id=category_id,
            source_url="https://example.com/imported-recipe",
            owner_user_id=admin_user.id,
        )
        recipe.translations.append(RecipeTranslation(language="en", title="Imported"))
        db_session.add(recipe)
        db_session.commit()
        db_session.refresh(recipe)

        response = client.patch(f"/recipes/{recipe.id}/share", json={"is_shared": True})

        assert response.status_code == 400
