import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RecipeBrowser } from "../frontoffice/RecipeBrowser";
import { AuthProvider, AUTH_STORAGE_KEY } from "../auth/AuthContext";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import { triggerIntersection } from "./testUtils/intersectionObserverMock";
import type { Category, Recipe, RecipesPage } from "../types";

vi.mock("../api/client", () => ({
  api: {
    listCategories: vi.fn(),
    listRecipesPage: vi.fn(),
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
  slug: "cake",
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
  owner_username: "admin",
  is_shared: true,
  import_reviewed_at: null,
};

const soup: Recipe = {
  ...cake,
  id: 2,
  title: "Soup",
  slug: "soup",
  owner_username: "someone",
  is_shared: false,
};

function page(items: Recipe[]): RecipesPage {
  return { items, total: items.length };
}

// Routes the mock by the same params RecipeBrowser actually sends: owner:"me" -> the "mine"
// feed, onlyPublic -> the community feed, neither -> the logged-out single public feed.
function mockFeeds(mine: Recipe[], communityOrPublic: Recipe[]) {
  mockedApi.listRecipesPage.mockImplementation((params) => {
    if (params.owner === "me") return Promise.resolve(page(params.offset === 0 ? mine : []));
    return Promise.resolve(page(params.offset === 0 ? communityOrPublic : []));
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  // Not localStorage.clear() — that would also wipe the language key the global test setup
  // seeds in its own beforeEach (see src/tests/setup.ts), which runs before this one.
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  mockedApi.listCategories.mockResolvedValue([desserts, mains]);
  mockFeeds([], [cake, soup]);
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
  mockedApi.me.mockResolvedValue({
    id: 1,
    username,
    email: null,
    is_admin: false,
    is_super_admin: false,
    imported_recipes_count: 0,
  });
  mockedApi.listFavorites.mockResolvedValue([]);
}

describe("RecipeBrowser", () => {
  it("links each recipe card to its detail page", async () => {
    renderBrowser();

    const link = (await screen.findByText("Cake")).closest("a");
    expect(link).toHaveAttribute("href", "/en/recipes/1-cake");
  });

  it("filters by category when a pill is clicked", async () => {
    const user = userEvent.setup();
    renderBrowser();
    await screen.findByText("Cake");

    await user.click(screen.getByRole("button", { name: "Mains" }));

    await waitFor(() =>
      expect(mockedApi.listRecipesPage).toHaveBeenCalledWith(
        expect.objectContaining({ categoryId: 2, language: "en" })
      )
    );
  });

  it("shows a single public feed with no My recipes/community split when logged out", async () => {
    renderBrowser();

    expect(await screen.findByText("Cake")).toBeInTheDocument();
    expect(screen.getByText("Soup")).toBeInTheDocument();
    expect(screen.queryByText("My recipes")).not.toBeInTheDocument();
    expect(screen.queryByText("From the community")).not.toBeInTheDocument();
  });

  it("splits recipes into my recipes and the community section when logged in", async () => {
    mockFeeds([soup], [cake, soup]);
    await logInAs("someone");

    renderBrowser();

    expect(await screen.findByText("My recipes")).toBeInTheDocument();
    expect(screen.getByText("From the community")).toBeInTheDocument();
    const myRecipesHeading = screen.getByRole("heading", { name: "My recipes" });
    expect(myRecipesHeading.closest("section")).toHaveTextContent("Soup");
    // "Soup" is owned by "someone" (the logged-in user) — even though the public feed also
    // returns it (it's shared), the community section must not show it a second time.
    const communityHeading = screen.getByRole("heading", { name: "From the community" });
    const communitySection = communityHeading.closest("section")!;
    expect(communitySection).toHaveTextContent("Cake");
    expect(communitySection).not.toHaveTextContent("Soup");
  });

  it("does not show the community section when it has nothing in it", async () => {
    mockFeeds([soup], []);
    await logInAs("someone");

    renderBrowser();

    expect(await screen.findByText("My recipes")).toBeInTheDocument();
    expect(screen.queryByText("From the community")).not.toBeInTheDocument();
    expect(screen.queryByText("Jump to community ↓")).not.toBeInTheDocument();
  });

  it("loads the next page of my recipes when the sentinel scrolls into view", async () => {
    // total larger than one page's worth so hasMore stays true after the first load
    mockedApi.listRecipesPage.mockImplementation((params) => {
      if (params.owner !== "me") return Promise.resolve(page([]));
      if (params.offset === 0) return Promise.resolve({ items: [soup], total: 2 });
      return Promise.resolve({ items: [{ ...cake, id: 3, title: "Third", slug: "third" }], total: 2 });
    });
    await logInAs("someone");

    renderBrowser();
    await screen.findByText("Soup");
    expect(screen.queryByText("Third")).not.toBeInTheDocument();

    act(() => triggerIntersection());

    expect(await screen.findByText("Third")).toBeInTheDocument();
  });

  it("shows a favorite toggle when logged in and saves via the API", async () => {
    mockFeeds([cake], []);
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
    mockFeeds([], [cake]);
    renderBrowser();
    await screen.findByText("Cake");

    expect(screen.queryByRole("button", { name: "Save recipe" })).not.toBeInTheDocument();
  });
});
