import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
  owner_user_id: 1,
  owner_email: null,
  is_shared: true,
  import_reviewed_at: null,
  shared_from_recipe_id: null,
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
    total_grams: null,
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

  it("includes recipeYield and per-serving nutrition in JSON-LD once nutrition is enriched", async () => {
    mockedApi.getRecipe.mockResolvedValue(lemonTart);
    mockedApi.getNutrition.mockResolvedValue({
      status: "done",
      error: null,
      estimated_servings: 8,
      total_grams: 960,
      totals: { calories: 2160, protein_g: 24, carbs_g: 280, sugars_g: 200, fat_g: 96 },
      per_serving: { calories: 270, protein_g: 3, carbs_g: 35, sugars_g: 25, fat_g: 12 },
      per_ingredient: [],
    });

    renderAt("/en/recipes/1-lemon-tart");
    await screen.findByRole("heading", { name: "Lemon Tart" });

    const jsonLd = document.querySelector('script[type="application/ld+json"]');
    const data = JSON.parse(jsonLd!.textContent ?? "{}");
    expect(data.recipeYield).toBe("8");
    expect(data.nutrition).toEqual({
      "@type": "NutritionInformation",
      calories: "270 calories",
      proteinContent: "3 g",
      carbohydrateContent: "35 g",
      sugarContent: "25 g",
      fatContent: "12 g",
    });
  });

  it("omits recipeYield and nutrition from JSON-LD when nutrition isn't enriched yet", async () => {
    mockedApi.getRecipe.mockResolvedValue(lemonTart);
    // beforeEach's default mock already returns not_enriched/nulls.

    renderAt("/en/recipes/1-lemon-tart");
    await screen.findByRole("heading", { name: "Lemon Tart" });

    const jsonLd = document.querySelector('script[type="application/ld+json"]');
    const data = JSON.parse(jsonLd!.textContent ?? "{}");
    expect(data.recipeYield).toBeUndefined();
    expect(data.nutrition).toBeUndefined();
  });

  it("opens the send-to-a-friend dialog with the permanent public link, no sign-up needed", async () => {
    mockedApi.getRecipe.mockResolvedValue(lemonTart);
    const user = userEvent.setup();

    renderAt("/en/recipes/1-lemon-tart");
    await screen.findByRole("heading", { name: "Lemon Tart" });

    await user.click(screen.getByRole("button", { name: "Send to a friend" }));

    expect(await screen.findByText(/This recipe is public/)).toBeInTheDocument();
    expect(
      screen.getByDisplayValue(`${window.location.origin}/en/recipes/1-lemon-tart`)
    ).toBeInTheDocument();
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
