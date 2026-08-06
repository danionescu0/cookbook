import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FailedImportsManager } from "../backoffice/FailedImportsManager";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { Category, ImportJob, ImportJobsPage } from "../types";

vi.mock("../api/client", () => ({
  api: {
    listCategories: vi.fn(),
    getPublicSettings: vi.fn(),
    listFailedImportsPage: vi.fn(),
    approveImportJob: vi.fn(),
    deleteImportJob: vi.fn(),
    markImportReviewed: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

const desserts: Category = { id: 1, name: "Desserts", slug: "desserts" };

const failedJob: ImportJob = {
  id: 1,
  category_id: 1,
  type: "single",
  source: "https://example.com/broken-recipe",
  status: "failed",
  error: "unexpected error: connection reset",
  error_kind: "technical",
  created_at: "2026-08-06T00:00:00Z",
  created_by_username: "someone",
  dismissed_at: null,
  admin_reviewed_at: null,
};

function page(items: ImportJob[], total = items.length): ImportJobsPage {
  return { items, total };
}

function renderManager() {
  return render(
    <LanguageProvider>
      <FailedImportsManager />
    </LanguageProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mockedApi.listCategories.mockResolvedValue([desserts]);
  mockedApi.getPublicSettings.mockResolvedValue({
    turnstile_site_key: "",
    backoffice_recipes_page_size: 10,
    max_imports_per_user: 30,
  });
  mockedApi.listFailedImportsPage.mockResolvedValue(page([failedJob]));
});

describe("FailedImportsManager", () => {
  it("lists a failed import with its full raw error", async () => {
    renderManager();

    expect(await screen.findByText("example.com")).toBeInTheDocument();
    expect(screen.getByText("unexpected error: connection reset")).toBeInTheDocument();
    expect(screen.getByText("Technical")).toBeInTheDocument();
  });

  it("doesn't show a category badge when the job never reached category resolution", async () => {
    // Most failed jobs never get that far — see worker/app/handlers.py's handle_import_job,
    // where category resolution happens near the end of the try block, after fetch/extraction
    // already succeeded.
    mockedApi.listFailedImportsPage.mockResolvedValue(page([{ ...failedJob, category_id: null }]));

    renderManager();

    await screen.findByText("example.com");
    expect(screen.queryByText("Desserts")).not.toBeInTheDocument();
  });

  it("shows an empty state when there are no failed imports", async () => {
    mockedApi.listFailedImportsPage.mockResolvedValue(page([]));

    renderManager();

    expect(await screen.findByText("No failed imports.")).toBeInTheDocument();
  });

  it("retrying calls the approve endpoint and reloads", async () => {
    const user = userEvent.setup();
    mockedApi.approveImportJob.mockResolvedValue({ ...failedJob, status: "queued" });

    renderManager();
    await screen.findByText("example.com");

    await user.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(mockedApi.approveImportJob).toHaveBeenCalledWith(1));
  });

  it("marking as reviewed calls the API and reloads", async () => {
    const user = userEvent.setup();
    mockedApi.markImportReviewed.mockResolvedValue({
      ...failedJob,
      admin_reviewed_at: "2026-08-06T01:00:00Z",
    });

    renderManager();
    await screen.findByText("example.com");

    await user.click(screen.getByRole("button", { name: "Mark as reviewed" }));

    await waitFor(() => expect(mockedApi.markImportReviewed).toHaveBeenCalledWith(1));
    expect(mockedApi.listFailedImportsPage).toHaveBeenCalledTimes(2);
  });

  it("asks for confirmation, then deletes once confirmed", async () => {
    const user = userEvent.setup();
    mockedApi.deleteImportJob.mockResolvedValue(undefined);

    renderManager();
    await screen.findByText("example.com");

    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(mockedApi.deleteImportJob).not.toHaveBeenCalled();

    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(mockedApi.deleteImportJob).toHaveBeenCalledWith(1));
  });

  it("paginates via the shared Pagination component", async () => {
    const user = userEvent.setup();
    mockedApi.getPublicSettings.mockResolvedValue({
      turnstile_site_key: "",
      backoffice_recipes_page_size: 1,
      max_imports_per_user: 30,
    });
    mockedApi.listFailedImportsPage.mockImplementation((params) =>
      Promise.resolve(
        page(params.offset === 0 ? [failedJob] : [{ ...failedJob, id: 2, source: "https://second.example.com" }], 2)
      )
    );

    renderManager();
    await screen.findByText("example.com");

    const nav = screen.getByRole("navigation", { name: "Recipe pages" });
    await user.click(within(nav).getByRole("button", { name: "2" }));

    await waitFor(() =>
      expect(mockedApi.listFailedImportsPage).toHaveBeenCalledWith(
        expect.objectContaining({ limit: 1, offset: 1 })
      )
    );
    expect(await screen.findByText("second.example.com")).toBeInTheDocument();
  });
});
