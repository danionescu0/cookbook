import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ImportJobType(str, enum.Enum):
    SINGLE = "single"
    BULK = "bulk"
    BOOKMARK = "bookmark"
    INSTAGRAM = "instagram"


class ImportJobStatus(str, enum.Enum):
    # Kept in sync by hand with api/app/models/import_job.py's ImportJobStatus — see the
    # "Worker/API code sharing" design decision. This drifted once already (missing PENDING
    # crashed db.get() on any row read while pending/queued-but-uncommitted was observed) —
    # if this enum is ever touched, touch the API's copy in the same change.
    PENDING = "pending"
    QUEUED = "queued"
    FETCHING = "fetching"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(nullable=False)
    type: Mapped[ImportJobType] = mapped_column(
        Enum(ImportJobType, native_enum=False), default=ImportJobType.SINGLE
    )
    source: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[ImportJobStatus] = mapped_column(
        Enum(ImportJobStatus, native_enum=False), default=ImportJobStatus.QUEUED
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecipeStatus(str, enum.Enum):
    UNAPPROVED = "unapproved"
    APPROVED = "approved"


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(nullable=False)
    images: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[RecipeStatus] = mapped_column(
        Enum(RecipeStatus, native_enum=False), default=RecipeStatus.APPROVED
    )

    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_servings: Mapped[int | None] = mapped_column(nullable=True)

    translations: Mapped[list["RecipeTranslation"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )


class RecipeTranslation(Base):
    __tablename__ = "recipe_translations"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    ingredients: Mapped[list[str]] = mapped_column(JSON, default=list)
    steps: Mapped[list[str]] = mapped_column(JSON, default=list)
    tips: Mapped[list[str]] = mapped_column(JSON, default=list)

    recipe: Mapped["Recipe"] = relationship(back_populates="translations")


class AppSettings(Base):
    # Kept in sync by hand with api/app/models/app_settings.py — see that module's docstring
    # for what each column means. The worker only ever reads this table (via
    # app.settings_service.get_settings); api owns writes and the migration that creates/seeds
    # it. Same "kept in sync by hand" caveat as ImportJobStatus above.
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    supported_languages: Mapped[str] = mapped_column(String(100), nullable=False)
    default_language: Mapped[str] = mapped_column(String(10), nullable=False)
    admin_password: Mapped[str] = mapped_column(String(200), nullable=False)
    anthropic_api_key: Mapped[str] = mapped_column(String(200), nullable=False)
    calorie_ninjas_api_key: Mapped[str] = mapped_column(String(200), nullable=False)
    default_rate_limit_requests_per_minute: Mapped[int] = mapped_column(nullable=False)
    scrape_timeout_seconds: Mapped[float] = mapped_column(nullable=False)
    max_html_chars: Mapped[int] = mapped_column(nullable=False)
    image_max_dimension: Mapped[int] = mapped_column(nullable=False)
    image_max_size_kb: Mapped[int] = mapped_column(nullable=False)


class Ingredient(Base):
    # Kept in sync by hand with api/app/models/ingredient.py — see that module's docstring. The
    # worker is the only writer of this table (via nutrition_handlers.py); the api only reads it
    # to compute a recipe's nutrition totals.
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    calories_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    protein_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    sugars_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_per_100g: Mapped[float] = mapped_column(Float, nullable=False)


class RecipeIngredientLink(Base):
    # Kept in sync by hand with api/app/models/recipe_ingredient_link.py — see that module's
    # docstring for the full "why this is stored" reasoning.
    __tablename__ = "recipe_ingredient_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    ingredient_index: Mapped[int] = mapped_column(Integer, nullable=False)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), nullable=False)

    raw_text: Mapped[str] = mapped_column(String(500), nullable=False)
    estimated_grams: Mapped[float] = mapped_column(Float, nullable=False)
    grams_source: Mapped[str] = mapped_column(String(20), nullable=False)


class NutritionJobStatus(str, enum.Enum):
    # Kept in sync by hand with api/app/models/nutrition_job.py's NutritionJobStatus.
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class NutritionJob(Base):
    __tablename__ = "nutrition_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[NutritionJobStatus] = mapped_column(
        Enum(NutritionJobStatus, native_enum=False), default=NutritionJobStatus.QUEUED
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngredientRefreshJobStatus(str, enum.Enum):
    # Kept in sync by hand with api/app/models/ingredient_refresh_job.py's
    # IngredientRefreshJobStatus.
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class IngredientRefreshJob(Base):
    __tablename__ = "ingredient_refresh_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[IngredientRefreshJobStatus] = mapped_column(
        Enum(IngredientRefreshJobStatus, native_enum=False),
        default=IngredientRefreshJobStatus.QUEUED,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingredients_updated: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
