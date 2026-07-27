import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RecipeStatus(str, enum.Enum):
    UNAPPROVED = "unapproved"
    APPROVED = "approved"


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)

    images: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[RecipeStatus] = mapped_column(
        Enum(RecipeStatus, native_enum=False), default=RecipeStatus.APPROVED
    )
    # Set by the nutrition-enrichment job (see nutrition_job.py), not the original import — null
    # until an admin clicks "Enrich nutrition" for this recipe.
    estimated_servings: Mapped[int | None] = mapped_column(nullable=True)

    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    category: Mapped["Category"] = relationship(back_populates="recipes")
    translations: Mapped[list["RecipeTranslation"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )
