import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, func
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
    # Every recipe has exactly one owner — admin-created/imported ones included (see migration
    # 0020's backfill). Recipes are private to their owner by default; see routers/recipes.py's
    # visibility predicate.
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # Only ever True for a manually-added recipe (source_url is None) — imported recipes never
    # get a sharing UI/endpoint, so this stays False for them by construction, not a DB
    # constraint. A shared+approved recipe is visible to everyone, not just its owner.
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    category: Mapped["Category"] = relationship(back_populates="recipes")
    translations: Mapped[list["RecipeTranslation"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )
    owner: Mapped["User"] = relationship()
