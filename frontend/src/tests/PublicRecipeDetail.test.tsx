import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PublicRecipeDetail } from "../frontoffice/PublicRecipeDetail";
import { AuthProvider, AUTH_STORAGE_KEY } from "../auth/AuthContext";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { Recipe } from "../types";

vi.mock("../api/client", () => ({
  api: {
    getRecipe: vi.fn(),
    getNutrition: vi.fn(),
    me: vi.fn(),
    listFavorites: vi.fn(),
    favoriteRecipe: vi.fn(),
    unfavoriteRecipe: vi.fn(),
  },
  BASE_URL: "http://localhost:8000",
  setAuthToken: vi.fn(),
  setUnauthorizedHandler: vi.fn(),
}));

const mockedApi = vi.mocked(api);

const lemonTart: Recipe = {
  id: 1,
  title: "Lemon Tart",
  slug: "lemon-tart",
  description: "A tangy dessert.",
  ingredients: ["lemon", "sugar"],
  steps: ["Mix", "Bake"],
  tips: [],
  images: ["/images/tart.jpg"],
  language: "en",
  category_id: 1,
  source_url: null,
  status: "approved",
  added_at: "2026-07-23T00:00:00Z",
  approved_at: "2026-07-23T00:00:00Z",
  available_languages: ["en"],
  processing_status: null,
  owner_username: "admin",
  is_shared: true,
};

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
            <Route path="/" element={<div data-testid="landing" />} />
            <Route path="/:lang/recipes/:idSlug" element={<PublicRecipeDetail />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </LanguageProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  mockedApi.getNutrition.mockResolvedValue({
    status: "not_enriched",
    error: null,
    estimated_servings: null,
    totals: null,
    per_serving: null,
    per_ingredient: [],
  });
});

describe("PublicRecipeDetail", () => {
  it("renders the recipe when the URL already has the canonical slug", async () => {
    mockedApi.getRecipe.mockResolvedValue(lemonTart);

    renderAt("/en/recipes/1-lemon-tart");

    expect(await screen.findByRole("heading", { name: "Lemon Tart" })).toBeInTheDocument();
    expect(mockedApi.getRecipe).toHaveBeenCalledWith(1, "en");
    expect(screen.getByTestId("location")).toHaveTextContent("/en/recipes/1-lemon-tart");
  });

  it("redirects a bare id to the canonical id-slug URL", async () => {
    mockedApi.getRecipe.mockResolvedValue(lemonTart);

    renderAt("/en/recipes/1");

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent("/en/recipes/1-lemon-tart")
    );
  });

  it("redirects a stale slug to the current one", async () => {
    mockedApi.getRecipe.mockResolvedValue(lemonTart);

    renderAt("/en/recipes/1-old-title");

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent("/en/recipes/1-lemon-tart")
    );
  });

  it("redirects to the landing page for an unsupported language code", async () => {
    renderAt("/xx/recipes/1-lemon-tart");

    await waitFor(() => expect(screen.getByTestId("landing")).toBeInTheDocument());
    expect(mockedApi.getRecipe).not.toHaveBeenCalled();
  });

  it("renders JSON-LD structured data and an indexable robots tag for a public recipe", async () => {
    mockedApi.getRecipe.mockResolvedValue(lemonTart);

    renderAt("/en/recipes/1-lemon-tart");
    await screen.findByRole("heading", { name: "Lemon Tart" });

    const jsonLd = document.querySelector('script[type="application/ld+json"]');
    expect(jsonLd).not.toBeNull();
    const data = JSON.parse(jsonLd!.textContent ?? "{}");
    expect(data["@type"]).toBe("Recipe");
    expect(data.name).toBe("Lemon Tart");
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute(
      "content",
      "index,follow"
    );
  });

  it("omits JSON-LD and sets noindex for a private recipe (visible only to its owner)", async () => {
    mockedApi.getRecipe.mockResolvedValue({ ...lemonTart, is_shared: false });

    renderAt("/en/recipes/1-lemon-tart");
    await screen.findByRole("heading", { name: "Lemon Tart" });

    expect(document.querySelector('script[type="application/ld+json"]')).toBeNull();
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute(
      "content",
      "noindex,nofollow"
    );
  });
});
