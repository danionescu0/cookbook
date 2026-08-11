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
        recipe.translations.append(RecipeTranslation(language="en", title="Imported", slug="imported"))
        db_session.add(recipe)
        db_session.commit()
        db_session.refresh(recipe)

        response = client.patch(f"/recipes/{recipe.id}/share", json={"is_shared": True})

        assert response.status_code == 400


class TestCategoryEndpoint:
    def test_owner_can_change_their_own_recipes_category(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        category_id = _create_category(client, "Desserts")
        other_category_id = _create_category(client, "Main courses")
        recipe = _create_recipe(user_client, category_id)

        response = user_client.patch(
            f"/recipes/{recipe['id']}/category", json={"category_id": other_category_id}
        )

        assert response.status_code == 200
        assert response.json()["category_id"] == other_category_id

    def test_owner_can_change_an_imported_recipes_category(
        self,
        client: TestClient,
        user_client: TestClient,
        db_session: Session,
        regular_user: User,
    ) -> None:
        category_id = _create_category(client, "Desserts")
        other_category_id = _create_category(client, "Main courses")
        recipe = Recipe(
            category_id=category_id,
            source_url="https://example.com/imported-recipe",
            owner_user_id=regular_user.id,
        )
        recipe.translations.append(RecipeTranslation(language="en", title="Imported", slug="imported"))
        db_session.add(recipe)
        db_session.commit()
        db_session.refresh(recipe)

        response = user_client.patch(
            f"/recipes/{recipe.id}/category", json={"category_id": other_category_id}
        )

        assert response.status_code == 200
        assert response.json()["category_id"] == other_category_id

    def test_admin_can_change_someone_elses_recipe_category(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        category_id = _create_category(client, "Desserts")
        other_category_id = _create_category(client, "Main courses")
        recipe = _create_recipe(user_client, category_id)

        response = client.patch(
            f"/recipes/{recipe['id']}/category", json={"category_id": other_category_id}
        )

        assert response.status_code == 200
        assert response.json()["category_id"] == other_category_id

    def test_non_owner_non_admin_cannot_change_category(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        category_id = _create_category(client, "Desserts")
        other_category_id = _create_category(client, "Main courses")
        recipe = _create_recipe(client, category_id)

        response = user_client.patch(
            f"/recipes/{recipe['id']}/category", json={"category_id": other_category_id}
        )

        assert response.status_code == 403

    def test_change_category_requires_login(
        self, client: TestClient, unauthenticated_client: TestClient
    ) -> None:
        category_id = _create_category(client, "Desserts")
        recipe = _create_recipe(client, category_id)

        response = unauthenticated_client.patch(
            f"/recipes/{recipe['id']}/category", json={"category_id": category_id}
        )

        assert response.status_code == 401

    def test_change_category_rejects_an_unknown_category(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        category_id = _create_category(client, "Desserts")
        recipe = _create_recipe(user_client, category_id)

        response = user_client.patch(f"/recipes/{recipe['id']}/category", json={"category_id": 999999})

        assert response.status_code == 400


class TestUpdateEndpoint:
    def test_owner_can_edit_their_own_recipe(self, client: TestClient, user_client: TestClient) -> None:
        category_id = _create_category(client)
        recipe = _create_recipe(user_client, category_id)

        response = user_client.put(
            f"/recipes/{recipe['id']}",
            json={"translation": {"title": "Better soup"}},
            params={"language": "en"},
        )

        assert response.status_code == 200
        assert response.json()["title"] == "Better soup"

    def test_non_owner_non_admin_cannot_edit(self, client: TestClient, user_client: TestClient) -> None:
        category_id = _create_category(client)
        recipe = _create_recipe(client, category_id)

        response = user_client.put(
            f"/recipes/{recipe['id']}", json={"translation": {"title": "Hijacked"}}
        )

        assert response.status_code == 403

    def test_non_admin_cannot_change_status_via_update(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        recipe = _create_recipe(user_client, category_id)

        response = user_client.put(f"/recipes/{recipe['id']}", json={"status": "unapproved"})

        assert response.status_code == 400

    def test_update_requires_login(
        self, client: TestClient, unauthenticated_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        recipe = _create_recipe(client, category_id)

        response = unauthenticated_client.put(
            f"/recipes/{recipe['id']}", json={"translation": {"title": "Nope"}}
        )

        assert response.status_code == 401


class TestAcknowledgeImportEndpoint:
    def _create_imported_recipe(self, db_session: Session, category_id: int, owner: User) -> Recipe:
        recipe = Recipe(
            category_id=category_id,
            source_url="https://example.com/imported-recipe",
            owner_user_id=owner.id,
        )
        recipe.translations.append(RecipeTranslation(language="en", title="Imported", slug="imported"))
        db_session.add(recipe)
        db_session.commit()
        db_session.refresh(recipe)
        return recipe

    def test_owner_can_acknowledge_their_own_import(
        self, client: TestClient, user_client: TestClient, db_session: Session, regular_user: User
    ) -> None:
        category_id = _create_category(client)
        recipe = self._create_imported_recipe(db_session, category_id, regular_user)
        assert recipe.import_reviewed_at is None

        response = user_client.post(f"/recipes/{recipe.id}/acknowledge-import")

        assert response.status_code == 200
        assert response.json()["import_reviewed_at"] is not None

    def test_admin_can_acknowledge_someone_elses_import(
        self, client: TestClient, db_session: Session, regular_user: User
    ) -> None:
        category_id = _create_category(client)
        recipe = self._create_imported_recipe(db_session, category_id, regular_user)

        response = client.post(f"/recipes/{recipe.id}/acknowledge-import")

        assert response.status_code == 200
        assert response.json()["import_reviewed_at"] is not None

    def test_non_owner_non_admin_cannot_acknowledge(
        self, client: TestClient, user_client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        category_id = _create_category(client)
        recipe = self._create_imported_recipe(db_session, category_id, admin_user)

        response = user_client.post(f"/recipes/{recipe.id}/acknowledge-import")

        assert response.status_code == 403

    def test_acknowledge_rejects_a_non_imported_recipe(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        recipe = _create_recipe(user_client, category_id)

        response = user_client.post(f"/recipes/{recipe['id']}/acknowledge-import")

        assert response.status_code == 400


class TestListPagination:
    def test_limit_and_offset_page_through_results_newest_first(
        self, client: TestClient
    ) -> None:
        category_id = _create_category(client)
        first = _create_recipe(client, category_id, title="First", is_shared=True)
        second = _create_recipe(client, category_id, title="Second", is_shared=True)
        third = _create_recipe(client, category_id, title="Third", is_shared=True)

        page1 = client.get("/recipes", params={"category_id": category_id, "limit": 2, "offset": 0})
        page2 = client.get("/recipes", params={"category_id": category_id, "limit": 2, "offset": 2})

        assert [r["id"] for r in page1.json()] == [third["id"], second["id"]]
        assert [r["id"] for r in page2.json()] == [first["id"]]

    def test_x_total_count_reflects_the_full_match_not_just_the_page(
        self, client: TestClient
    ) -> None:
        category_id = _create_category(client)
        for i in range(5):
            _create_recipe(client, category_id, title=f"Recipe {i}", is_shared=True)

        response = client.get("/recipes", params={"category_id": category_id, "limit": 2})

        assert response.headers["x-total-count"] == "5"
        assert len(response.json()) == 2

    def test_omitting_limit_returns_everything_matching_unpaginated(
        self, client: TestClient, unauthenticated_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        _create_recipe(client, category_id, title="Shared one", is_shared=True)
        _create_recipe(client, category_id, title="Shared two", is_shared=True)

        response = unauthenticated_client.get("/recipes", params={"category_id": category_id})

        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.headers["x-total-count"] == "2"

    def test_owner_me_returns_only_the_callers_own_recipes_any_status(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        mine_private = _create_recipe(user_client, category_id, title="My private recipe")
        mine_shared = _create_recipe(
            user_client, category_id, title="My shared recipe", is_shared=True
        )
        _create_recipe(client, category_id, title="Someone else's recipe", is_shared=True)

        response = user_client.get("/recipes", params={"owner": "me"})

        assert response.status_code == 200
        ids = {r["id"] for r in response.json()}
        assert ids == {mine_private["id"], mine_shared["id"]}

    def test_owner_me_requires_authentication(self, unauthenticated_client: TestClient) -> None:
        response = unauthenticated_client.get("/recipes", params={"owner": "me"})

        assert response.status_code == 401

    def test_owner_by_id_returns_that_users_recipes_any_status_for_an_admin(
        self, client: TestClient, user_client: TestClient, regular_user: User
    ) -> None:
        category_id = _create_category(client)
        theirs_private = _create_recipe(user_client, category_id, title="Their private recipe")
        theirs_shared = _create_recipe(
            user_client, category_id, title="Their shared recipe", is_shared=True
        )
        _create_recipe(client, category_id, title="Admin's own recipe", is_shared=True)

        response = client.get("/recipes", params={"owner": str(regular_user.id)})

        assert response.status_code == 200
        ids = {r["id"] for r in response.json()}
        assert ids == {theirs_private["id"], theirs_shared["id"]}

    def test_owner_by_id_rejects_a_non_admin_caller(
        self, user_client: TestClient, admin_user: User
    ) -> None:
        response = user_client.get("/recipes", params={"owner": str(admin_user.id)})

        assert response.status_code == 403

    def test_owner_by_id_rejects_an_anonymous_caller(
        self, unauthenticated_client: TestClient, admin_user: User
    ) -> None:
        response = unauthenticated_client.get("/recipes", params={"owner": str(admin_user.id)})

        assert response.status_code == 403

    def test_owner_by_id_404s_for_an_unknown_id(self, client: TestClient) -> None:
        response = client.get("/recipes", params={"owner": "999999"})

        assert response.status_code == 404

    def test_owner_rejects_a_non_numeric_value(self, client: TestClient) -> None:
        response = client.get("/recipes", params={"owner": "nobody"})

        assert response.status_code == 400

    def test_only_public_excludes_the_admins_own_private_recipes(
        self, client: TestClient
    ) -> None:
        category_id = _create_category(client)
        _create_recipe(client, category_id, title="Admin private recipe")
        shared = _create_recipe(client, category_id, title="Admin shared recipe", is_shared=True)

        response = client.get("/recipes", params={"only_public": True})

        ids = {r["id"] for r in response.json()}
        assert ids == {shared["id"]}

    def test_only_public_still_excludes_a_regular_users_own_private_recipe(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        _create_recipe(user_client, category_id, title="My private recipe")
        # A non-admin's shared recipe needs approval before it's actually public — see
        # create_recipe's moderation rule. Approve it so it's genuinely part of the public pool.
        shared = _create_recipe(user_client, category_id, title="My shared recipe", is_shared=True)
        client.post(f"/recipes/{shared['id']}/approve")

        response = user_client.get("/recipes", params={"only_public": True})

        titles = [r["title"] for r in response.json()]
        assert titles == [shared["title"]]

    def test_favorites_only_returns_only_the_callers_favorited_recipes(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        favorited = _create_recipe(client, category_id, title="Favorited", is_shared=True)
        _create_recipe(client, category_id, title="Not favorited", is_shared=True)
        user_client.post(f"/recipes/{favorited['id']}/favorite")

        response = user_client.get("/recipes", params={"favorites_only": True})

        assert response.status_code == 200
        ids = [r["id"] for r in response.json()]
        assert ids == [favorited["id"]]

    def test_favorites_only_combines_with_category_id(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        desserts_id = _create_category(client, "Desserts")
        mains_id = _create_category(client, "Mains")
        dessert = _create_recipe(client, desserts_id, title="Favorited dessert", is_shared=True)
        main = _create_recipe(client, mains_id, title="Favorited main", is_shared=True)
        user_client.post(f"/recipes/{dessert['id']}/favorite")
        user_client.post(f"/recipes/{main['id']}/favorite")

        response = user_client.get(
            "/recipes", params={"favorites_only": True, "category_id": desserts_id}
        )

        ids = [r["id"] for r in response.json()]
        assert ids == [dessert["id"]]

    def test_favorites_only_hides_a_favorite_that_lost_visibility(
        self, client: TestClient, user_client: TestClient
    ) -> None:
        category_id = _create_category(client)
        # Own-and-share, favorite it, then un-share it — the favorite outlives the recipe's
        # public visibility, and favorites_only must not leak it back.
        shared = _create_recipe(client, category_id, title="Now private", is_shared=True)
        user_client.post(f"/recipes/{shared['id']}/favorite")
        client.patch(f"/recipes/{shared['id']}/share", json={"is_shared": False})

        response = user_client.get("/recipes", params={"favorites_only": True})

        assert response.json() == []

    def test_favorites_only_requires_authentication(
        self, unauthenticated_client: TestClient
    ) -> None:
        response = unauthenticated_client.get("/recipes", params={"favorites_only": True})

        assert response.status_code == 401
