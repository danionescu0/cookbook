from datetime import datetime

from pydantic import BaseModel

from app.models.recipe import RecipeStatus


class RecipeCreate(BaseModel):
    category_id: int
    images: list[str] = []
    # Defaults to settings.default_language if omitted.
    language: str | None = None
    title: str
    description: str = ""
    ingredients: list[str] = []
    steps: list[str] = []
    tips: list[str] = []
    # Only meaningful for a manually-added recipe (this endpoint never sets source_url) — see
    # routers/recipes.py's create_recipe for what each caller (admin vs. regular user) does with
    # it.
    is_shared: bool = False


class RecipeTranslationUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    ingredients: list[str] | None = None
    steps: list[str] | None = None
    tips: list[str] | None = None


class RecipeUpdate(BaseModel):
    category_id: int | None = None
    status: RecipeStatus | None = None
    images: list[str] | None = None
    # Which translation this applies to comes from the `language` query param (same one GET
    # already uses to resolve a response) rather than a second field here — an earlier version
    # had both, and they could silently disagree (caught by a test where the query param and a
    # separate body field pointed at different languages, and the query param's language quietly
    # lost). One source of truth removes that whole failure mode.
    translation: RecipeTranslationUpdate | None = None


class RecipeShareUpdate(BaseModel):
    is_shared: bool


class RecipeCategoryUpdate(BaseModel):
    category_id: int


class RecipeRead(BaseModel):
    id: int
    category_id: int
    images: list[str]
    source_url: str | None
    status: RecipeStatus
    added_at: datetime
    approved_at: datetime | None

    # Resolved translation: `language` is what actually got returned, which may differ from what
    # was requested if that translation didn't exist (falls back to the site's default language).
    language: str
    title: str
    # SEO URL segment for this translation, e.g. "lemon-tart" — see
    # RecipeTranslation.slug for how/when it's generated. Combine with `id` to build
    # /{lang}/recipes/{id}-{slug}; the id is what's actually resolved server-side.
    slug: str
    description: str
    ingredients: list[str]
    steps: list[str]
    tips: list[str]
    available_languages: list[str]

    # "translating" | "recalculating_nutrition" | "reparsing" | None — set while a just-saved
    # edit is still being propagated to other languages, nutrition is being re-enriched, or a
    # reparse (re-scrape + re-extract) is in flight. See routers/recipes.py's
    # _processing_statuses.
    processing_status: str | None = None
    # Every recipe has an owner now (see migration 0020) — this is always set, not just for user
    # submissions. Safe to expose to anyone (just an id, used client-side for self/ownership
    # checks) — owner_email below is the sensitive one.
    owner_user_id: int
    # Only populated for an admin caller — see routers/recipes.py's _serialize, same nulling
    # pattern routers/imports.py already uses for a non-admin's ImportJobRead.error. A public or
    # non-owner caller must never learn another user's real email address.
    owner_email: str | None = None
    # True only for a manually-added recipe (never an import) whose owner opted to make it
    # visible to everyone once approved — see routers/recipes.py's visibility rule.
    is_shared: bool
    # Null until the owner acknowledges a just-finished import on the account page (see
    # routers/recipes.py's acknowledge_import) — drives the post-import review panel. Always null
    # for a manually-added recipe (source_url is None), which never shows that panel.
    import_reviewed_at: datetime | None
