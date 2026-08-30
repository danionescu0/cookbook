import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RecipeManager } from "../backoffice/RecipeManager";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { Category, Recipe, RecipesPage } from "../types";

vi.mock("../api/client", () => ({
  api: {
    listCategories: vi.fn(),
    listRecipesPage: vi.fn(),
    getPublicSettings: vi.fn(),
    createRecipe: vi.fn(),
    updateRecipe: vi.fn(),
    uploadImage: vi.fn(),
    deleteRecipe: vi.fn(),
    approveRecipe: vi.fn(),
    toggleShare: vi.fn(),
    reparseRecipe: vi.fn(),
    reparseAllImportedRecipes: vi.fn(),
  },
  BASE_URL: "http://localhost:8000",
}));

const mockedApi = vi.mocked(api);

const desserts: Category = { id: 1, name: "Desserts", slug: "desserts" };
const cake: Recipe = {
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
  owner_user_id: 1,
  owner_email: null,
  is_shared: false,
  import_reviewed_at: null,
  shared_from_recipe_id: null,
};
const pendingSoup: Recipe = {
  id: 2,
  title: "Soup",
  slug: "soup",
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
  processing_status: null,
  owner_user_id: 1,
  owner_email: null,
  is_shared: false,
  import_reviewed_at: "2026-07-23T00:00:00Z",
  shared_from_recipe_id: null,
};

function page(items: Recipe[]): RecipesPage {
  return { items, total: items.length };
}

function mockRecipeList(items: Recipe[]) {
  mockedApi.listRecipesPage.mockResolvedValue(page(items));
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  mockedApi.listCategories.mockResolvedValue([desserts]);
  mockedApi.getPublicSettings.mockResolvedValue({
    turnstile_site_key: "",
    google_client_id: "",
    backoffice_recipes_page_size: 10,
    max_imports_per_user: 30,
  });
  mockRecipeList([cake]);
});

