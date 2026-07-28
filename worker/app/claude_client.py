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


_PARSE_INGREDIENTS_TOOL = {
    "name": "parsed_ingredients",
    "description": (
        "Structured, nutrition-lookup-ready breakdown of a recipe's ingredient list, plus an "
        "estimate of how many people the recipe serves."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "estimated_servings": {
                "type": "integer",
                "description": (
                    "Best estimate of how many people this recipe serves, based on the "
                    "ingredient quantities (any explicit serving count in the recipe wins if "
                    "one was given)."
                ),
            },
            "items": {
                "type": "array",
                "description": "One entry per input ingredient line, same order as given.",
                "items": {
                    "type": "object",
                    "properties": {
                        "line_index": {
                            "type": "integer",
                            "description": "0-based index matching the input ingredient list.",
                        },
                        "food_name": {
                            "type": "string",
                            "description": (
                                "Generic English food name for a nutrition-database lookup, "
                                "e.g. 'onion', 'olive oil', 'garlic' — no brand names, no "
                                "preparation notes like 'diced' or 'ripe'."
                            ),
                        },
                        "quantity": {
                            "type": "number",
                            "description": (
                                "Numeric quantity, e.g. 2 for '2 cloves garlic'. Use 1 if the "
                                "line doesn't give a count, e.g. 'a pinch of salt'."
                            ),
                        },
                        "unit": {
                            "type": "string",
                            "description": (
                                "The unit or size word used, e.g. 'clove', 'medium', 'cup', "
                                "'tbsp', 'g'. Empty string if the line has none."
                            ),
                        },
                        "estimated_grams": {
                            "type": "number",
                            "description": (
                                "Your own best-guess total weight in grams for this ingredient "
                                "line (quantity x unit) — used only as a fallback when no "
                                "matching portion-weight data exists in the nutrition database."
                            ),
                        },
                    },
                    "required": ["line_index", "food_name", "quantity", "unit", "estimated_grams"],
                },
            },
        },
        "required": ["estimated_servings", "items"],
    },
}


_PARSE_RECIPE_TEXT_TOOL = {
    "name": "extracted_recipe_text",
    "description": (
        "The cleaned-up recipe extracted from a social-media post's caption and comments, "
        "translated into each requested language. No image list — unlike HTML-page extraction, "
        "the post's image is already resolved independently of this call."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "translations": {
                "type": "array",
                "description": (
                    "One entry per requested language code. Empty array if no recipe is "
                    "present in the text at all."
                ),
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
        "required": ["translations"],
    },
}


_TRANSLATE_RECIPE_TOOL = {
    "name": "translated_recipe",
    "description": (
        "A recipe's title, description, ingredients, steps, and tips translated from one "
        "language into each of the given target languages. This is a faithful translation of "
        "already-clean, just-edited content — not a fresh extraction — so the same number of "
        "ingredient/step/tip lines, in the same order, with the same quantities, must come back "
        "for every target language."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "translations": {
                "type": "array",
                "description": "One entry per target language code.",
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
        "required": ["translations"],
    },
}


class RecipeExtractionError(Exception):
    pass


class IngredientParseError(Exception):
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


def parse_ingredients_for_nutrition(ingredient_lines: list[str], api_key: str) -> dict:
    numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(ingredient_lines))
    response = _client(api_key).messages.create(
        model=MODEL,
        max_tokens=2048,
        tools=[_PARSE_INGREDIENTS_TOOL],
        tool_choice={"type": "tool", "name": "parsed_ingredients"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Parse this recipe's ingredient list for a nutrition-database lookup. For "
                    "each line, give the generic food name, its quantity and unit, and your own "
                    "best-guess total weight in grams. Also estimate how many people the whole "
                    f"recipe serves.\n\n{numbered}"
                ),
            }
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "parsed_ingredients":
            return block.input

    raise IngredientParseError("Claude did not return parsed ingredients")


def parse_recipe_from_text(text: str, languages: list[str], api_key: str) -> dict:
    languages_str = ", ".join(languages)
    response = _client(api_key).messages.create(
        model=MODEL,
        max_tokens=4096,
        tools=[_PARSE_RECIPE_TEXT_TOOL],
        tool_choice={"type": "tool", "name": "extracted_recipe_text"},
        messages=[
            {
                "role": "user",
                "content": (
                    "You are extracting a cooking recipe from a social media post's caption and "
                    "comments (e.g. an Instagram post or reel). The recipe may be entirely in "
                    "the caption, or split between the caption and a comment. Ignore unrelated "
                    "comments (praise, questions, hashtags, engagement bait, other users' posts). "
                    "Produce one translation for each of these language codes: "
                    f"{languages_str}. If no recipe is present anywhere in the text, return an "
                    f"empty translations array. Here is the post's text:\n\n{text}"
                ),
            }
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "extracted_recipe_text":
            return block.input

    raise RecipeExtractionError("Claude did not return a structured recipe")


def translate_recipe(source: dict, target_languages: list[str], api_key: str) -> dict:
    languages_str = ", ".join(target_languages)
    prompt_lines = [
        "Translate this recipe faithfully into each of these language codes: "
        f"{languages_str}. Keep the same number of ingredient, step, and tip lines in the same "
        "order, with the same quantities — this is a translation of content that was just "
        "hand-edited, not a fresh recipe extraction, so nothing should be added, removed, or "
        "reinterpreted.",
        "",
        f"Title: {source.get('title', '')}",
        f"Description: {source.get('description', '')}",
        "Ingredients:",
        *source.get("ingredients", []),
        "Steps:",
        *source.get("steps", []),
        "Tips:",
        *source.get("tips", []),
    ]
    response = _client(api_key).messages.create(
        model=MODEL,
        max_tokens=4096,
        tools=[_TRANSLATE_RECIPE_TOOL],
        tool_choice={"type": "tool", "name": "translated_recipe"},
        messages=[{"role": "user", "content": "\n".join(prompt_lines)}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "translated_recipe":
            return block.input

    raise RecipeExtractionError("Claude did not return a structured recipe")
