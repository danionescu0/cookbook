import anthropic

MODEL = "claude-sonnet-5"

_EXTRACT_RECIPE_TOOL = {
    "name": "extracted_recipe",
    "description": (
        "The cleaned-up recipe extracted from a raw recipe-page HTML, translated into each "
        "requested language."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "images": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "URLs of the recipe's own photos (hero image, step photos), absolute or "
                    "relative to the page. Do not include ads, icons, logos, or unrelated images."
                ),
            },
            "translations": {
                "type": "array",
                "description": "One entry per requested language code.",
                "items": {
                    "type": "object",
                    "properties": {
                        "language": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "ingredients": {"type": "array", "items": {"type": "string"}},
                        "steps": {"type": "array", "items": {"type": "string"}},
                        "tips": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [
                        "language",
                        "title",
                        "description",
                        "ingredients",
                        "steps",
                        "tips",
                    ],
                },
            },
        },
        "required": ["images", "translations"],
    },
}


class RecipeExtractionError(Exception):
    pass


def _client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key)


def extract_recipe(html: str, languages: list[str], api_key: str) -> dict:
    languages_str = ", ".join(languages)
    response = _client(api_key).messages.create(
        model=MODEL,
        max_tokens=4096,
        tools=[_EXTRACT_RECIPE_TOOL],
        tool_choice={"type": "tool", "name": "extracted_recipe"},
        messages=[
            {
                "role": "user",
                "content": (
                    "You are extracting a cooking recipe from the raw HTML of a recipe web page. "
                    "Strip ads, navigation, comments, and any other boilerplate. Keep only the "
                    "recipe's own images, description, ingredients, steps, and tips. Produce one "
                    f"translation for each of these language codes: {languages_str}. Here is the "
                    f"page HTML:\n\n{html}"
                ),
            }
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "extracted_recipe":
            return block.input

    raise RecipeExtractionError("Claude did not return a structured recipe")
