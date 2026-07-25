from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RecipeTranslation(Base):
    __tablename__ = "recipe_translations"
    __table_args__ = (
        UniqueConstraint("recipe_id", "language", name="uq_recipe_translations_recipe_language"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    # Plain string, not a DB enum, validated against settings.supported_languages_list at the
    # application layer — adding a language is a config change, not a migration.
    language: Mapped[str] = mapped_column(String(10), nullable=False)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    ingredients: Mapped[list[str]] = mapped_column(JSON, default=list)
    steps: Mapped[list[str]] = mapped_column(JSON, default=list)
    tips: Mapped[list[str]] = mapped_column(JSON, default=list)

    recipe: Mapped["Recipe"] = relationship(back_populates="translations")
