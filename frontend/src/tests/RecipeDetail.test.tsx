import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RecipeDetail } from "../frontoffice/RecipeDetail";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { Recipe } from "../types";

vi.mock("../api/client", () => ({
  api: {
    getRecipe: vi.fn(),
    getNutrition: vi.fn(),
  },
  BASE_URL: "http://localhost:8000",
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
};

beforeEach(() => {
  vi.resetAllMocks();
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
      <MemoryRouter initialEntries={[`/recipes/${id}`]}>
        <Routes>
          <Route path="/recipes/:id" element={<RecipeDetail />} />
        </Routes>
      </MemoryRouter>
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
});
