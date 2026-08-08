import anthropic

from app.recipe_sections import SECTION_HEADER_PREFIX

# Structured extraction/parsing from raw scraped content (extract_recipe, parse_recipe_from_text,
# parse_ingredients_for_nutrition) is a mechanical forced-tool-call task, not open-ended reasoning,
# and dominates per-recipe Claude cost via extract_recipe's large HTML input — Haiku is the far
# cheaper fit. translate_recipe stays on Sonnet: its input is already-clean structured content
# (small, so cost isn't the driver there) and translation quality matters more.
EXTRACTION_MODEL = "claude-haiku-4-5"
MODEL = "claude-sonnet-5"

# DeepSeek, an alternate provider an admin can opt into via Settings (app_settings.
# preferred_ai_provider), is reached through DeepSeek's own Anthropic-API-compatible endpoint —
# same Messages API wire format, including forced tool_choice, so every function below needs no
# request-shape change at all, just a different base_url/api_key/model per call. Mirrors the
# existing Haiku/Sonnet cost split onto DeepSeek's own cheap/quality tiers. See README Design
# Decisions ("DeepSeek as an alternate AI provider").
_DEEPSEEK_BASE_URL = "https://api.deepseek.com/anthropic"
DEEPSEEK_EXTRACTION_MODEL = "deepseek-v4-flash"
DEEPSEEK_MODEL = "deepseek-v4-pro"

_PROVIDER_MODELS = {
    "claude": {"extraction": EXTRACTION_MODEL, "translate": MODEL},
    "deepseek": {"extraction": DEEPSEEK_EXTRACTION_MODEL, "translate": DEEPSEEK_MODEL},
}


def _thinking_kwargs(provider: str) -> dict:
    # DeepSeek's Anthropic-compatible endpoint runs deepseek-v4-flash/-pro in "thinking mode" by
    # default, and rejects forced tool_choice outright while thinking is active — "Thinking mode
    # does not support this tool_choice" (400) — discovered via a real failed import
    # (chefi.ro/reteta-de-ciocolata-neagra..., 2026-08-08). Every function below forces tool_choice
    # to a specific tool because it needs guaranteed structured output, never freeform reasoning,
    # so thinking is explicitly turned off for DeepSeek. Real Claude models don't hit this — the
    # same forced-tool_choice calls have always worked against them without a `thinking` param —
    # so this is scoped to the "deepseek" provider only, not applied globally.
    if provider == "deepseek":
        return {"thinking": {"type": "disabled"}}
    return {}

# Shared by extract_recipe/parse_recipe_from_text/translate_recipe — every call that produces a
# full `translations` array (title/description/ingredients/steps/tips, once per configured
# language). A real import hit `stop_reason: "max_tokens"` at the old value of 4096: a long,
# detailed recipe translated into two languages needed ~4500 output tokens just for the content,
# leaving no room to also emit `images` first — Claude ran out of budget mid-response with only
# `images` written and never reached `translations` at all, which surfaced as a misleadingly
# generic "Claude returned no translations" failure with no hint that it was actually a token
# limit. See the "Extraction max_tokens was too low for a long, multi-language recipe" Design
# Decisions entry.
_TRANSLATIONS_MAX_TOKENS = 8192

# Shared across every prompt that produces or preserves ingredients/steps — see
# app.recipe_sections for why this is a plain string-list marker rather than a schema change.
# Tightened after a live DeepSeek/Claude accuracy comparison (2026-08-08, see README Design
# Decisions, "DeepSeek as an alternate AI provider") found DeepSeek treating a page's own generic
# "Ingredients"/"Method" heading — labeling the *entire* list, not a real sub-recipe — as if it
# were a sub-group marker, and copying the page's own literal step numbers ("1. ...", "2. ...")
# into step text, which double-numbers once the app's own frontend numbers steps. Both new
# sentences below are aimed squarely at that failure mode; the original sub-group behavior
# (verified against real Claude extractions) is unchanged.
_SECTION_HEADER_INSTRUCTION = (
    "Some recipes split their ingredients and/or steps into labeled sub-groups (e.g. 'For the "
    "cake:', 'For the frosting:') — genuinely distinct components, each with its own ingredients "
    "and/or steps. When that happens, include each group's label as its own entry in the "
    f"ingredients/steps array, prefixed with {SECTION_HEADER_PREFIX!r} (e.g. "
    f"{SECTION_HEADER_PREFIX + 'For the cake'!r}), placed immediately before that group's lines. "
    "Do not fold the label into the wording of another line — it must be its own array entry. "
    "Do not add a label that merely names the whole list, like 'Ingredients' or 'Method'/'Mod de "
    "preparare' — even if the source page prints one — since that is not a sub-group, it is just "
    "the section itself; it must never become its own array entry. If the recipe has no genuine "
    "sub-groups, don't add any label at all. Separately: never prefix a step with your own number "
    "(no '1.', '2.', etc.) even if the source page numbers its steps that way — return each step "
    "as plain instruction text only, since the app numbers steps itself and a number baked into "
    "the text would be shown twice."
)

