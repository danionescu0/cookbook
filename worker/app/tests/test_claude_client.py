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
    monkeypatch.setattr(claude_client, "_client", lambda: FakeClient(fake_response))

    result = claude_client.extract_recipe("<html></html>", ["ro", "en"])

    assert result == expected


def test_extract_recipe_raises_when_no_tool_use_block(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = SimpleNamespace(content=[FakeBlock("text")])
    monkeypatch.setattr(claude_client, "_client", lambda: FakeClient(fake_response))

    with pytest.raises(claude_client.RecipeExtractionError):
        claude_client.extract_recipe("<html></html>", ["ro", "en"])
