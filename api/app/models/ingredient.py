from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Ingredient(Base):
    """Canonical nutrition reference for one food, resolved once and reused across recipes.

    Populated by the worker's nutrition job (see worker/app/nutrition_handlers.py), sourced from
    the CalorieNinjas API — see README Design Decisions ("Ingredient nutrition"). Nutrient values
    are per 100g (normalized from whatever serving size the API returned for a "100g <name>"
    query), so a recipe's totals are computed as `nutrient_per_100g * estimated_grams / 100` at
    read time (see RecipeIngredientLink).
    """

    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Claude's canonical English food name for this ingredient (lowercased) — not guaranteed
    # globally unique (e.g. "onion" vs "yellow onion" can both get created); the API is a plain
    # text-query lookup with no stable per-food ID to dedupe by instead. Good enough for a
    # single-operator tool; revisit with fuzzy matching if duplicates turn out to matter.
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    calories_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    protein_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    sugars_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
