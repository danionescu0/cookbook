import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AccountPage } from "../account/AccountPage";
import { AuthProvider } from "../auth/AuthContext";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { Category, Recipe, UserProfile } from "../types";

vi.mock("../api/client", () => ({
  api: {
    me: vi.fn(),
    listFavorites: vi.fn(),
    listMySubmissions: vi.fn(),
    listCategories: vi.fn(),
    toggleShare: vi.fn(),
    updateRecipeCategory: vi.fn(),
    changePassword: vi.fn(),
    // ImportManager (rendered inside AccountPage) needs these too.
    listImportJobs: vi.fn(),
    createImportJob: vi.fn(),
    approveImportJob: vi.fn(),
    deleteImportJob: vi.fn(),
    getPublicSettings: vi.fn(),
    // PendingImportsPanel (also rendered inside AccountPage).
    acknowledgeImportedRecipe: vi.fn(),
    dismissFailedImport: vi.fn(),
  },
  BASE_URL: "http://localhost:8000",
  setAuthToken: vi.fn(),
  setUnauthorizedHandler: vi.fn(),
}));

const mockedApi = vi.mocked(api);

const profile: UserProfile = {
  id: 1,
  username: "someone",
  email: "someone@example.com",
  is_admin: false,
  is_super_admin: false,
  imported_recipes_count: 1,
};

const desserts: Category = { id: 1, name: "Desserts", slug: "desserts" };
const mains: Category = { id: 2, name: "Main courses", slug: "main-courses" };

const importedRecipe: Recipe = {
  id: 5,
  title: "Imported cake",
  slug: "imported-cake",
  description: "",
  ingredients: [],
  steps: [],
  tips: [],
  images: [],
  language: "en",
  category_id: 1,
  source_url: "https://example.com/cake",
  status: "approved",
  added_at: "2026-08-04T00:00:00Z",
  approved_at: "2026-08-04T00:00:00Z",
  available_languages: ["en"],
  processing_status: null,
  owner_username: "someone",
  is_shared: false,
  import_reviewed_at: "2026-08-04T00:00:00Z",
};

function renderPage() {
  return render(
    <LanguageProvider>
      <AuthProvider>
        <MemoryRouter>
          <AccountPage />
        </MemoryRouter>
      </AuthProvider>
    </LanguageProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mockedApi.me.mockResolvedValue(profile);
  mockedApi.listFavorites.mockResolvedValue([]);
  mockedApi.listMySubmissions.mockResolvedValue([importedRecipe]);
  mockedApi.listCategories.mockResolvedValue([desserts, mains]);
  mockedApi.listImportJobs.mockResolvedValue([]);
  mockedApi.getPublicSettings.mockResolvedValue({
    turnstile_site_key: "site-key",
    backoffice_recipes_page_size: 10,
    max_imports_per_user: 30,
  });
});

// The recipe card's own category selector shares its accessible name ("Category") with
// ImportManager's unrelated one, also rendered on this page — scope to the "My recipes" list
// (the only <ul> on the page, since both favorites and import jobs are empty in these tests) to
// disambiguate.
async function findRecipeCategorySelect() {
  const list = await screen.findByRole("list");
  return within(list).getByRole("combobox", { name: "Category" });
}

describe("AccountPage", () => {
  it("shows a category selector on an owned recipe, preselected to its current category", async () => {
    renderPage();

    const select = await findRecipeCategorySelect();
    expect(select).toHaveValue("1");
    expect(within(select).getByRole("option", { name: "Desserts" })).toBeInTheDocument();
    expect(within(select).getByRole("option", { name: "Main courses" })).toBeInTheDocument();
  });

  it("changes an imported recipe's category via the selector", async () => {
    mockedApi.updateRecipeCategory.mockResolvedValue({ ...importedRecipe, category_id: 2 });
    const user = userEvent.setup();

    renderPage();
    const select = await findRecipeCategorySelect();

    await user.selectOptions(select, "Main courses");

    expect(mockedApi.updateRecipeCategory).toHaveBeenCalledWith(5, 2);
    await waitFor(() => expect(select).toHaveValue("2"));
  });

  it("shows an error when changing the category fails", async () => {
    mockedApi.updateRecipeCategory.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();

    renderPage();
    const select = await findRecipeCategorySelect();

    await user.selectOptions(select, "Main courses");

    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });

  it("links an owned recipe to its edit page", async () => {
    renderPage();

    await findRecipeCategorySelect();
    expect(screen.getByRole("link", { name: "Edit" })).toHaveAttribute(
      "href",
      "/recipes/5/edit"
    );
  });

  it("shows a freshly-submitted import's recipe once it's created, without a page reload", async () => {
    // Reproduces a real report: the review panel only ever polled while it already knew about an
    // active job — a job submitted *after* the page loaded with nothing in flight was never
    // picked up at all. ImportManager's onJobCreated callback is what closes that gap.
    const user = userEvent.setup();
    const newRecipe: Recipe = {
      ...importedRecipe,
      id: 42,
      title: "Rulada de dovlecei",
      import_reviewed_at: null,
    };
    mockedApi.createImportJob.mockResolvedValue({
      id: 99,
      category_id: 1,
      type: "single",
      source: "https://example.com/new",
      status: "queued",
      error: null,
      error_kind: null,
      created_at: "2026-08-06T00:00:00Z",
      created_by_username: "someone",
      dismissed_at: null,
      admin_reviewed_at: null,
    });
    mockedApi.listMySubmissions
      .mockResolvedValueOnce([importedRecipe])
      .mockResolvedValue([importedRecipe, newRecipe]);

    renderPage();
    const urlInput = await screen.findByLabelText("Recipe URL");
    const importForm = urlInput.closest("form")!;

    await user.type(urlInput, "https://example.com/new");
    await user.selectOptions(within(importForm).getByLabelText("Category"), "Desserts");
    await user.click(within(importForm).getByRole("button", { name: "Add" }));

    expect((await screen.findAllByText("Rulada de dovlecei"))[0]).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "OK, got it" })).toBeInTheDocument();
  });
});
