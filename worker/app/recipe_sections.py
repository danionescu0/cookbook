# Kept in sync by hand with api/app/recipe_sections.py — see the "Worker/API code sharing"
# design decision (worker and api are separate deployable images, neither imports the other).
#
# A recipe's ingredients/steps are stored as flat string lists. Some source recipes split those
# into labeled sub-groups (e.g. "For the cake:", "For the frosting:") — rather than a structural
# schema change (which would complicate nutrition's flat, index-based
# RecipeIngredientLink.ingredient_index), a sub-group label is just another entry in the same
# list, marked with this prefix so it's unambiguous and never collides with real
# ingredient/step text.
SECTION_HEADER_PREFIX = "### "


def is_section_header(line: str) -> bool:
    return line.startswith(SECTION_HEADER_PREFIX)


def strip_section_header(line: str) -> str:
    return line[len(SECTION_HEADER_PREFIX) :] if is_section_header(line) else line
