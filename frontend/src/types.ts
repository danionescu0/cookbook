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
