import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { UsersManager } from "../backoffice/UsersManager";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { Recipe, RecipesPage, UserAdmin } from "../types";

vi.mock("../api/client", () => ({
  api: {
    listUsers: vi.fn(),
    listRecipesPage: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

const alice: UserAdmin = {
  id: 1,
  username: "alice",
  email: "alice@example.com",
  is_verified: true,
  created_at: "2026-07-01T00:00:00Z",
  last_login_at: "2026-08-01T00:00:00Z",
  imported_recipes_count: 4,
  owned_recipes_count: 6,
  shared_recipes_count: 2,
};

const bob: UserAdmin = {
  id: 2,
  username: "bob",
  email: null,
  is_verified: false,
  created_at: "2026-07-15T00:00:00Z",
  last_login_at: null,
  imported_recipes_count: 0,
  owned_recipes_count: 0,
  shared_recipes_count: 0,
};

function recipe(overrides: Partial<Recipe> = {}): Recipe {
  return {
    id: 1,
    title: "Cake",
    slug: "cake",
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
    processing_status: null,
    owner_username: "alice",
    is_shared: false,
    import_reviewed_at: null,
    ...overrides,
  };
}

function page(items: Recipe[], total = items.length): RecipesPage {
  return { items, total };
}

function renderManager() {
  return render(
    <LanguageProvider>
      <UsersManager />
    </LanguageProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("UsersManager", () => {
  it("lists users with their stats", async () => {
    mockedApi.listUsers.mockResolvedValue([alice, bob]);

    renderManager();

    expect(await screen.findByText("alice")).toBeInTheDocument();
    const aliceRow = screen.getByText("alice").closest("tr")!;
    expect(within(aliceRow).getByText("alice@example.com")).toBeInTheDocument();
    expect(within(aliceRow).getByText("Confirmed")).toBeInTheDocument();
    expect(within(aliceRow).getByText("4")).toBeInTheDocument();
    expect(within(aliceRow).getByText("6")).toBeInTheDocument();
    expect(within(aliceRow).getByText("2")).toBeInTheDocument();

    const bobRow = screen.getByText("bob").closest("tr")!;
    expect(within(bobRow).getByText("—")).toBeInTheDocument();
    expect(within(bobRow).getByText("Unconfirmed")).toBeInTheDocument();
    expect(within(bobRow).getByText("Never")).toBeInTheDocument();
  });

  it("shows an error when the user list fails to load", async () => {
    mockedApi.listUsers.mockRejectedValue(new Error("boom"));

    renderManager();

    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });

  it("expands a user's recipes on demand, paginated 10 at a time", async () => {
    mockedApi.listUsers.mockResolvedValue([alice]);
    mockedApi.listRecipesPage.mockResolvedValue(
      page([recipe({ id: 1, title: "Soup" }), recipe({ id: 2, title: "Salad", is_shared: true })], 15)
    );
    const user = userEvent.setup();

    renderManager();
    await screen.findByText("alice");

    await user.click(screen.getByRole("button", { name: "Show recipes" }));

    expect(await screen.findByText("Soup")).toBeInTheDocument();
    expect(screen.getByText("Salad")).toBeInTheDocument();
    expect(mockedApi.listRecipesPage).toHaveBeenCalledWith({
      owner: "alice",
      limit: 10,
      offset: 0,
    });
    // 15 total at 10/page is 2 pages, so pagination controls should appear.
    expect(screen.getByRole("navigation", { name: "Recipe pages" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() =>
      expect(mockedApi.listRecipesPage).toHaveBeenCalledWith({
        owner: "alice",
        limit: 10,
        offset: 10,
      })
    );
  });

  it("collapses a user's recipes when toggled again", async () => {
    mockedApi.listUsers.mockResolvedValue([alice]);
    mockedApi.listRecipesPage.mockResolvedValue(page([recipe({ title: "Soup" })]));
    const user = userEvent.setup();

    renderManager();
    await screen.findByText("alice");

    await user.click(screen.getByRole("button", { name: "Show recipes" }));
    await screen.findByText("Soup");

    await user.click(screen.getByRole("button", { name: "Hide recipes" }));

    expect(screen.queryByText("Soup")).not.toBeInTheDocument();
  });

  it("shows a message when the expanded user has no recipes", async () => {
    mockedApi.listUsers.mockResolvedValue([bob]);
    mockedApi.listRecipesPage.mockResolvedValue(page([]));
    const user = userEvent.setup();

    renderManager();
    await screen.findByText("bob");

    await user.click(screen.getByRole("button", { name: "Show recipes" }));

    expect(await screen.findByText("This user has no recipes.")).toBeInTheDocument();
  });
});
