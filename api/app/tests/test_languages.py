from fastapi.testclient import TestClient


def test_list_languages(client: TestClient) -> None:
    response = client.get("/languages")

    assert response.status_code == 200
    body = response.json()
    assert body == {"supported": ["ro", "en"], "default": "ro"}
