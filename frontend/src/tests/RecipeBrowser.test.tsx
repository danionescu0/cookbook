import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RecipeBrowser } from "../frontoffice/RecipeBrowser";
import { AuthProvider, AUTH_STORAGE_KEY } from "../auth/AuthContext";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { Category, Recipe } from "../types";

vi.mock("../api/client", () => ({
  api: {
    listCategories: vi.fn(),
    listRecipes: vi.fn(),
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

const desserts: Category = { id: 1, name: "Desserts", slug: "desserts" };
const mains: Category = { id: 2, name: "Mains", slug: "mains" };

const cake: Recipe = {
  id: 1,
  title: "Cake",
  description: "A rich chocolate cake.",
  ingredients: ["flour"],
  steps: ["bake"],
  tips: [],
  images: ["/images/cake.jpg"],
  language: "en",
  category_id: 1,
  source_url: null,
  status: "approved",
  added_at: "2026-07-23T00:00:00Z",
  approved_at: "2026-07-23T00:00:00Z",
  available_languages: ["en"],
  processing_status: null,
  // The API already scopes the response to what this viewer may see — the frontend just needs
  // to split it, not re-filter it. Owned by someone else so it lands in "From the community"
  // for the logged-in "someone" user used below.
  owner_username: "admin",
  is_shared: true,
};

const soup: Recipe = {
  ...cake,
  id: 2,
  title: "Soup",
  owner_username: "someone",
  is_shared: false,
};

beforeEach(() => {
  vi.resetAllMocks();
  // Not localStorage.clear() — that would also wipe the language key the global test setup
  // seeds in its own beforeEach (see src/tests/setup.ts), which runs before this one.
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  mockedApi.listCategories.mockResolvedValue([desserts, mains]);
  mockedApi.listRecipes.mockResolvedValue([cake, soup]);
});

function renderBrowser() {
  return render(
    <LanguageProvider>
      <AuthProvider>
        <MemoryRouter>
          <RecipeBrowser />
        </MemoryRouter>
      </AuthProvider>
    </LanguageProvider>
  );
}

async function logInAs(username: string) {
  window.localStorage.setItem(AUTH_STORAGE_KEY, "a-token");
  mockedApi.me.mockResolvedValue({ id: 1, username, email: null, is_admin: false, is_super_admin: false });
  mockedApi.listFavorites.mockResolvedValue([]);
}

describe("RecipeBrowser", () => {
  it("links each recipe card to its detail page", async () => {
    renderBrowser();

    const link = (await screen.findByText("Cake")).closest("a");
    expect(link).toHaveAttribute("href", "/recipes/1");
  });

  it("filters by category when a pill is clicked", async () => {
    const user = userEvent.setup();
    renderBrowser();
    await screen.findByText("Cake");

    await user.click(screen.getByRole("button", { name: "Mains" }));

    await waitFor(() => expect(mockedApi.listRecipes).toHaveBeenCalledWith(2, "en"));
  });

  it("shows a single community section when logged out", async () => {
    renderBrowser();

    expect(await screen.findByText("Cake")).toBeInTheDocument();
    expect(screen.getByText("Soup")).toBeInTheDocument();
    expect(screen.queryByText("My recipes")).not.toBeInTheDocument();
    expect(screen.queryByText("From the community")).not.toBeInTheDocument();
  });

  it("splits recipes into my recipes and the community section when logged in", async () => {
    await logInAs("someone");

    renderBrowser();

    expect(await screen.findByText("My recipes")).toBeInTheDocument();
    expect(screen.getByText("From the community")).toBeInTheDocument();
    // "Soup" is owned by "someone" (the logged-in user) — the main section.
    const myRecipesHeading = screen.getByRole("heading", { name: "My recipes" });
    expect(myRecipesHeading.closest("section")).toHaveTextContent("Soup");
    // "Cake" is owned by "admin" — the community section.
    const communityHeading = screen.getByRole("heading", { name: "From the community" });
    expect(communityHeading.closest("section")).toHaveTextContent("Cake");
  });

  it("shows a favorite toggle when logged in and saves via the API", async () => {
    mockedApi.listRecipes.mockResolvedValue([cake]);
    await logInAs("someone");
    mockedApi.favoriteRecipe.mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderBrowser();
    await screen.findByText("Cake");

    const saveButton = await screen.findByRole("button", { name: "Save recipe" });
    await user.click(saveButton);

    await waitFor(() => expect(mockedApi.favoriteRecipe).toHaveBeenCalledWith(1));
  });

  it("does not show a favorite toggle when logged out", async () => {
    mockedApi.listRecipes.mockResolvedValue([cake]);
    renderBrowser();
    await screen.findByText("Cake");

    expect(screen.queryByRole("button", { name: "Save recipe" })).not.toBeInTheDocument();
  });
});
