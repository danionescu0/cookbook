from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RecipeIngredientLink(Base):
    """The expensive-to-compute part of nutrition: which canonical ingredient (and how many
    estimated grams) a recipe's Nth ingredient line resolves to.

    Recomputing a recipe's nutrition totals from these rows is cheap (a join + sum over already-
    resolved data), so those totals are never stored — only this mapping is, since resolving it
    costs a CalorieNinjas lookup and a Claude parse per ingredient. See README Design Decisions
    ("Ingredient nutrition").

    `ingredient_index` ties back to the position in recipe_translations.ingredients — resolution
    runs once per recipe (not once per language) on the assumption that every language's
    translation preserves ingredient order/count; see worker/app/nutrition_handlers.py.
    """

    __tablename__ = "recipe_ingredient_links"
    __table_args__ = (
        UniqueConstraint(
            "recipe_id", "ingredient_index", name="uq_recipe_ingredient_links_recipe_index"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_index: Mapped[int] = mapped_column(Integer, nullable=False)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), nullable=False)

    raw_text: Mapped[str] = mapped_column(String(500), nullable=False)
    estimated_grams: Mapped[float] = mapped_column(Float, nullable=False)
    # "api_lookup" when CalorieNinjas resolved a serving weight for this line's exact quantity
    # text, "claude_estimate" when that lookup failed and Claude's own gram guess was used
    # instead — surfaced so an admin can tell which numbers are more trustworthy.
    grams_source: Mapped[str] = mapped_column(String(20), nullable=False)

    ingredient: Mapped["Ingredient"] = relationship()
