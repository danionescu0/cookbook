import httpx

NUTRITION_URL = "https://api.calorieninjas.com/v1/nutrition"

_ZERO_NUTRIENTS = {
    "calories_per_100g": 0.0,
    "protein_per_100g": 0.0,
    "carbs_per_100g": 0.0,
    "sugars_per_100g": 0.0,
    "fat_per_100g": 0.0,
}


def lookup_nutrition(query: str, api_key: str, *, timeout_seconds: float = 15.0) -> dict | None:
    """Looks up one free-text food/quantity phrase (e.g. "100g onion", "1 medium onion").

    Returns the first matched item as a raw dict (CalorieNinjas always wraps results in an
    `items` array, even for a single-food query), or None if nothing matched.
    """
    response = httpx.get(
        NUTRITION_URL,
        params={"query": query},
        headers={"X-Api-Key": api_key},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    items = response.json().get("items", [])
    return items[0] if items else None


def extract_nutrients_per_100g(item: dict) -> dict[str, float]:
    """Normalizes an item's absolute nutrient values (for whatever serving_size_g the query
    resolved to) to per-100g, so cached Ingredient rows stay comparable regardless of which
    quantity phrase originally produced them."""
    serving_size_g = item.get("serving_size_g") or 0.0
    if serving_size_g <= 0:
        return dict(_ZERO_NUTRIENTS)

    factor = 100.0 / serving_size_g
    return {
        "calories_per_100g": float(item.get("calories") or 0) * factor,
        "protein_per_100g": float(item.get("protein_g") or 0) * factor,
        "carbs_per_100g": float(item.get("carbohydrates_total_g") or 0) * factor,
        "sugars_per_100g": float(item.get("sugar_g") or 0) * factor,
        "fat_per_100g": float(item.get("fat_total_g") or 0) * factor,
    }