afterEach(() => {
  vi.useRealTimers();
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

  it("asks for confirmation, then deletes a recipe once confirmed", async () => {
    const user = userEvent.setup();
    mockedApi.deleteRecipe.mockResolvedValue(undefined);

    renderManager();
    await screen.findByText(/Cake/);

    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(mockedApi.deleteRecipe).not.toHaveBeenCalled();

    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(mockedApi.deleteRecipe).toHaveBeenCalledWith(1));
  });

  it("does not delete a recipe when the confirm dialog is dismissed", async () => {
    const user = userEvent.setup();

    renderManager();
    await screen.findByText(/Cake/);

    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));

    expect(mockedApi.deleteRecipe).not.toHaveBeenCalled();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("shows an approve button only for unapproved recipes and calls the API", async () => {
    const user = userEvent.setup();
    mockRecipeList([cake, pendingSoup]);
    mockedApi.approveRecipe.mockResolvedValue({ ...pendingSoup, status: "approved" });

    renderManager();
    await screen.findByText(/Cake/);

    expect(screen.getAllByRole("button", { name: "Approve" })).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(mockedApi.approveRecipe).toHaveBeenCalledWith(2));
  });

  it("toggles a preview showing the recipe's full details", async () => {
    const user = userEvent.setup();
    mockRecipeList([pendingSoup]);

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

  it("edits a recipe's text fields and saves via the API", async () => {
    const user = userEvent.setup();
    mockedApi.updateRecipe.mockResolvedValue({ ...cake, title: "Better Cake" });

    renderManager();
    await screen.findByText(/Cake/);

    await user.click(screen.getByRole("button", { name: "Edit" }));
    const titleInput = screen.getAllByDisplayValue("Cake")[0];
    await user.clear(titleInput);
    await user.type(titleInput, "Better Cake");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(mockedApi.updateRecipe).toHaveBeenCalledWith(
        1,
        expect.objectContaining({
          category_id: 1,
          images: [],
          translation: expect.objectContaining({ title: "Better Cake" }),
        }),
        expect.any(String)
      )
    );
  });

  it("uploads a pasted/selected image in edit mode and can remove it before saving", async () => {
    const user = userEvent.setup();
    mockedApi.uploadImage.mockResolvedValue({ url: "/images/new.jpg" });
    mockedApi.updateRecipe.mockResolvedValue(cake);

    renderManager();
    await screen.findByText(/Cake/);
    await user.click(screen.getByRole("button", { name: "Edit" }));

    const file = new File(["fake image bytes"], "photo.png", { type: "image/png" });
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(fileInput, file);

    await waitFor(() => expect(mockedApi.uploadImage).toHaveBeenCalledWith(file));
    const thumbnail = await screen.findByRole("button", { name: "Remove image" });
    expect(document.querySelector('img[src="http://localhost:8000/images/new.jpg"]')).toBeTruthy();

    await user.click(thumbnail);
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(mockedApi.updateRecipe).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ images: [] }),
        expect.any(String)
      )
    );
  });

  it("shares and unshares a manually-added recipe via the API", async () => {
    const user = userEvent.setup();
    mockedApi.toggleShare.mockResolvedValue({ ...cake, is_shared: true });

    renderManager();
    await screen.findByText(/Cake/);

    await user.click(screen.getByRole("button", { name: "Share with community" }));

    await waitFor(() => expect(mockedApi.toggleShare).toHaveBeenCalledWith(1, true));
  });

  it("does not show a share toggle for an imported recipe", async () => {
    mockRecipeList([pendingSoup]);

    renderManager();
    await screen.findByText(/Soup/);

    expect(screen.queryByRole("button", { name: "Share with community" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Make private" })).not.toBeInTheDocument();
  });

  it("shows the source URL as a link for an imported recipe, and nothing for a manual one", async () => {
    mockRecipeList([cake, pendingSoup]);

    renderManager();
    await screen.findByText(/Cake/);

    const sourceLink = screen.getByRole("link", { name: "imported from example.com" });
    expect(sourceLink).toHaveAttribute("href", "https://example.com/soup");
  });

  it("shows a Reparse button only for an imported recipe, and confirms before calling the API", async () => {
    const user = userEvent.setup();
    mockRecipeList([cake, pendingSoup]);
    mockedApi.reparseRecipe.mockResolvedValue({ job_id: 1 });

    renderManager();
    await screen.findByText(/Cake/);

    expect(screen.getAllByRole("button", { name: "Reparse" })).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "Reparse" }));
    expect(mockedApi.reparseRecipe).not.toHaveBeenCalled();

    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Reparse" }));

    await waitFor(() => expect(mockedApi.reparseRecipe).toHaveBeenCalledWith(2));
  });

  it("shows a processing-status badge and polls until it clears", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedApi.listRecipesPage
      .mockResolvedValueOnce(page([cake]))
      .mockResolvedValueOnce(page([{ ...cake, processing_status: "translating" }]))
      .mockResolvedValue(page([cake]));
    mockedApi.updateRecipe.mockResolvedValue({ ...cake, processing_status: "translating" });

    renderManager();
    await screen.findByText(/Cake/);

    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Translating…")).toBeInTheDocument();
    expect(mockedApi.listRecipesPage).toHaveBeenCalledTimes(2); // initial load + reload after save

    // Polling kicks in because the reloaded recipe still has a processing_status.
    await act(() => vi.advanceTimersByTimeAsync(3000));
    expect(mockedApi.listRecipesPage).toHaveBeenCalledTimes(3);
    await waitFor(() => expect(screen.queryByText("Translating…")).not.toBeInTheDocument());

    // Now settled — no further polling.
    await act(() => vi.advanceTimersByTimeAsync(3000));
    expect(mockedApi.listRecipesPage).toHaveBeenCalledTimes(3);
  });

  it("shows numbered pagination and requests the right offset when a page is clicked", async () => {
    const user = userEvent.setup();
    mockedApi.getPublicSettings.mockResolvedValue({
      turnstile_site_key: "",
      google_client_id: "",
      backoffice_recipes_page_size: 1,
      max_imports_per_user: 30,
    });
    mockedApi.listRecipesPage.mockImplementation((params) =>
      Promise.resolve({ items: params.offset === 0 ? [cake] : [pendingSoup], total: 2 })
    );

    renderManager();
    await screen.findByText(/Cake/);

    const nav = screen.getByRole("navigation", { name: "Recipe pages" });
    expect(within(nav).getByRole("button", { name: "1" })).toHaveAttribute("aria-current", "page");

    await user.click(within(nav).getByRole("button", { name: "2" }));

    await waitFor(() =>
      expect(mockedApi.listRecipesPage).toHaveBeenCalledWith(
        expect.objectContaining({ limit: 1, offset: 1 })
      )
    );
    expect(await screen.findByText(/Soup/)).toBeInTheDocument();
  });

  it("does not show pagination controls when everything fits on one page", async () => {
    mockRecipeList([cake]);

    renderManager();
    await screen.findByText(/Cake/);

    expect(screen.queryByRole("navigation", { name: "Recipe pages" })).not.toBeInTheDocument();
  });

  it("sends the search text 1.5s after typing stops and resets to page 1", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedApi.getPublicSettings.mockResolvedValue({
      turnstile_site_key: "",
      google_client_id: "",
      backoffice_recipes_page_size: 1,
      max_imports_per_user: 30,
    });
    mockedApi.listRecipesPage.mockImplementation((params) =>
      Promise.resolve({ items: params.offset === 0 ? [cake] : [pendingSoup], total: 2 })
    );

    renderManager();
    await screen.findByText(/Cake/);

    const nav = screen.getByRole("navigation", { name: "Recipe pages" });
    await user.click(within(nav).getByRole("button", { name: "2" }));
    await screen.findByText(/Soup/);

    mockedApi.listRecipesPage.mockClear();
    mockRecipeList([cake]);
    await user.type(screen.getByPlaceholderText("Search by title…"), "cak");
    await act(() => vi.advanceTimersByTimeAsync(1500));

    await waitFor(() =>
      expect(mockedApi.listRecipesPage).toHaveBeenCalledWith(
        expect.objectContaining({ search: "cak", offset: 0 })
      )
    );
  });

  it("shows a no-results message in place of the list when the search matches nothing", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderManager();
    await screen.findByText(/Cake/);

    mockRecipeList([]);
    await user.type(screen.getByPlaceholderText("Search by title…"), "xyz");
    await act(() => vi.advanceTimersByTimeAsync(1500));

    expect(await screen.findByText("No recipes match your search.")).toBeInTheDocument();
  });
});
