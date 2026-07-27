import pytest

from app import nutrition_api_client


class FakeResponse:
    def __init__(self, json_data: dict) -> None:
        self._json = json_data

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._json


def test_lookup_nutrition_returns_the_first_item(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        nutrition_api_client.httpx,
        "get",
        lambda url, **kwargs: FakeResponse(
            {"items": [{"name": "onion", "calories": 44.0, "serving_size_g": 100.0}]}
        ),
    )

    result = nutrition_api_client.lookup_nutrition("100g onion", "test-key")

    assert result == {"name": "onion", "calories": 44.0, "serving_size_g": 100.0}


def test_lookup_nutrition_sends_the_api_key_header(monkeypatch: pytest.MonkeyPatch) -> None:
    received_headers = []

    def _fake_get(url: str, **kwargs: object) -> FakeResponse:
        received_headers.append(kwargs.get("headers"))
        return FakeResponse({"items": []})

    monkeypatch.setattr(nutrition_api_client.httpx, "get", _fake_get)

    nutrition_api_client.lookup_nutrition("onion", "my-secret-key")

    assert received_headers == [{"X-Api-Key": "my-secret-key"}]


def test_lookup_nutrition_returns_none_when_no_items_matched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        nutrition_api_client.httpx, "get", lambda url, **kwargs: FakeResponse({"items": []})
    )

    assert nutrition_api_client.lookup_nutrition("nonexistent food xyz", "test-key") is None


def test_extract_nutrients_per_100g_normalizes_by_serving_size() -> None:
    # 200g serving reporting 80 kcal -> 40 kcal per 100g.
    item = {
        "calories": 80.0,
        "protein_g": 2.0,
        "carbohydrates_total_g": 20.0,
        "sugar_g": 8.0,
        "fat_total_g": 0.2,
        "serving_size_g": 200.0,
    }

    nutrients = nutrition_api_client.extract_nutrients_per_100g(item)

    assert nutrients == {
        "calories_per_100g": 40.0,
        "protein_per_100g": 1.0,
        "carbs_per_100g": 10.0,
        "sugars_per_100g": 4.0,
        "fat_per_100g": 0.1,
    }


def test_extract_nutrients_per_100g_is_a_no_op_when_serving_is_already_100g() -> None:
    item = {
        "calories": 44.0,
        "protein_g": 1.1,
        "carbohydrates_total_g": 9.3,
        "sugar_g": 4.2,
        "fat_total_g": 0.1,
        "serving_size_g": 100.0,
    }

    nutrients = nutrition_api_client.extract_nutrients_per_100g(item)

    assert nutrients == {
        "calories_per_100g": 44.0,
        "protein_per_100g": 1.1,
        "carbs_per_100g": 9.3,
        "sugars_per_100g": 4.2,
        "fat_per_100g": 0.1,
    }


def test_extract_nutrients_per_100g_defaults_to_zero_for_missing_serving_size() -> None:
    nutrients = nutrition_api_client.extract_nutrients_per_100g({"calories": 44.0})

    assert nutrients == {
        "calories_per_100g": 0.0,
        "protein_per_100g": 0.0,
        "carbs_per_100g": 0.0,
        "sugars_per_100g": 0.0,
        "fat_per_100g": 0.0,
    }