_EXTRACT_RECIPE_TOOL = {
    "name": "extracted_recipe",
    "description": (
        "The cleaned-up recipe extracted from a raw recipe-page HTML, translated into each "
        "requested language."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": (
                    "The single best-matching category name, chosen from the exact list of "
                    "existing category names given in the prompt. Always return one of those "
                    "exact names verbatim, even if the match is only approximate — never invent "
                    "a new one."
                ),
            },
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
                        "ingredients": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                f"May include sub-group labels prefixed with "
                                f"{SECTION_HEADER_PREFIX!r} — see the sub-group instructions."
                            ),
                        },
                        "steps": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                f"May include sub-group labels prefixed with "
                                f"{SECTION_HEADER_PREFIX!r} — see the sub-group instructions."
                            ),
                        },
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
        "required": ["category", "images", "translations"],
    },
}


_PARSE_INGREDIENTS_TOOL = {
    "name": "parsed_ingredients",
    "description": ("Structured, nutrition-lookup-ready breakdown of a recipe's ingredient list."),
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "description": (
                    "One entry per input ingredient line, same order as given — except lines "
                    f"that start with {SECTION_HEADER_PREFIX!r} (a sub-group label like 'For the "
                    "cake', not an ingredient): skip those entirely, do not include an item for "
                    "them."
                ),
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
        "required": ["items"],
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
            "category": {
                "type": "string",
                "description": (
                    "The single best-matching category name, chosen from the exact list of "
                    "existing category names given in the prompt. Always return one of those "
                    "exact names verbatim, even if the match is only approximate — never invent "
                    "a new one. Empty string if no recipe is present in the text at all."
                ),
            },
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
                        "ingredients": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                f"May include sub-group labels prefixed with "
                                f"{SECTION_HEADER_PREFIX!r} — see the sub-group instructions."
                            ),
                        },
                        "steps": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                f"May include sub-group labels prefixed with "
                                f"{SECTION_HEADER_PREFIX!r} — see the sub-group instructions."
                            ),
                        },
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
        "required": ["category", "translations"],
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
                        "ingredients": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                f"May include sub-group labels prefixed with "
                                f"{SECTION_HEADER_PREFIX!r} — see the sub-group instructions."
                            ),
                        },
                        "steps": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                f"May include sub-group labels prefixed with "
                                f"{SECTION_HEADER_PREFIX!r} — see the sub-group instructions."
                            ),
                        },
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


def _client(provider: str, api_key: str) -> anthropic.Anthropic:
    if provider == "deepseek":
        return anthropic.Anthropic(api_key=api_key, base_url=_DEEPSEEK_BASE_URL)
    return anthropic.Anthropic(api_key=api_key)


def _model_for(provider: str, task: str) -> str:
    return _PROVIDER_MODELS.get(provider, _PROVIDER_MODELS["claude"])[task]


def _category_instruction(category_names: list[str]) -> str:
    # Categories are admin-created, free-text rows (see CategoryManager), not a fixed enum — so
    # Claude is given the real, current list and told to pick from it verbatim, rather than the
    # code trying to guess/maintain a mapping from Claude's own free-text label to a category id.
    names_str = ", ".join(repr(name) for name in category_names)
    return (
        f"Also choose the single best-matching category for this recipe from this exact list of "
        f"existing categories: {names_str}. Return one of those exact names verbatim in the "
        f"`category` field, even if the match is only approximate."
    )


