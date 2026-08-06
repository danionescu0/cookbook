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

    result = claude_client.extract_recipe(
        "<html></html>", ["ro", "en"], "test-key", ["Desserts", "Main"]
    )

    assert result == expected


def test_extract_recipe_raises_when_no_tool_use_block(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = SimpleNamespace(content=[FakeBlock("text")])
    monkeypatch.setattr(claude_client, "_client", lambda api_key: FakeClient(fake_response))

    with pytest.raises(claude_client.RecipeExtractionError):
        claude_client.extract_recipe("<html></html>", ["ro", "en"], "test-key", ["Desserts"])


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

    claude_client.extract_recipe("<html></html>", ["ro"], "sk-ant-live-key", ["Desserts"])

    assert received_keys == ["sk-ant-live-key"]


def test_parse_ingredients_for_nutrition_returns_tool_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {
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


def test_parse_recipe_from_text_returns_tool_input(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = {
        "translations": [
            {
                "language": "ro",
                "title": "Batoane cu mere",
                "description": "",
                "ingredients": ["mere", "fulgi de ovaz"],
                "steps": ["amestecă", "coace"],
                "tips": [],
            }
        ]
    }
    fake_response = SimpleNamespace(
        content=[FakeBlock("tool_use", "extracted_recipe_text", expected)]
    )
    monkeypatch.setattr(claude_client, "_client", lambda api_key: FakeClient(fake_response))

    result = claude_client.parse_recipe_from_text(
        "caption text here", ["ro"], "test-key", ["Desserts"]
    )

    assert result == expected


def test_parse_recipe_from_text_raises_when_no_tool_use_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_response = SimpleNamespace(content=[FakeBlock("text")])
    monkeypatch.setattr(claude_client, "_client", lambda api_key: FakeClient(fake_response))

    with pytest.raises(claude_client.RecipeExtractionError):
        claude_client.parse_recipe_from_text("caption text here", ["ro"], "test-key", ["Desserts"])


def test_translate_recipe_returns_tool_input(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = {
        "translations": [
            {
                "language": "en",
                "title": "Cake",
                "description": "A cake.",
                "ingredients": ["flour", "sugar"],
                "steps": ["mix", "bake"],
                "tips": [],
            }
        ]
    }
    fake_response = SimpleNamespace(content=[FakeBlock("tool_use", "translated_recipe", expected)])
    monkeypatch.setattr(claude_client, "_client", lambda api_key: FakeClient(fake_response))

    source = {
        "title": "Prăjitură",
        "description": "O prăjitură.",
        "ingredients": ["făină", "zahăr"],
        "steps": ["amestecă", "coace"],
        "tips": [],
    }
    result = claude_client.translate_recipe(source, ["en"], "test-key")

    assert result == expected


def test_translate_recipe_raises_when_no_tool_use_block(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = SimpleNamespace(content=[FakeBlock("text")])
    monkeypatch.setattr(claude_client, "_client", lambda api_key: FakeClient(fake_response))

    with pytest.raises(claude_client.RecipeExtractionError):
        claude_client.translate_recipe({"title": "Soup"}, ["ro"], "test-key")


class RecordingFakeMessages:
    def __init__(self, response: SimpleNamespace) -> None:
        self._response = response
        self.received_kwargs: dict[str, object] | None = None

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.received_kwargs = kwargs
        return self._response


class RecordingFakeClient:
    def __init__(self, response: SimpleNamespace) -> None:
        self.messages = RecordingFakeMessages(response)


# Extraction/parsing calls (large-HTML input, mechanical tool-forced output) run on the cheaper
# Haiku model; translate_recipe (small input, quality-sensitive) stays on Sonnet — see the model
# constants' docstring in claude_client.py.
def test_extract_recipe_uses_extraction_model(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = SimpleNamespace(content=[FakeBlock("tool_use", "extracted_recipe", {})])
    fake_client = RecordingFakeClient(fake_response)
    monkeypatch.setattr(claude_client, "_client", lambda api_key: fake_client)

    claude_client.extract_recipe("<html></html>", ["ro"], "test-key", ["Desserts"])

    assert fake_client.messages.received_kwargs["model"] == claude_client.EXTRACTION_MODEL


def test_parse_ingredients_for_nutrition_uses_extraction_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_response = SimpleNamespace(content=[FakeBlock("tool_use", "parsed_ingredients", {})])
    fake_client = RecordingFakeClient(fake_response)
    monkeypatch.setattr(claude_client, "_client", lambda api_key: fake_client)

    claude_client.parse_ingredients_for_nutrition(["1 medium onion"], "test-key")

    assert fake_client.messages.received_kwargs["model"] == claude_client.EXTRACTION_MODEL


def test_parse_recipe_from_text_uses_extraction_model(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = SimpleNamespace(
        content=[FakeBlock("tool_use", "extracted_recipe_text", {})]
    )
    fake_client = RecordingFakeClient(fake_response)
    monkeypatch.setattr(claude_client, "_client", lambda api_key: fake_client)

    claude_client.parse_recipe_from_text("caption text", ["ro"], "test-key", ["Desserts"])

    assert fake_client.messages.received_kwargs["model"] == claude_client.EXTRACTION_MODEL


def test_translate_recipe_uses_sonnet_model(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = SimpleNamespace(content=[FakeBlock("tool_use", "translated_recipe", {})])
    fake_client = RecordingFakeClient(fake_response)
    monkeypatch.setattr(claude_client, "_client", lambda api_key: fake_client)

    claude_client.translate_recipe({"title": "Soup"}, ["en"], "test-key")

    assert fake_client.messages.received_kwargs["model"] == claude_client.MODEL


# A real import (a long recipe, translated into two languages) hit `stop_reason: "max_tokens"` at
# the old 4096 ceiling: Claude finished the `images` array but never got to `translations` at all,
# which surfaced as a misleadingly generic "Claude returned no translations" failure rather than
# anything mentioning truncation. These lock in the higher budget — see the "Extraction max_tokens
# was too low for a long, multi-language recipe" Design Decisions entry.
def test_extract_recipe_uses_a_high_enough_max_tokens_for_a_long_multilingual_recipe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_response = SimpleNamespace(content=[FakeBlock("tool_use", "extracted_recipe", {})])
    fake_client = RecordingFakeClient(fake_response)
    monkeypatch.setattr(claude_client, "_client", lambda api_key: fake_client)

    claude_client.extract_recipe("<html></html>", ["ro", "en"], "test-key", ["Desserts"])

    assert fake_client.messages.received_kwargs["max_tokens"] >= 8192


def test_parse_recipe_from_text_uses_a_high_enough_max_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_response = SimpleNamespace(
        content=[FakeBlock("tool_use", "extracted_recipe_text", {})]
    )
    fake_client = RecordingFakeClient(fake_response)
    monkeypatch.setattr(claude_client, "_client", lambda api_key: fake_client)

    claude_client.parse_recipe_from_text("caption text", ["ro", "en"], "test-key", ["Desserts"])

    assert fake_client.messages.received_kwargs["max_tokens"] >= 8192


# Categories are admin-created, free-text rows (not a fixed enum) — Claude has to be given the
# real, current list per call so it can pick from it verbatim (see claude_client.py's
# _category_instruction and worker/app/handlers.py's _resolve_category_id, which resolves
# whatever name comes back to a real category_id).
def test_extract_recipe_includes_the_category_list_in_the_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_response = SimpleNamespace(content=[FakeBlock("tool_use", "extracted_recipe", {})])
    fake_client = RecordingFakeClient(fake_response)
    monkeypatch.setattr(claude_client, "_client", lambda api_key: fake_client)

    claude_client.extract_recipe("<html></html>", ["ro"], "test-key", ["Desserts", "Main course"])

    prompt = fake_client.messages.received_kwargs["messages"][0]["content"]
    assert "Desserts" in prompt
    assert "Main course" in prompt


def test_parse_recipe_from_text_includes_the_category_list_in_the_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_response = SimpleNamespace(
        content=[FakeBlock("tool_use", "extracted_recipe_text", {})]
    )
    fake_client = RecordingFakeClient(fake_response)
    monkeypatch.setattr(claude_client, "_client", lambda api_key: fake_client)

    claude_client.parse_recipe_from_text(
        "caption text", ["ro"], "test-key", ["Desserts", "Main course"]
    )

    prompt = fake_client.messages.received_kwargs["messages"][0]["content"]
    assert "Desserts" in prompt
    assert "Main course" in prompt


def test_translate_recipe_uses_a_high_enough_max_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = SimpleNamespace(content=[FakeBlock("tool_use", "translated_recipe", {})])
    fake_client = RecordingFakeClient(fake_response)
    monkeypatch.setattr(claude_client, "_client", lambda api_key: fake_client)

    claude_client.translate_recipe({"title": "Soup"}, ["en", "ro"], "test-key")

    assert fake_client.messages.received_kwargs["max_tokens"] >= 8192
