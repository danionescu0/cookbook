import type { Category, ImportJob, Recipe, RecipeDraft } from "../types";

export const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

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
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(extractErrorMessage(body) ?? `Request failed (${response.status})`);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
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
  deleteRecipe: (id: number) => request<void>(`/recipes/${id}`, { method: "DELETE" }),
  approveRecipe: (id: number) => request<Recipe>(`/recipes/${id}/approve`, { method: "POST" }),

  listImportJobs: () => request<ImportJob[]>("/imports"),
  createImportJob: (source: string, categoryId: number) =>
    request<ImportJob>("/imports", {
      method: "POST",
      body: JSON.stringify({ source, category_id: categoryId }),
    }),
  approveImportJob: (id: number) =>
    request<ImportJob>(`/imports/${id}/approve`, { method: "POST" }),
  deleteImportJob: (id: number) => request<void>(`/imports/${id}`, { method: "DELETE" }),
};
