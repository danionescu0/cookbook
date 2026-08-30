import { StrictMode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { AUTH_STORAGE_KEY, AuthProvider } from "../auth/AuthContext";
import { LanguageProvider } from "../i18n/LanguageContext";
import { setPendingShareToken } from "../sharing/pendingShare";
import { api } from "../api/client";
import type { RecipeShareDetail, UserProfile } from "../types";

vi.mock("../api/client", () => ({
  api: {
    me: vi.fn(),
    getLanguages: vi.fn(),
    getRecipeShare: vi.fn(),
    copyRecipeShare: vi.fn(),
    getNutrition: vi.fn(),
    getPublicSettings: vi.fn(),
    listCategories: vi.fn(),
    listRecipesPage: vi.fn(),
    listFavorites: vi.fn(),
  },
  BASE_URL: "http://localhost:8000",
  setAuthToken: vi.fn(),
  setUnauthorizedHandler: vi.fn(),
}));

const mockedApi = vi.mocked(api);

const profile: UserProfile = {
  id: 2,
  email: "recipient@example.com",
  is_admin: false,
  is_super_admin: false,
  imported_recipes_count: 0,
};

function teaserOnlyDetail(): RecipeShareDetail {
  return {
    status: "active",
    expires_at: new Date(Date.now() + 20 * 60 * 60 * 1000).toISOString(),
    teaser: { title: "Lemon Tart", image: null, description: "" },
    shared_by_email: null,
    recipe: null,
  };
}

function LocationDisplay() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}</span>;
}

beforeEach(() => {
  vi.resetAllMocks();
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  mockedApi.getLanguages.mockRejectedValue(new Error("not mocked for this test"));
});

describe("post-auth redirect (App)", () => {
  // Reproduces a real bug: an earlier version redirected via a separate App()-level effect that
  // raced with the /login route's own <Navigate to="/">, and lost that race under StrictMode's
  // mount -> cleanup -> mount effect double-invocation — the second invocation re-read
  // localStorage *after* the first had already cleared it, saw nothing pending, and silently
  // redirected to "/" instead. Rendered under <StrictMode> here specifically because that's what
  // exposed it; a non-StrictMode render would pass even with the bug present.
  it("lands on the pending share page, not home, when already authenticated on /login under StrictMode", async () => {
    window.localStorage.setItem(AUTH_STORAGE_KEY, "token");
    mockedApi.me.mockResolvedValue(profile);
    mockedApi.getRecipeShare.mockResolvedValue(teaserOnlyDetail());
    mockedApi.getPublicSettings.mockResolvedValue({
      turnstile_site_key: "",
      google_client_id: "",
      backoffice_recipes_page_size: 10,
      max_imports_per_user: 30,
    });
    mockedApi.getNutrition.mockResolvedValue({
      status: "not_enriched",
      error: null,
      estimated_servings: null,
      total_grams: null,
      totals: null,
      per_serving: null,
      per_ingredient: [],
    });
    setPendingShareToken("abc123");

    render(
      <StrictMode>
        <LanguageProvider>
          <AuthProvider>
            <MemoryRouter initialEntries={["/login"]}>
              <LocationDisplay />
              <App />
            </MemoryRouter>
          </AuthProvider>
        </LanguageProvider>
      </StrictMode>
    );

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent("/share/abc123")
    );
    // Appears twice (the teaser tile's image-fallback text and its own heading) — see
    // SharePage.tsx's unauthenticated branch.
    expect((await screen.findAllByText("Lemon Tart")).length).toBeGreaterThan(0);
  });

  it("redirects to home when already authenticated on /login with no pending share", async () => {
    window.localStorage.setItem(AUTH_STORAGE_KEY, "token");
    mockedApi.me.mockResolvedValue(profile);
    mockedApi.listCategories.mockResolvedValue([]);
    mockedApi.listRecipesPage.mockResolvedValue({ items: [], total: 0 });
    mockedApi.listFavorites.mockResolvedValue([]);

    render(
      <StrictMode>
        <LanguageProvider>
          <AuthProvider>
            <MemoryRouter initialEntries={["/login"]}>
              <LocationDisplay />
              <App />
            </MemoryRouter>
          </AuthProvider>
        </LanguageProvider>
      </StrictMode>
    );

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/"));
  });
});
