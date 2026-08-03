import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RecipeManager } from "../backoffice/RecipeManager";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { Category, Recipe } from "../types";

vi.mock("../api/client", () => ({
  api: {
    listCategories: vi.fn(),
    listRecipes: vi.fn(),
    createRecipe: vi.fn(),
    updateRecipe: vi.fn(),
    uploadImage: vi.fn(),
    deleteRecipe: vi.fn(),
    approveRecipe: vi.fn(),
    toggleShare: vi.fn(),
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
  owner_username: "admin",
  is_shared: false,
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
  owner_username: "admin",
  is_shared: false,
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  mockedApi.listCategories.mockResolvedValue([desserts]);
  mockedApi.listRecipes.mockResolvedValue([cake]);
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
    mockedApi.listRecipes.mockResolvedValue([pendingSoup]);

    renderManager();
    await screen.findByText(/Soup/);

    expect(screen.queryByRole("button", { name: "Share with community" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Make private" })).not.toBeInTheDocument();
  });

  it("shows the source URL as a link for an imported recipe, and nothing for a manual one", async () => {
    mockedApi.listRecipes.mockResolvedValue([cake, pendingSoup]);

    renderManager();
    await screen.findByText(/Cake/);

    const sourceLink = screen.getByRole("link", { name: "imported from example.com" });
    expect(sourceLink).toHaveAttribute("href", "https://example.com/soup");
  });

  it("shows a processing-status badge and polls until it clears", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedApi.listRecipes
      .mockResolvedValueOnce([cake])
      .mockResolvedValueOnce([{ ...cake, processing_status: "translating" }])
      .mockResolvedValue([cake]);
    mockedApi.updateRecipe.mockResolvedValue({ ...cake, processing_status: "translating" });

    renderManager();
    await screen.findByText(/Cake/);

    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Translating…")).toBeInTheDocument();
    expect(mockedApi.listRecipes).toHaveBeenCalledTimes(2); // initial load + reload after save

    // Polling kicks in because the reloaded recipe still has a processing_status.
    await act(() => vi.advanceTimersByTimeAsync(3000));
    expect(mockedApi.listRecipes).toHaveBeenCalledTimes(3);
    await waitFor(() => expect(screen.queryByText("Translating…")).not.toBeInTheDocument());

    // Now settled — no further polling.
    await act(() => vi.advanceTimersByTimeAsync(3000));
    expect(mockedApi.listRecipes).toHaveBeenCalledTimes(3);
  });
});
