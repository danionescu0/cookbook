import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RecipeDetail } from "../frontoffice/RecipeDetail";
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

const cake: Recipe = {
  id: 1,
  title: "Cake",
  description: "A rich chocolate cake.",
  ingredients: ["flour", "sugar"],
  steps: ["Mix", "Bake"],
  tips: ["Let it cool before frosting"],
  images: ["/images/cake.jpg"],
  language: "en",
  category_id: 1,
  source_url: "https://example.com/cake",
  status: "approved",
  added_at: "2026-07-23T00:00:00Z",
  approved_at: "2026-07-23T00:00:00Z",
  available_languages: ["en"],
  processing_status: null,
  owner_username: "admin",
  is_shared: false,
};

beforeEach(() => {
  vi.resetAllMocks();
  // Not localStorage.clear() — that would also wipe the language key the global test setup
  // seeds in its own beforeEach (see src/tests/setup.ts), which runs before this one.
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  // Not under test here (see NutritionPanel.test.tsx) — just needs to resolve so RecipeDetail's
  // best-effort fetch doesn't reject.
  mockedApi.getNutrition.mockResolvedValue({
    status: "not_enriched",
    error: null,
    estimated_servings: null,
    totals: null,
    per_serving: null,
    per_ingredient: [],
  });
});

function renderDetail(id = "1") {
  return render(
    <LanguageProvider>
      <AuthProvider>
        <MemoryRouter initialEntries={[`/recipes/${id}`]}>
          <Routes>
            <Route path="/recipes/:id" element={<RecipeDetail />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </LanguageProvider>
  );
}

describe("RecipeDetail", () => {
  it("shows the recipe's full details once loaded", async () => {
    mockedApi.getRecipe.mockResolvedValue(cake);

    renderDetail();

    expect(await screen.findByRole("heading", { name: "Cake" })).toBeInTheDocument();
    expect(screen.getByText("A rich chocolate cake.")).toBeInTheDocument();
    expect(screen.getByText("flour")).toBeInTheDocument();
    expect(screen.getByText("Mix")).toBeInTheDocument();
    expect(screen.getByText("Let it cool before frosting")).toBeInTheDocument();
    expect(screen.getByAltText("Cake")).toHaveAttribute(
      "src",
      "http://localhost:8000/images/cake.jpg"
    );
    expect(mockedApi.getRecipe).toHaveBeenCalledWith(1, "en");
  });

  it("shows a not-published message for an unapproved recipe", async () => {
    mockedApi.getRecipe.mockResolvedValue({ ...cake, status: "unapproved" });

    renderDetail();

    expect(await screen.findByText("This recipe isn't published yet.")).toBeInTheDocument();
    expect(screen.queryByText("flour")).not.toBeInTheDocument();
  });

  it("shows an error when the recipe fails to load", async () => {
    mockedApi.getRecipe.mockRejectedValue(new Error("boom"));

    renderDetail();

    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });

  it("shows a favorite toggle when logged in and saves via the API", async () => {
    window.localStorage.setItem(AUTH_STORAGE_KEY, "a-token");
    mockedApi.me.mockResolvedValue({
      id: 1,
      username: "someone",
      email: null,
      is_admin: false,
      is_super_admin: false,
    });
    mockedApi.listFavorites.mockResolvedValue([]);
    mockedApi.favoriteRecipe.mockResolvedValue(undefined);
    mockedApi.getRecipe.mockResolvedValue(cake);
    const user = userEvent.setup();

    renderDetail();
    await screen.findByRole("heading", { name: "Cake" });

    const favoriteButton = await screen.findByRole("button", { name: "Save recipe" });
    await user.click(favoriteButton);

    await waitFor(() => expect(mockedApi.favoriteRecipe).toHaveBeenCalledWith(1));
  });

  it("does not show a favorite toggle when logged out", async () => {
    mockedApi.getRecipe.mockResolvedValue(cake);

    renderDetail();

    await screen.findByRole("heading", { name: "Cake" });
    expect(screen.queryByRole("button", { name: "Save recipe" })).not.toBeInTheDocument();
  });
});