def extract_recipe(
    html: str,
    languages: list[str],
    api_key: str,
    category_names: list[str],
    provider: str = "claude",
) -> dict:
    languages_str = ", ".join(languages)
    response = _client(provider, api_key).messages.create(
        model=_model_for(provider, "extraction"),
        max_tokens=_TRANSLATIONS_MAX_TOKENS,
        tools=[_EXTRACT_RECIPE_TOOL],
        tool_choice={"type": "tool", "name": "extracted_recipe"},
        **_thinking_kwargs(provider),
        messages=[
            {
                "role": "user",
                "content": (
                    "You are extracting a cooking recipe from the raw HTML of a recipe web page. "
                    "Strip ads, navigation, comments, and any other boilerplate. Keep only the "
                    "recipe's own images, description, ingredients, steps, and tips. "
                    f"{_SECTION_HEADER_INSTRUCTION} Produce one translation for each of these "
                    f"language codes: {languages_str}. {_category_instruction(category_names)} "
                    f"Here is the page HTML:\n\n{html}"
                ),
            }
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "extracted_recipe":
            return block.input

    raise RecipeExtractionError("Claude did not return a structured recipe")


def parse_ingredients_for_nutrition(
    ingredient_lines: list[str], api_key: str, provider: str = "claude"
) -> dict:
    numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(ingredient_lines))
    response = _client(provider, api_key).messages.create(
        model=_model_for(provider, "extraction"),
        max_tokens=2048,
        tools=[_PARSE_INGREDIENTS_TOOL],
        tool_choice={"type": "tool", "name": "parsed_ingredients"},
        **_thinking_kwargs(provider),
        messages=[
            {
                "role": "user",
                "content": (
                    "Parse this recipe's ingredient list for a nutrition-database lookup. For "
                    "each line, give the generic food name, its quantity and unit, and your own "
                    f"best-guess total weight in grams. Lines starting with {SECTION_HEADER_PREFIX!r} "
                    "are sub-group labels, not ingredients — skip them, don't return an item for "
                    f"them.\n\n{numbered}"
                ),
            }
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "parsed_ingredients":
            return block.input

    raise IngredientParseError("Claude did not return parsed ingredients")


def parse_recipe_from_text(
    text: str,
    languages: list[str],
    api_key: str,
    category_names: list[str],
    provider: str = "claude",
) -> dict:
    languages_str = ", ".join(languages)
    response = _client(provider, api_key).messages.create(
        model=_model_for(provider, "extraction"),
        max_tokens=_TRANSLATIONS_MAX_TOKENS,
        tools=[_PARSE_RECIPE_TEXT_TOOL],
        tool_choice={"type": "tool", "name": "extracted_recipe_text"},
        **_thinking_kwargs(provider),
        messages=[
            {
                "role": "user",
                "content": (
                    "You are extracting a cooking recipe from a social media post's caption and "
                    "comments (e.g. an Instagram post or reel). The recipe may be entirely in "
                    "the caption, or split between the caption and a comment. Ignore unrelated "
                    "comments (praise, questions, hashtags, engagement bait, other users' posts). "
                    f"{_SECTION_HEADER_INSTRUCTION} Produce one translation for each of these "
                    f"language codes: {languages_str}. {_category_instruction(category_names)} "
                    "If no recipe is present anywhere in the text, return an empty translations "
                    f"array and an empty `category` string. Here is the post's text:\n\n{text}"
                ),
            }
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "extracted_recipe_text":
            return block.input

    raise RecipeExtractionError("Claude did not return a structured recipe")


def translate_recipe(
    source: dict, target_languages: list[str], api_key: str, provider: str = "claude"
) -> dict:
    languages_str = ", ".join(target_languages)
    prompt_lines = [
        "Translate this recipe faithfully into each of these language codes: "
        f"{languages_str}. Keep the same number of ingredient, step, and tip lines in the same "
        "order, with the same quantities — this is a translation of content that was just "
        "hand-edited, not a fresh recipe extraction, so nothing should be added, removed, or "
        "reinterpreted. Some lines are sub-group labels rather than ingredients/steps — "
        f"recognizable by the {SECTION_HEADER_PREFIX!r} prefix (e.g. "
        f"{SECTION_HEADER_PREFIX + 'For the cake'!r}). Translate only the label text after the "
        "prefix, and keep the prefix itself exactly as-is, untranslated, on the same line.",
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
    response = _client(provider, api_key).messages.create(
        model=_model_for(provider, "translate"),
        max_tokens=_TRANSLATIONS_MAX_TOKENS,
        tools=[_TRANSLATE_RECIPE_TOOL],
        tool_choice={"type": "tool", "name": "translated_recipe"},
        **_thinking_kwargs(provider),
        messages=[{"role": "user", "content": "\n".join(prompt_lines)}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "translated_recipe":
            return block.input

    raise RecipeExtractionError("Claude did not return a structured recipe")
