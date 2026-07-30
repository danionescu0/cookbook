export interface Category {
  id: number;
  name: string;
  slug: string;
}

export type RecipeStatus = "unapproved" | "approved";

export type RecipeProcessingStatus = "translating" | "recalculating_nutrition" | null;

export interface Recipe {
  id: number;
  title: string;
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

export interface ImportJob {
  id: number;
  category_id: number;
  type: "single" | "bulk" | "bookmark" | "instagram";
  source: string;
  status: ImportJobStatus;
  error: string | null;
  created_at: string;
  // Whoever ran the import — the resulting recipe is always private to them, never shareable.
  created_by_username: string | null;
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
}

export interface PublicSettings {
  turnstile_site_key: string;
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
