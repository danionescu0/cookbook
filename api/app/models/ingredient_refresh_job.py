import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IngredientRefreshJobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class IngredientRefreshJob(Base):
    """Global (not per-recipe) job: re-fetches USDA nutrition data for every existing
    `Ingredient` row. Triggered by the "Reparse all ingredients" button in Backoffice > Settings
    — see README Design Decisions ("Ingredient nutrition").
    """

    __tablename__ = "ingredient_refresh_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[IngredientRefreshJobStatus] = mapped_column(
        Enum(IngredientRefreshJobStatus, native_enum=False),
        default=IngredientRefreshJobStatus.QUEUED,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingredients_updated: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
