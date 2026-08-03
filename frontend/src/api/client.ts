import type {
  Category,
  ImportJob,
  IngredientRefreshJob,
  IngredientRefreshStatus,
  LoginResponse,
  Nutrition,
  PublicLanguages,
  PublicSettings,
  Recipe,
  RecipeDraft,
  RecipesPage,
  RecipeUpdate,
  Settings,
  SettingsUpdate,
  SignupRequest,
  UserProfile,
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

function createRecipeRequest(draft: RecipeDraft): Promise<Recipe> {
  return request<Recipe>("/recipes", { method: "POST", body: JSON.stringify(draft) });
}

// Separate from `request` (which discards headers) because pagination needs the total match
// count from X-Total-Count, not just the page's own items — see routers/recipes.py's
// list_recipes. Exposed to browser JS via the API's CORS expose_headers config.
async function requestRecipesPage(params: URLSearchParams): Promise<RecipesPage> {
  const headers: Record<string, string> = {};
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  const response = await fetch(`${BASE_URL}/recipes?${params.toString()}`, { headers });

  if (!response.ok) {
    if (response.status === 401) onUnauthorized?.();
    const body = await response.text();
    throw new Error(extractErrorMessage(body) ?? `Request failed (${response.status})`);
  }

  const items = (await response.json()) as Recipe[];
  const totalHeader = response.headers.get("X-Total-Count");
  return { items, total: totalHeader !== null ? Number(totalHeader) : items.length };
}

export const api = {
  login: (username: string, password: string) =>
    request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  signup: (payload: SignupRequest) =>
    request<{ detail: string }>("/auth/signup", { method: "POST", body: JSON.stringify(payload) }),
  verifyEmail: (token: string) =>
    request<{ detail: string }>("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  resendVerification: (username: string, turnstileToken: string) =>
    request<{ detail: string }>("/auth/resend-verification", {
      method: "POST",
      body: JSON.stringify({ username, turnstile_token: turnstileToken }),
    }),
  me: () => request<UserProfile>("/users/me"),
  changePassword: (currentPassword: string, newPassword: string) =>
    request<void>("/users/me/password", {
      method: "PATCH",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),
  getPublicSettings: () => request<PublicSettings>("/settings/public"),
  getLanguages: () => request<PublicLanguages>("/languages"),

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
  listRecipesPage: (params: {
    categoryId?: number;
    language?: string;
    owner?: "me";
    onlyPublic?: boolean;
    limit: number;
    offset: number;
  }): Promise<RecipesPage> => {
    const query = new URLSearchParams();
    if (params.categoryId !== undefined) query.set("category_id", String(params.categoryId));
    if (params.language) query.set("language", params.language);
    if (params.owner) query.set("owner", params.owner);
    if (params.onlyPublic) query.set("only_public", "true");
    query.set("limit", String(params.limit));
    query.set("offset", String(params.offset));
    return requestRecipesPage(query);
  },
  getRecipe: (id: number, language?: string) =>
    request<Recipe>(`/recipes/${id}${language ? `?language=${language}` : ""}`),
  createRecipe: createRecipeRequest,
  // Same endpoint as createRecipe — the recipe lands owned by whoever's logged in, private
  // unless is_shared was requested (see api/app/routers/recipes.py). Named separately here so
  // call sites read as what they mean, not just how they're implemented.
  submitRecipe: createRecipeRequest,
  updateRecipe: (id: number, patch: RecipeUpdate, language?: string) =>
    request<Recipe>(`/recipes/${id}${language ? `?language=${language}` : ""}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  deleteRecipe: (id: number) => request<void>(`/recipes/${id}`, { method: "DELETE" }),
  approveRecipe: (id: number) => request<Recipe>(`/recipes/${id}/approve`, { method: "POST" }),
  toggleShare: (id: number, isShared: boolean) =>
    request<Recipe>(`/recipes/${id}/share`, {
      method: "PATCH",
      body: JSON.stringify({ is_shared: isShared }),
    }),
  favoriteRecipe: (id: number) => request<void>(`/recipes/${id}/favorite`, { method: "POST" }),
  unfavoriteRecipe: (id: number) => request<void>(`/recipes/${id}/favorite`, { method: "DELETE" }),
  listFavorites: () => request<Recipe[]>("/users/me/favorites"),
  listMySubmissions: () => request<Recipe[]>("/users/me/submissions"),

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
