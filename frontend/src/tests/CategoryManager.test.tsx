import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CategoryManager } from "../backoffice/CategoryManager";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { Category } from "../types";

vi.mock("../api/client", () => ({
  api: {
    listCategories: vi.fn(),
    createCategory: vi.fn(),
    deleteCategory: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

const desserts: Category = { id: 1, name: "Desserts", slug: "desserts" };

beforeEach(() => {
  vi.resetAllMocks();
  mockedApi.listCategories.mockResolvedValue([desserts]);
});

function renderManager() {
  return render(
    <LanguageProvider>
      <CategoryManager />
    </LanguageProvider>
  );
}

describe("CategoryManager", () => {
  it("lists categories fetched on mount", async () => {
    renderManager();

    expect(await screen.findByText("Desserts")).toBeInTheDocument();
  });

  it("creates a category and reloads the list", async () => {
    const user = userEvent.setup();
    mockedApi.createCategory.mockResolvedValue({ id: 2, name: "Mains", slug: "mains" });
    mockedApi.listCategories
      .mockResolvedValueOnce([desserts])
      .mockResolvedValueOnce([desserts, { id: 2, name: "Mains", slug: "mains" }]);

    renderManager();
    await screen.findByText("Desserts");

    await user.type(screen.getByLabelText("Name"), "Mains");
    await user.click(screen.getByRole("button", { name: "Add category" }));

    await waitFor(() => expect(mockedApi.createCategory).toHaveBeenCalledWith("Mains"));
    expect(await screen.findByText("Mains")).toBeInTheDocument();
  });

  it("shows an error when creating a category fails", async () => {
    const user = userEvent.setup();
    mockedApi.createCategory.mockRejectedValue(new Error("boom"));

    renderManager();
    await screen.findByText("Desserts");

    await user.type(screen.getByLabelText("Name"), "Mains");
    await user.click(screen.getByRole("button", { name: "Add category" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });

  it("asks for confirmation, then deletes a category once confirmed", async () => {
    const user = userEvent.setup();
    mockedApi.deleteCategory.mockResolvedValue(undefined);
    mockedApi.listCategories.mockResolvedValueOnce([desserts]).mockResolvedValueOnce([]);

    renderManager();
    await screen.findByText("Desserts");

    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(mockedApi.deleteCategory).not.toHaveBeenCalled();

    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(mockedApi.deleteCategory).toHaveBeenCalledWith(1));
    expect(screen.queryByText("Desserts")).not.toBeInTheDocument();
  });

  it("does not delete a category when the confirm dialog is dismissed", async () => {
    const user = userEvent.setup();

    renderManager();
    await screen.findByText("Desserts");

    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));

    expect(mockedApi.deleteCategory).not.toHaveBeenCalled();
    expect(screen.getByText("Desserts")).toBeInTheDocument();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });
});
