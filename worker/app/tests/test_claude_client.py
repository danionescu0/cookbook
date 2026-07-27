from types import SimpleNamespace

import pytest

from app import claude_client


class FakeBlock:
    def __init__(self, type: str, name: str | None = None, input: dict | None = None) -> None:
        self.type = type
        self.name = name
        self.input = input


class FakeMessages:
    def __init__(self, response: SimpleNamespace) -> None:
        self._response = response

    def create(self, **kwargs: object) -> SimpleNamespace:
        return self._response


class FakeClient:
    def __init__(self, response: SimpleNamespace) -> None:
        self.messages = FakeMessages(response)


def test_extract_recipe_returns_tool_input(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = {
        "images": ["/cake.jpg"],
        "translations": [
            {
                "language": "ro",
                "title": "Prăjitură",
                "description": "O prăjitură.",
                "ingredients": ["făină"],
                "steps": ["coace"],
                "tips": [],
            },
            {
                "language": "en",
                "title": "Cake",
                "description": "A cake.",
                "ingredients": ["flour"],
                "steps": ["bake"],
                "tips": [],
            },
        ],
    }
    fake_response = SimpleNamespace(
        content=[FakeBlock("tool_use", "extracted_recipe", expected)]
    )
    monkeypatch.setattr(claude_client, "_client", lambda api_key: FakeClient(fake_response))

    result = claude_client.extract_recipe("<html></html>", ["ro", "en"], "test-key")

    assert result == expected


def test_extract_recipe_raises_when_no_tool_use_block(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = SimpleNamespace(content=[FakeBlock("text")])
    monkeypatch.setattr(claude_client, "_client", lambda api_key: FakeClient(fake_response))

    with pytest.raises(claude_client.RecipeExtractionError):
        claude_client.extract_recipe("<html></html>", ["ro", "en"], "test-key")


def test_extract_recipe_uses_the_given_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # A key changed via the Settings backoffice page must reach the next Anthropic call
    # directly, not a value cached from process startup.
    received_keys = []
    fake_response = SimpleNamespace(content=[FakeBlock("tool_use", "extracted_recipe", {})])
    monkeypatch.setattr(
        claude_client,
        "_client",
        lambda api_key: received_keys.append(api_key) or FakeClient(fake_response),
    )

    claude_client.extract_recipe("<html></html>", ["ro"], "sk-ant-live-key")

    assert received_keys == ["sk-ant-live-key"]


def test_parse_ingredients_for_nutrition_returns_tool_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {
        "estimated_servings": 4,
        "items": [
            {
                "line_index": 0,
                "food_name": "onion",
                "quantity": 1,
                "unit": "medium",
                "estimated_grams": 110,
            }
        ],
    }
    fake_response = SimpleNamespace(content=[FakeBlock("tool_use", "parsed_ingredients", expected)])
    monkeypatch.setattr(claude_client, "_client", lambda api_key: FakeClient(fake_response))

    result = claude_client.parse_ingredients_for_nutrition(["1 medium onion"], "test-key")

    assert result == expected


def test_parse_ingredients_for_nutrition_raises_when_no_tool_use_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_response = SimpleNamespace(content=[FakeBlock("text")])
    monkeypatch.setattr(claude_client, "_client", lambda api_key: FakeClient(fake_response))

    with pytest.raises(claude_client.IngredientParseError):
        claude_client.parse_ingredients_for_nutrition(["1 medium onion"], "test-key")
