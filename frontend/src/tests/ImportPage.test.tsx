import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ImportPage } from "../account/ImportPage";
import { AuthProvider } from "../auth/AuthContext";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { Category, Recipe, UserProfile } from "../types";

vi.mock("../api/client", () => ({
  api: {
    me: vi.fn(),
    listMySubmissions: vi.fn(),
    listCategories: vi.fn(),
    toggleShare: vi.fn(),
    updateRecipeCategory: vi.fn(),
    deleteRecipe: vi.fn(),
    // ImportManager (rendered inside ImportPage) needs these too.
    listImportJobs: vi.fn(),
    createImportJob: vi.fn(),
    approveImportJob: vi.fn(),
    deleteImportJob: vi.fn(),
    getPublicSettings: vi.fn(),
    // PendingImportsPanel (also rendered inside ImportPage).
    acknowledgeImportedRecipe: vi.fn(),
    dismissFailedImport: vi.fn(),
    // BookmarkImportPanel (also rendered inside ImportPage).
    parseBookmarkFile: vi.fn(),
    importBookmarkSelection: vi.fn(),
  },
  BASE_URL: "http://localhost:8000",
  setAuthToken: vi.fn(),
  setUnauthorizedHandler: vi.fn(),
}));

const mockedApi = vi.mocked(api);

const profile: UserProfile = {
  id: 1,
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
  owner_user_id: 1,
  owner_email: null,
  is_shared: false,
  import_reviewed_at: "2026-08-04T00:00:00Z",
  shared_from_recipe_id: null,
};

function renderPage() {
  return render(
    <LanguageProvider>
      <AuthProvider>
        <MemoryRouter>
          <ImportPage />
        </MemoryRouter>
      </AuthProvider>
    </LanguageProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mockedApi.me.mockResolvedValue(profile);
  mockedApi.listMySubmissions.mockResolvedValue([importedRecipe]);
  mockedApi.listCategories.mockResolvedValue([desserts, mains]);
  mockedApi.listImportJobs.mockResolvedValue([]);
  mockedApi.getPublicSettings.mockResolvedValue({
    turnstile_site_key: "site-key",
    google_client_id: "",
    backoffice_recipes_page_size: 10,
    max_imports_per_user: 30,
  });
});

// The recipe card's own category selector shares its accessible name ("Category") with
// ImportManager's unrelated one, also rendered on this page — scope to the "My recipes" list
// (the only <ul> on the page, since import jobs are empty in these tests) to disambiguate.
async function findRecipeCategorySelect() {
  const list = await screen.findByRole("list");
  return within(list).getByRole("combobox", { name: "Category" });
}

describe("ImportPage", () => {
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

  it("asks for confirmation, then deletes an owned recipe once confirmed", async () => {
    const user = userEvent.setup();
    mockedApi.deleteRecipe.mockResolvedValue(undefined);

    renderPage();
    await findRecipeCategorySelect();

    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(mockedApi.deleteRecipe).not.toHaveBeenCalled();

    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(mockedApi.deleteRecipe).toHaveBeenCalledWith(5));
    expect(screen.queryByText("Imported cake")).not.toBeInTheDocument();
  });

  it("does not delete a recipe when the confirm dialog is dismissed", async () => {
    const user = userEvent.setup();

    renderPage();
    await findRecipeCategorySelect();

    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));

    expect(mockedApi.deleteRecipe).not.toHaveBeenCalled();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(screen.getAllByText("Imported cake").length).toBeGreaterThan(0);
  });

  it("shows an error when deleting a recipe fails", async () => {
    const user = userEvent.setup();
    mockedApi.deleteRecipe.mockRejectedValue(new Error("boom"));

    renderPage();
    await findRecipeCategorySelect();

    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
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
      category_id: null,
      type: "single",
      source: "https://example.com/new",
      status: "queued",
      error: null,
      error_kind: null,
      created_at: "2026-08-06T00:00:00Z",
      created_by_user_id: 1,
      created_by_email: null,
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
    await user.click(within(importForm).getByRole("button", { name: "Add" }));

    expect((await screen.findAllByText("Rulada de dovlecei"))[0]).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "OK, got it" })).toBeInTheDocument();
  });

  it("filters the recipe list client-side 1.5s after typing 3+ characters", async () => {
    const soup: Recipe = { ...importedRecipe, id: 6, title: "Soup deluxe" };
    mockedApi.listMySubmissions.mockResolvedValue([importedRecipe, soup]);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    renderPage();
    await screen.findAllByText("Imported cake");
    expect(screen.getAllByText("Soup deluxe").length).toBeGreaterThan(0);

    await user.type(screen.getByPlaceholderText("Search by title…"), "sou");
    await act(() => vi.advanceTimersByTimeAsync(1500));

    expect(screen.queryByText("Imported cake")).not.toBeInTheDocument();
    expect(screen.getAllByText("Soup deluxe").length).toBeGreaterThan(0);

    vi.useRealTimers();
  });

  it("ignores diacritics in both directions", async () => {
    const cake: Recipe = { ...importedRecipe, id: 7, title: "Brioșe cu dovleac" };
    mockedApi.listMySubmissions.mockResolvedValue([cake]);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    renderPage();
    await screen.findAllByText("Brioșe cu dovleac");

    await user.type(screen.getByPlaceholderText("Search by title…"), "briose");
    await act(() => vi.advanceTimersByTimeAsync(1500));

    expect(screen.getAllByText("Brioșe cu dovleac").length).toBeGreaterThan(0);
    expect(screen.queryByText("No recipes match your search.")).not.toBeInTheDocument();

    vi.useRealTimers();
  });

  it("shows a no-results message when the search matches nothing, keeping the recipes present", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    renderPage();
    await screen.findAllByText("Imported cake");

    await user.type(screen.getByPlaceholderText("Search by title…"), "xyz");
    await act(() => vi.advanceTimersByTimeAsync(1500));

    expect(await screen.findByText("No recipes match your search.")).toBeInTheDocument();
    expect(screen.queryByText("Imported cake")).not.toBeInTheDocument();

    vi.useRealTimers();
  });
});
