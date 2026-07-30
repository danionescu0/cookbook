import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ImportManager } from "../backoffice/ImportManager";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { Category, ImportJob } from "../types";

vi.mock("../api/client", () => ({
  api: {
    listCategories: vi.fn(),
    listImportJobs: vi.fn(),
    createImportJob: vi.fn(),
    approveImportJob: vi.fn(),
    deleteImportJob: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

const desserts: Category = { id: 1, name: "Desserts", slug: "desserts" };

const pendingJob: ImportJob = {
  id: 1,
  category_id: 1,
  type: "single",
  source: "https://example.com/recipe",
  status: "pending",
  error: null,
  created_at: "2026-07-24T00:00:00Z",
  created_by_username: "admin",
};
const queuedJob: ImportJob = { ...pendingJob, id: 2, status: "queued" };
const failedJob: ImportJob = { ...pendingJob, id: 3, status: "failed", error: "boom" };
const doneJob: ImportJob = { ...pendingJob, id: 4, status: "done" };

function renderManager() {
  return render(
    <LanguageProvider>
      <ImportManager />
    </LanguageProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  mockedApi.listCategories.mockResolvedValue([desserts]);
  mockedApi.listImportJobs.mockResolvedValue([pendingJob]);
});

afterEach(() => {
  vi.useRealTimers();
});

describe("ImportManager", () => {
  it("explains that Instagram links are also supported", async () => {
    renderManager();

    expect(await screen.findByText(/Instagram post and reel links/)).toBeInTheDocument();
  });

  it("explains that imports are private to the importer", async () => {
    renderManager();

    expect(await screen.findByText(/Imported recipes are private to you/)).toBeInTheDocument();
  });

  it("shows who imported a job", async () => {
    renderManager();

    expect(await screen.findByText("imported by admin")).toBeInTheDocument();
  });

  it("submits a URL and category, creating a pending job", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedApi.createImportJob.mockResolvedValue(pendingJob);

    renderManager();
    await screen.findByText("https://example.com/recipe");

    await user.type(screen.getByLabelText("Recipe URL"), "https://example.com/new");
    await user.selectOptions(screen.getByLabelText("Category"), "Desserts");
    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() =>
      expect(mockedApi.createImportJob).toHaveBeenCalledWith("https://example.com/new", 1)
    );
  });

  it("shows an approve button only for pending/failed jobs", async () => {
    mockedApi.listImportJobs.mockResolvedValue([pendingJob, queuedJob, failedJob, doneJob]);

    renderManager();
    await screen.findAllByText("https://example.com/recipe");

    expect(screen.getAllByRole("button", { name: "Approve" })).toHaveLength(2); // pending + failed
  });

  it("approving a pending job calls the API", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedApi.approveImportJob.mockResolvedValue({ ...pendingJob, status: "queued" });

    renderManager();
    await screen.findByText("https://example.com/recipe");

    await user.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(mockedApi.approveImportJob).toHaveBeenCalledWith(1));
  });

  it("deleting a job calls the API", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedApi.deleteImportJob.mockResolvedValue(undefined);

    renderManager();
    await screen.findByText("https://example.com/recipe");

    await user.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(mockedApi.deleteImportJob).toHaveBeenCalledWith(1));
  });

  it("shows the job's error message when failed", async () => {
    mockedApi.listImportJobs.mockResolvedValue([failedJob]);

    renderManager();

    expect(await screen.findByText("boom")).toBeInTheDocument();
  });

  it("polls while a job is active, and stops once it settles", async () => {
    mockedApi.listImportJobs.mockResolvedValueOnce([queuedJob]).mockResolvedValue([doneJob]);

    renderManager();
    await screen.findByText("https://example.com/recipe");
    expect(mockedApi.listImportJobs).toHaveBeenCalledTimes(1);

    await act(() => vi.advanceTimersByTimeAsync(3000));
    expect(mockedApi.listImportJobs).toHaveBeenCalledTimes(2);

    // now settled to "done" — no further polling
    await act(() => vi.advanceTimersByTimeAsync(3000));
    expect(mockedApi.listImportJobs).toHaveBeenCalledTimes(2);
  });
});
