export interface Category {
  id: number;
  name: string;
  slug: string;
}

export type RecipeStatus = "unapproved" | "approved";

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
}

export type RecipeDraft = Pick<
  Recipe,
  "title" | "description" | "ingredients" | "steps" | "tips" | "images" | "language" | "category_id"
>;

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
  type: "single" | "bulk" | "bookmark";
  source: string;
  status: ImportJobStatus;
  error: string | null;
  created_at: string;
}

export interface Settings {
  supported_languages: string;
  default_language: string;
  admin_password_is_set: boolean;
  anthropic_api_key_is_set: boolean;
  default_rate_limit_requests_per_minute: number;
  scrape_timeout_seconds: number;
  max_html_chars: number;
  image_max_dimension: number;
  image_max_size_kb: number;
}

export interface SettingsUpdate {
  supported_languages?: string;
  default_language?: string;
  // Omit or send "" to leave the current secret unchanged — the UI never has the real value.
  admin_password?: string;
  anthropic_api_key?: string;
  default_rate_limit_requests_per_minute?: number;
  scrape_timeout_seconds?: number;
  max_html_chars?: number;
  image_max_dimension?: number;
  image_max_size_kb?: number;
}
