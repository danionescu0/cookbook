import enum
from datetime import datetime

from sqlalchemy import Boolean, JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)


class ImportJobType(str, enum.Enum):
    SINGLE = "single"
    BULK = "bulk"
    BOOKMARK = "bookmark"
    INSTAGRAM = "instagram"


class ImportErrorKind(str, enum.Enum):
    # Kept in sync by hand with api/app/models/import_job.py's ImportErrorKind — see the
    # "Worker/API code sharing" design decision.
    DISALLOWED = "disallowed"
    NOT_A_RECIPE = "not_a_recipe"
    TECHNICAL = "technical"


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
    category_id: Mapped[int | None] = mapped_column(nullable=True)
    type: Mapped[ImportJobType] = mapped_column(
        Enum(ImportJobType, native_enum=False), default=ImportJobType.SINGLE
    )
    source: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[ImportJobStatus] = mapped_column(
        Enum(ImportJobStatus, native_enum=False), default=ImportJobStatus.QUEUED
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_kind: Mapped[ImportErrorKind | None] = mapped_column(
        Enum(ImportErrorKind, native_enum=False), nullable=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    import_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    slug: Mapped[str] = mapped_column(String(110), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    ingredients: Mapped[list[str]] = mapped_column(JSON, default=list)
    steps: Mapped[list[str]] = mapped_column(JSON, default=list)
    tips: Mapped[list[str]] = mapped_column(JSON, default=list)

    recipe: Mapped["Recipe"] = relationship(back_populates="translations")


class RecipeReparseJobStatus(str, enum.Enum):
    # Kept in sync by hand with api/app/models/recipe_reparse_job.py's RecipeReparseJobStatus.
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class RecipeReparseJob(Base):
    __tablename__ = "recipe_reparse_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[RecipeReparseJobStatus] = mapped_column(
        Enum(RecipeReparseJobStatus, native_enum=False), default=RecipeReparseJobStatus.QUEUED
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppSettings(Base):
    # Kept in sync by hand with api/app/models/app_settings.py — see that module's docstring
    # for what each column means. The worker only ever reads this table (via
    # app.settings_service.get_settings); api owns writes and the migration that creates/seeds
    # it. Same "kept in sync by hand" caveat as ImportJobStatus above.
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    supported_languages: Mapped[str] = mapped_column(String(100), nullable=False)
    default_language: Mapped[str] = mapped_column(String(10), nullable=False)
    anthropic_api_key: Mapped[str] = mapped_column(String(200), nullable=False)
    calorie_ninjas_api_key: Mapped[str] = mapped_column(String(200), nullable=False)
    default_rate_limit_requests_per_minute: Mapped[int] = mapped_column(nullable=False)
    scrape_timeout_seconds: Mapped[float] = mapped_column(nullable=False)
    max_html_chars: Mapped[int] = mapped_column(nullable=False)
    image_max_dimension: Mapped[int] = mapped_column(nullable=False)
    image_max_size_kb: Mapped[int] = mapped_column(nullable=False)
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_port: Mapped[int] = mapped_column(nullable=False)
    smtp_username: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_password: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_from_address: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, nullable=False)
    turnstile_site_key: Mapped[str] = mapped_column(String(255), nullable=False)
    turnstile_secret_key: Mapped[str] = mapped_column(String(255), nullable=False)
    public_site_url: Mapped[str] = mapped_column(String(255), nullable=False)
    # Where handle_contact_message_job (contact_handlers.py) sends a submission notification —
    # blank means not configured yet, handled as a clean job failure, not a crash.
    contact_recipient_email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # Which LLM provider claude_client.py's calls use ("claude" or "deepseek") — see that
    # module's docstring.
    preferred_ai_provider: Mapped[str] = mapped_column(String(20), nullable=False, default="claude")
    deepseek_api_key: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    google_client_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")


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


class TranslationSyncJobStatus(str, enum.Enum):
    # Kept in sync by hand with api/app/models/translation_sync_job.py's TranslationSyncJobStatus.
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class TranslationSyncJob(Base):
    __tablename__ = "translation_sync_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    source_language: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[TranslationSyncJobStatus] = mapped_column(
        Enum(TranslationSyncJobStatus, native_enum=False), default=TranslationSyncJobStatus.QUEUED
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    # Kept in sync by hand with api/app/models/user.py. Mostly read-only from the worker's side
    # (to find the recipient's email address for a queued EmailJob) — one exception:
    # imported_recipes_count is incremented here, in _finish_import, since a successful import
    # is only known at the end of the worker's fetch/extract/image pipeline. It's a lifetime
    # counter, never decremented, so deleting the resulting recipe never frees up quota.
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    imported_recipes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # The language to send account emails in — see api/app/models/user.py's User.language.
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="ro")


class EmailJobStatus(str, enum.Enum):
    # Kept in sync by hand with api/app/models/email_job.py's EmailJobStatus.
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class EmailJob(Base):
    __tablename__ = "email_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[EmailJobStatus] = mapped_column(
        Enum(EmailJobStatus, native_enum=False), default=EmailJobStatus.QUEUED
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmailVerificationToken(Base):
    # Kept in sync by hand with api/app/models/email_verification_token.py — the worker only
    # reads the newest unused token for a user to build the link inside a verification email.
    __tablename__ = "email_verification_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PasswordResetToken(Base):
    # Kept in sync by hand with api/app/models/password_reset_token.py — the worker only reads
    # the newest unused token for a user to build the link inside a password-reset email.
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContactMessageStatus(str, enum.Enum):
    # Kept in sync by hand with api/app/models/contact_message.py's ContactMessageStatus.
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class ContactMessage(Base):
    # Kept in sync by hand with api/app/models/contact_message.py — the worker only reads this
    # row (name/email/phone/message) to build the notification email and writes back
    # status/error; the api owns creation.
    __tablename__ = "contact_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[ContactMessageStatus] = mapped_column(
        Enum(ContactMessageStatus, native_enum=False), default=ContactMessageStatus.QUEUED
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
