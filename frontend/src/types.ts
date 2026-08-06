export interface Category {
  id: number;
  name: string;
  slug: string;
}

export type RecipeStatus = "unapproved" | "approved";

export type RecipeProcessingStatus = "translating" | "recalculating_nutrition" | "reparsing" | null;

export interface Recipe {
  id: number;
  title: string;
  // SEO URL segment for the resolved language, e.g. "lemon-tart" — combine with `id` to build
  // /{lang}/recipes/{id}-{slug}. See api's RecipeTranslation.slug docstring.
  slug: string;
  description: string;
  ingredients: string[];
  steps: string[];
  tips: string[];
  images: string[];
  language: string;
  category_id: number;
  source_url: string | null;
  status: RecipeStatus;
  added_at: string;
  approved_at: string | null;
  available_languages: string[];
  processing_status: RecipeProcessingStatus;
  // Every recipe has an owner now — private to them by default, see is_shared.
  owner_username: string;
  // Only ever true for a manually-added recipe (source_url is null) — imports are never
  // shareable. A shared recipe is only actually visible to everyone once status is "approved."
  is_shared: boolean;
  // Null until the owner acknowledges a just-finished import on the account page — drives the
  // post-import review panel. Always null for a manually-added recipe (source_url is null).
  import_reviewed_at: string | null;
}

export interface RecipesPage {
  items: Recipe[];
  total: number;
}

export interface ImportJobsPage {
  items: ImportJob[];
  total: number;
}

export type RecipeDraft = Pick<
  Recipe,
  | "title"
  | "description"
  | "ingredients"
  | "steps"
  | "tips"
  | "images"
  | "language"
  | "category_id"
  | "is_shared"
>;

export interface RecipeTranslationUpdate {
  title?: string;
  description?: string;
  ingredients?: string[];
  steps?: string[];
  tips?: string[];
}

export interface RecipeUpdate {
  category_id?: number;
  status?: RecipeStatus;
  images?: string[];
  translation?: RecipeTranslationUpdate;
}

export type ImportJobStatus =
  | "pending"
  | "queued"
  | "fetching"
  | "processing"
  | "done"
  | "failed";

export type ImportErrorKind = "disallowed" | "technical";

export interface ImportJob {
  id: number;
  category_id: number;
  type: "single" | "bulk" | "bookmark" | "instagram";
  source: string;
  status: ImportJobStatus;
  // Raw technical text — null for a non-admin caller (see api's routers/imports.py _serialize);
  // error_kind below is what a non-admin actually renders.
  error: string | null;
  error_kind: ImportErrorKind | null;
  created_at: string;
  // Whoever ran the import — the resulting recipe is always private to them, never shareable.
  created_by_username: string | null;
  // Set once the owner dismisses a failed job from their account page. Never populated/consulted
  // by the admin failed-imports page.
  dismissed_at: string | null;
  // Set once an admin marks a failed job as handled on the Failed Imports back office page.
  // Independent of dismissed_at — the owner's dismissal never sets this and vice versa.
  admin_reviewed_at: string | null;
}

export interface Settings {
  supported_languages: string;
  default_language: string;
  anthropic_api_key_is_set: boolean;
  calorie_ninjas_api_key_is_set: boolean;
  default_rate_limit_requests_per_minute: number;
  scrape_timeout_seconds: number;
  max_html_chars: number;
  image_max_dimension: number;
  image_max_size_kb: number;
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_from_address: string;
  smtp_password_is_set: boolean;
  smtp_use_tls: boolean;
  turnstile_site_key: string;
  turnstile_secret_key_is_set: boolean;
  public_site_url: string;
  backoffice_recipes_page_size: number;
  max_imports_per_user: number;
}

export interface SettingsUpdate {
  supported_languages?: string;
  default_language?: string;
  anthropic_api_key?: string;
  calorie_ninjas_api_key?: string;
  default_rate_limit_requests_per_minute?: number;
  scrape_timeout_seconds?: number;
  max_html_chars?: number;
  image_max_dimension?: number;
  image_max_size_kb?: number;
  smtp_host?: string;
  smtp_port?: number;
  smtp_username?: string;
  smtp_from_address?: string;
  // Omit or send "" to leave the current secret unchanged — the UI never has the real value.
  smtp_password?: string;
  smtp_use_tls?: boolean;
  turnstile_site_key?: string;
  turnstile_secret_key?: string;
  public_site_url?: string;
  backoffice_recipes_page_size?: number;
  max_imports_per_user?: number;
}

export interface PublicSettings {
  turnstile_site_key: string;
  backoffice_recipes_page_size: number;
  max_imports_per_user: number;
}

export interface PublicLanguages {
  supported: string[];
  default: string;
}

export interface User {
  id: number;
  username: string;
  is_admin: boolean;
  // Stricter than is_admin — only this tier can reach the Settings subpage.
  is_super_admin: boolean;
}

export interface UserProfile extends User {
  email: string | null;
  // Lifetime count of successful imports — meaningless for admins (exempt from the cap).
  imported_recipes_count: number;
}

export interface UserAdmin {
  id: number;
  username: string;
  email: string | null;
  is_verified: boolean;
  created_at: string;
  // Null if the account has never logged in since this column existed.
  last_login_at: string | null;
  // Lifetime count, not "currently owns" — see UserProfile.imported_recipes_count.
  imported_recipes_count: number;
  owned_recipes_count: number;
  shared_recipes_count: number;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface SignupRequest {
  username: string;
  email: string;
  password: string;
  turnstile_token: string;
  terms_accepted: boolean;
  language: string;
}

export type NutritionStatus = "not_enriched" | "queued" | "processing" | "done" | "failed";

export interface NutritionTotals {
  calories: number;
  protein_g: number;
  carbs_g: number;
  sugars_g: number;
  fat_g: number;
}

export interface NutritionIngredient {
  index: number;
  estimated_grams: number;
  grams_source: "api_lookup" | "claude_estimate";
}

export interface Nutrition {
  status: NutritionStatus;
  error: string | null;
  estimated_servings: number | null;
  // Sum of every per_ingredient estimated_grams — the finished dish's total weight, and what
  // estimated_servings is actually derived from.
  total_grams: number | null;
  totals: NutritionTotals | null;
  per_serving: NutritionTotals | null;
  per_ingredient: NutritionIngredient[];
}

export type IngredientRefreshState = "never_run" | "queued" | "processing" | "done" | "failed";

export interface IngredientRefreshStatus {
  status: IngredientRefreshState;
  error: string | null;
  ingredients_updated: number | null;
}

export interface IngredientRefreshJob {
  id: number;
  status: IngredientRefreshState;
  error: string | null;
  ingredients_updated: number | null;
}
