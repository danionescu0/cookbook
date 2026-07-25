from fastapi.testclient import TestClient


def test_create_category(client: TestClient) -> None:
    response = client.post("/categories", json={"name": "Desserts"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Desserts"
    assert body["slug"] == "desserts"


def test_create_category_duplicate_name_conflicts(client: TestClient) -> None:
    client.post("/categories", json={"name": "Desserts"})
    response = client.post("/categories", json={"name": "Desserts"})

    assert response.status_code == 409


def test_list_categories(client: TestClient) -> None:
    client.post("/categories", json={"name": "Main Courses"})
    client.post("/categories", json={"name": "Desserts"})

    response = client.get("/categories")

    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert names == ["Desserts", "Main Courses"]  # ordered by name


def test_get_category_not_found(client: TestClient) -> None:
    response = client.get("/categories/999")

    assert response.status_code == 404


def test_update_category(client: TestClient) -> None:
    created = client.post("/categories", json={"name": "Desserts"}).json()

    response = client.put(f"/categories/{created['id']}", json={"name": "Sweets"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Sweets"
    assert body["slug"] == "sweets"


def test_delete_category(client: TestClient) -> None:
    created = client.post("/categories", json={"name": "Desserts"}).json()

    delete_response = client.delete(f"/categories/{created['id']}")
    get_response = client.get(f"/categories/{created['id']}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404
