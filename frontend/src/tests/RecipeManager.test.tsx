import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RecipeManager } from "../backoffice/RecipeManager";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { Category, Recipe } from "../types";

vi.mock("../api/client", () => ({
  api: {
    listCategories: vi.fn(),
    listRecipes: vi.fn(),
    createRecipe: vi.fn(),
    deleteRecipe: vi.fn(),
    approveRecipe: vi.fn(),
  },
  BASE_URL: "http://localhost:8000",
}));

const mockedApi = vi.mocked(api);

const desserts: Category = { id: 1, name: "Desserts", slug: "desserts" };
const cake: Recipe = {
  id: 1,
  title: "Cake",
  description: "",
  ingredients: [],
  steps: [],
  tips: [],
  images: [],
  language: "en",
  category_id: 1,
  source_url: null,
  status: "approved",
  added_at: "2026-07-23T00:00:00Z",
  approved_at: "2026-07-23T00:00:00Z",
  available_languages: ["en"],
};
const pendingSoup: Recipe = {
  id: 2,
  title: "Soup",
  description: "A warm soup.",
  ingredients: ["Water", "Salt"],
  steps: ["Boil", "Serve"],
  tips: ["Add more salt to taste"],
  images: ["/images/soup.jpg"],
  language: "en",
  category_id: 1,
  source_url: "https://example.com/soup",
  status: "unapproved",
  added_at: "2026-07-23T00:00:00Z",
  approved_at: null,
  available_languages: ["en"],
};

beforeEach(() => {
  vi.resetAllMocks();
  mockedApi.listCategories.mockResolvedValue([desserts]);
  mockedApi.listRecipes.mockResolvedValue([cake]);
});

function renderManager() {
  return render(
    <LanguageProvider>
      <RecipeManager />
    </LanguageProvider>
  );
}

describe("RecipeManager", () => {
  it("lists recipes with their status", async () => {
    renderManager();

    expect(await screen.findByText(/Cake/)).toBeInTheDocument();
    expect(screen.getByText("(approved)")).toBeInTheDocument();
  });

  it("creates a recipe with ingredients split by line", async () => {
    const user = userEvent.setup();
    mockedApi.createRecipe.mockResolvedValue({ ...cake, id: 2, title: "Soup" });

    renderManager();
    await screen.findByText(/Cake/);

    await user.type(screen.getByLabelText("Title"), "Soup");
    await user.selectOptions(screen.getByLabelText("Category"), "Desserts");
    await user.type(screen.getByLabelText("Ingredients (one per line)"), "Water\nSalt");
    await user.click(screen.getByRole("button", { name: "Add recipe" }));

    await waitFor(() =>
      expect(mockedApi.createRecipe).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Soup",
          category_id: 1,
          ingredients: ["Water", "Salt"],
        })
      )
    );
  });

  it("deletes a recipe", async () => {
    const user = userEvent.setup();
    mockedApi.deleteRecipe.mockResolvedValue(undefined);

    renderManager();
    await screen.findByText(/Cake/);

    await user.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(mockedApi.deleteRecipe).toHaveBeenCalledWith(1));
  });

  it("shows an approve button only for unapproved recipes and calls the API", async () => {
    const user = userEvent.setup();
    mockedApi.listRecipes.mockResolvedValue([cake, pendingSoup]);
    mockedApi.approveRecipe.mockResolvedValue({ ...pendingSoup, status: "approved" });

    renderManager();
    await screen.findByText(/Cake/);

    expect(screen.getAllByRole("button", { name: "Approve" })).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(mockedApi.approveRecipe).toHaveBeenCalledWith(2));
  });

  it("toggles a preview showing the recipe's full details", async () => {
    const user = userEvent.setup();
    mockedApi.listRecipes.mockResolvedValue([pendingSoup]);

    renderManager();
    await screen.findByText(/Soup/);

    expect(screen.queryByText("A warm soup.")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Preview" }));

    expect(screen.getByText("A warm soup.")).toBeInTheDocument();
    expect(screen.getByText("Boil")).toBeInTheDocument();
    expect(screen.getByAltText("Soup")).toHaveAttribute(
      "src",
      "http://localhost:8000/images/soup.jpg"
    );

    await user.click(screen.getByRole("button", { name: "Hide preview" }));

    expect(screen.queryByText("A warm soup.")).not.toBeInTheDocument();
  });
});
