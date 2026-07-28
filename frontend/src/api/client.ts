import type {
  Category,
  ImportJob,
  IngredientRefreshJob,
  IngredientRefreshStatus,
  Nutrition,
  Recipe,
  RecipeDraft,
  RecipeUpdate,
  Settings,
  SettingsUpdate,
} from "../types";

export const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

let authToken: string | null = null;
let onUnauthorized: (() => void) | null = null;

// Set by AuthProvider on login/logout/mount-from-storage. Kept as module state (rather than
// threading a token through every api.xxx() call) so call sites don't change at all.
export function setAuthToken(token: string | null): void {
  authToken = token;
}

// Set by AuthProvider so an expired/invalid token clears itself out automatically instead of
// every protected form just showing "Invalid or expired token" forever until a manual re-login.
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

// FastAPI error bodies are `{"detail": "message"}` for our own HTTPExceptions, or
// `{"detail": [{"msg": "...", ...}, ...]}` for pydantic validation errors (422).
function extractErrorMessage(body: string): string | null {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail)) {
      return parsed.detail
        .map((entry) => (typeof entry?.msg === "string" ? entry.msg : null))
        .filter((msg): msg is string => msg !== null)
        .join("; ");
    }
  } catch {
    // not JSON — caller falls back to a generic message
  }
  return null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  const response = await fetch(`${BASE_URL}${path}`, { headers, ...init });

  if (!response.ok) {
    if (response.status === 401 && path !== "/auth/login") {
      onUnauthorized?.();
    }
    const body = await response.text();
    throw new Error(extractErrorMessage(body) ?? `Request failed (${response.status})`);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string; token_type: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  listCategories: () => request<Category[]>("/categories"),
  createCategory: (name: string) =>
    request<Category>("/categories", { method: "POST", body: JSON.stringify({ name }) }),
  deleteCategory: (id: number) => request<void>(`/categories/${id}`, { method: "DELETE" }),

  listRecipes: (categoryId?: number, language?: string) => {
    const params = new URLSearchParams();
    if (categoryId !== undefined) params.set("category_id", String(categoryId));
    if (language) params.set("language", language);
    const query = params.toString();
    return request<Recipe[]>(`/recipes${query ? `?${query}` : ""}`);
  },
  getRecipe: (id: number, language?: string) =>
    request<Recipe>(`/recipes/${id}${language ? `?language=${language}` : ""}`),
  createRecipe: (draft: RecipeDraft) =>
    request<Recipe>("/recipes", { method: "POST", body: JSON.stringify(draft) }),
  updateRecipe: (id: number, patch: RecipeUpdate, language?: string) =>
    request<Recipe>(`/recipes/${id}${language ? `?language=${language}` : ""}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  deleteRecipe: (id: number) => request<void>(`/recipes/${id}`, { method: "DELETE" }),
  approveRecipe: (id: number) => request<Recipe>(`/recipes/${id}/approve`, { method: "POST" }),

  // Multipart, not JSON — bypasses the `request` helper (which always sets
  // Content-Type: application/json) so the browser can set its own multipart boundary.
  uploadImage: async (file: File): Promise<{ url: string }> => {
    const formData = new FormData();
    formData.append("file", file);
    const headers: Record<string, string> = {};
    if (authToken) headers.Authorization = `Bearer ${authToken}`;

    const response = await fetch(`${BASE_URL}/images`, {
      method: "POST",
      headers,
      body: formData,
    });
    if (!response.ok) {
      if (response.status === 401) onUnauthorized?.();
      const body = await response.text();
      throw new Error(extractErrorMessage(body) ?? `Request failed (${response.status})`);
    }
    return (await response.json()) as { url: string };
  },

  listImportJobs: () => request<ImportJob[]>("/imports"),
  createImportJob: (source: string, categoryId: number) =>
    request<ImportJob>("/imports", {
      method: "POST",
      body: JSON.stringify({ source, category_id: categoryId }),
    }),
  approveImportJob: (id: number) =>
    request<ImportJob>(`/imports/${id}/approve`, { method: "POST" }),
  deleteImportJob: (id: number) => request<void>(`/imports/${id}`, { method: "DELETE" }),

  getSettings: () => request<Settings>("/settings"),
  updateSettings: (patch: SettingsUpdate) =>
    request<Settings>("/settings", { method: "PATCH", body: JSON.stringify(patch) }),

  getNutrition: (recipeId: number) => request<Nutrition>(`/recipes/${recipeId}/nutrition`),

  getIngredientRefreshStatus: () => request<IngredientRefreshStatus>("/ingredients/refresh"),
  createIngredientRefreshJob: () =>
    request<IngredientRefreshJob>("/ingredients/refresh", { method: "POST" }),
};
