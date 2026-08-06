import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RecipeEditPage } from "../account/RecipeEditPage";
import { AuthProvider, AUTH_STORAGE_KEY } from "../auth/AuthContext";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { Category, Recipe } from "../types";

vi.mock("../api/client", () => ({
  api: {
    me: vi.fn(),
    getRecipe: vi.fn(),
    listCategories: vi.fn(),
    updateRecipe: vi.fn(),
    uploadImage: vi.fn(),
  },
  BASE_URL: "http://localhost:8000",
  setAuthToken: vi.fn(),
  setUnauthorizedHandler: vi.fn(),
}));

const mockedApi = vi.mocked(api);

const desserts: Category = { id: 1, name: "Desserts", slug: "desserts" };
const mains: Category = { id: 2, name: "Main courses", slug: "main-courses" };

const cake: Recipe = {
  id: 1,
  title: "Imported cake",
  slug: "imported-cake",
  description: "A cake.",
  ingredients: ["flour", "sugar"],
  steps: ["Mix", "Bake"],
  tips: [],
  images: [],
  language: "en",
  category_id: 1,
  source_url: "https://example.com/cake",
  status: "approved",
  added_at: "2026-08-06T00:00:00Z",
  approved_at: "2026-08-06T00:00:00Z",
  available_languages: ["en"],
  processing_status: null,
  owner_username: "someone",
  is_shared: false,
  import_reviewed_at: null,
};

function logIn(username: string, isAdmin = false) {
  window.localStorage.setItem(AUTH_STORAGE_KEY, "a-token");
  mockedApi.me.mockResolvedValue({
    id: username === "someone" ? 2 : 3,
    username,
    email: null,
    is_admin: isAdmin,
    is_super_admin: false,
    imported_recipes_count: 0,
  });
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/recipes/1/edit"]}>
      <LanguageProvider>
        <AuthProvider>
          <Routes>
            <Route path="/recipes/:id/edit" element={<RecipeEditPage />} />
          </Routes>
        </AuthProvider>
      </LanguageProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  mockedApi.getRecipe.mockResolvedValue(cake);
  mockedApi.listCategories.mockResolvedValue([desserts, mains]);
});

describe("RecipeEditPage", () => {
  it("shows the recipe's current fields, preloaded", async () => {
    logIn("someone");
    renderPage();

    expect(await screen.findByDisplayValue("Imported cake")).toBeInTheDocument();
    expect(screen.getByDisplayValue("A cake.")).toBeInTheDocument();
  });

  it("denies access to a non-owner, non-admin viewer", async () => {
    logIn("someone-else");
    renderPage();

    expect(await screen.findByText("You don't have access to this page.")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("Imported cake")).not.toBeInTheDocument();
  });

  it("lets an admin edit a recipe they don't own", async () => {
    logIn("an-admin", true);
    renderPage();

    expect(await screen.findByDisplayValue("Imported cake")).toBeInTheDocument();
  });

  it("saves the edited fields and navigates back to the account page", async () => {
    logIn("someone");
    mockedApi.updateRecipe.mockResolvedValue({ ...cake, title: "Better cake" });
    const user = userEvent.setup();

    renderPage();
    const titleInput = await screen.findByDisplayValue("Imported cake");
    await user.clear(titleInput);
    await user.type(titleInput, "Better cake");

    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(mockedApi.updateRecipe).toHaveBeenCalledWith(
        1,
        expect.objectContaining({
          category_id: 1,
          translation: expect.objectContaining({ title: "Better cake" }),
        }),
        "en"
      )
    );
  });

  it("shows an error if saving fails", async () => {
    logIn("someone");
    mockedApi.updateRecipe.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();

    renderPage();
    await screen.findByDisplayValue("Imported cake");

    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });
});
