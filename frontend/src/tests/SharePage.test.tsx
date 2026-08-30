import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AUTH_STORAGE_KEY, AuthProvider } from "../auth/AuthContext";
import { LanguageProvider } from "../i18n/LanguageContext";
import { SharePage } from "../sharing/SharePage";
import { clearPendingShareToken, getPendingShareToken } from "../sharing/pendingShare";
import { api } from "../api/client";
import type { Recipe, RecipeShareDetail, UserProfile } from "../types";

vi.mock("../api/client", () => ({
  api: {
    getRecipeShare: vi.fn(),
    copyRecipeShare: vi.fn(),
    getNutrition: vi.fn(),
    getPublicSettings: vi.fn(),
    me: vi.fn(),
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

const sharedRecipe: Recipe = {
  id: 5,
  title: "Brioșe cu dovleac",
  slug: "briose-cu-dovleac",
  description: "A pumpkin brioche.",
  ingredients: ["pumpkin", "flour"],
  steps: ["Mix", "Bake"],
  tips: [],
  images: ["/images/brioche.jpg"],
  language: "en",
  category_id: 1,
  source_url: null,
  status: "approved",
  added_at: "2026-08-20T00:00:00Z",
  approved_at: "2026-08-20T00:00:00Z",
  available_languages: ["en"],
  processing_status: null,
  owner_user_id: 1,
  owner_email: null,
  is_shared: false,
  import_reviewed_at: null,
  shared_from_recipe_id: null,
};

const activeExpiry = new Date(Date.now() + 20 * 60 * 60 * 1000).toISOString();

function teaserOnlyDetail(): RecipeShareDetail {
  return {
    status: "active",
    expires_at: activeExpiry,
    teaser: { title: "Brioșe cu dovleac", image: "/images/brioche.jpg", description: "A pumpkin brioche." },
    shared_by_email: null,
    recipe: null,
  };
}

function fullDetail(): RecipeShareDetail {
  return {
    status: "active",
    expires_at: activeExpiry,
    teaser: { title: "Brioșe cu dovleac", image: "/images/brioche.jpg", description: "A pumpkin brioche." },
    shared_by_email: "sender@example.com",
    recipe: sharedRecipe,
  };
}

function LocationDisplay() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}</span>;
}

function renderAt(path: string) {
  return render(
    <LanguageProvider>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <LocationDisplay />
          <Routes>
            <Route path="/share/:token" element={<SharePage />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </LanguageProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  // Not localStorage.clear() — the global setup.ts beforeEach (which runs before this one) sets
  // the language key to "en" for every test; clearing it out here would revert text assertions
  // to the Romanian default. Only reset what this file's own tests actually touch.
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  clearPendingShareToken();
  mockedApi.getPublicSettings.mockResolvedValue({
    turnstile_site_key: "site-key",
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
});

describe("SharePage", () => {
  it("shows the teaser and no recipe content while logged out", async () => {
    mockedApi.getRecipeShare.mockResolvedValue(teaserOnlyDetail());

    renderAt("/share/abc123");

    expect(await screen.findByText("Brioșe cu dovleac")).toBeInTheDocument();
    expect(screen.getByText("A pumpkin brioche.")).toBeInTheDocument();
    expect(screen.queryByText("Ingredients")).not.toBeInTheDocument();
    expect(screen.getByText("Create an account")).toBeInTheDocument();
    // Stashed so App.tsx's pending-share redirect can bring the visitor back here once they
    // finish signing up/logging in — see sharing/pendingShare.ts.
    await waitFor(() => expect(getPendingShareToken()).toBe("abc123"));
  });

  it("shows the full recipe and a working copy button once authenticated", async () => {
    window.localStorage.setItem(AUTH_STORAGE_KEY, "token");
    mockedApi.me.mockResolvedValue(profile);
    mockedApi.getRecipeShare.mockResolvedValue(fullDetail());
    mockedApi.copyRecipeShare.mockResolvedValue({ ...sharedRecipe, id: 99, owner_user_id: profile.id });
    const user = userEvent.setup();

    renderAt("/share/abc123");

    expect(await screen.findByRole("heading", { name: "Brioșe cu dovleac" })).toBeInTheDocument();
    expect(screen.getByText(/sender@example.com/)).toBeInTheDocument();
    expect(screen.getByText("Ingredients")).toBeInTheDocument();
    // No pending token needed once already authenticated.
    expect(getPendingShareToken()).toBeNull();

    await user.click(screen.getByRole("button", { name: "Copy to my recipes" }));

    await waitFor(() => expect(mockedApi.copyRecipeShare).toHaveBeenCalledWith("abc123"));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/recipes/99/edit"));
  });

  it("hides the copy button and shows a notice instead when the viewer owns the recipe", async () => {
    window.localStorage.setItem(AUTH_STORAGE_KEY, "token");
    mockedApi.me.mockResolvedValue(profile);
    mockedApi.getRecipeShare.mockResolvedValue({
      ...fullDetail(),
      recipe: { ...sharedRecipe, owner_user_id: profile.id },
    });

    renderAt("/share/abc123");

    await screen.findByRole("heading", { name: "Brioșe cu dovleac" });
    expect(screen.getByText("This is your own recipe.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copy to my recipes" })).not.toBeInTheDocument();
  });

  it("shows a single message for an expired link, hiding any recipe content", async () => {
    mockedApi.getRecipeShare.mockResolvedValue({
      status: "expired",
      expires_at: new Date(Date.now() - 1000).toISOString(),
      teaser: null,
      shared_by_email: null,
      recipe: null,
    });

    renderAt("/share/abc123");

    expect(await screen.findByText("This link has expired.")).toBeInTheDocument();
    expect(screen.queryByText("Brioșe cu dovleac")).not.toBeInTheDocument();
  });

  it("shows a single message for a revoked link", async () => {
    mockedApi.getRecipeShare.mockResolvedValue({
      status: "revoked",
      expires_at: activeExpiry,
      teaser: null,
      shared_by_email: null,
      recipe: null,
    });

    renderAt("/share/abc123");

    expect(await screen.findByText("This link was revoked by its sender.")).toBeInTheDocument();
  });
});
