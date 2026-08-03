from fastapi.testclient import TestClient


def _create_category(client: TestClient, name: str = "Desserts") -> int:
    return client.post("/categories", json={"name": name}).json()["id"]


def _set_public_site_url(client: TestClient, url: str = "https://example.com") -> None:
    response = client.patch("/settings", json={"public_site_url": url})
    assert response.status_code == 200


class TestSitemap:
    def test_empty_without_a_configured_public_site_url(self, unauthenticated_client: TestClient) -> None:
        response = unauthenticated_client.get("/sitemap.xml")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/xml")
        assert "<loc>" not in response.text
        assert "<urlset" in response.text

    def test_only_lists_approved_and_shared_recipes(
        self, client: TestClient, user_client: TestClient, unauthenticated_client: TestClient
    ) -> None:
        _set_public_site_url(client)
        category_id = _create_category(client)
        client.post(
            "/recipes",
            json={"title": "Private admin recipe", "category_id": category_id, "language": "en"},
        )
        user_client.post(
            "/recipes",
            json={"title": "Private user recipe", "category_id": category_id, "language": "en"},
        )
        shared = client.post(
            "/recipes",
            json={
                "title": "Shared Lemon Tart",
                "category_id": category_id,
                "language": "en",
                "is_shared": True,
            },
        ).json()

        response = unauthenticated_client.get("/sitemap.xml")

        assert response.status_code == 200
        assert "Private" not in response.text
        assert f"/en/recipes/{shared['id']}-shared-lemon-tart" in response.text

    def test_includes_hreflang_alternates_for_available_languages(
        self, client: TestClient, unauthenticated_client: TestClient
    ) -> None:
        _set_public_site_url(client)
        category_id = _create_category(client)
        recipe = client.post(
            "/recipes",
            json={
                "title": "Shared Soup",
                "category_id": category_id,
                "language": "en",
                "is_shared": True,
            },
        ).json()
        client.put(
            f"/recipes/{recipe['id']}",
            json={"translation": {"title": "Supă"}},
            params={"language": "ro"},
        )

        response = unauthenticated_client.get("/sitemap.xml")

        assert f'hreflang="en" href="https://example.com/en/recipes/{recipe["id"]}-shared-soup"' in response.text
        assert f'hreflang="ro" href="https://example.com/ro/recipes/{recipe["id"]}-supa"' in response.text

    def test_static_landing_and_browse_pages_are_listed_for_every_supported_language(
        self, client: TestClient, unauthenticated_client: TestClient
    ) -> None:
        _set_public_site_url(client)

        response = unauthenticated_client.get("/sitemap.xml")

        assert "<loc>https://example.com/en</loc>" in response.text
        assert "<loc>https://example.com/ro</loc>" in response.text
        assert "<loc>https://example.com/en/recipes</loc>" in response.text
        assert "<loc>https://example.com/ro/recipes</loc>" in response.text


class TestRobotsTxt:
    def test_disallows_private_app_areas(self, unauthenticated_client: TestClient) -> None:
        response = unauthenticated_client.get("/robots.txt")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        for path in ("/backoffice", "/account", "/login", "/signup"):
            assert f"Disallow: {path}" in response.text

    def test_references_the_sitemap_once_a_public_site_url_is_configured(
        self, client: TestClient, unauthenticated_client: TestClient
    ) -> None:
        _set_public_site_url(client)

        response = unauthenticated_client.get("/robots.txt")

        assert "Sitemap: https://example.com/sitemap.xml" in response.text

    def test_omits_the_sitemap_line_without_a_configured_public_site_url(
        self, unauthenticated_client: TestClient
    ) -> None:
        response = unauthenticated_client.get("/robots.txt")

        assert "Sitemap:" not in response.text
