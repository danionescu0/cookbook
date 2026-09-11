import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ImportManager } from "../backoffice/ImportManager";
import { AuthProvider, AUTH_STORAGE_KEY } from "../auth/AuthContext";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { ImportJob } from "../types";

vi.mock("../api/client", () => ({
  api: {
    listImportJobs: vi.fn(),
    createImportJob: vi.fn(),
    approveImportJob: vi.fn(),
    deleteImportJob: vi.fn(),
    me: vi.fn(),
    getPublicSettings: vi.fn(),
  },
  setAuthToken: vi.fn(),
  setUnauthorizedHandler: vi.fn(),
}));

const mockedApi = vi.mocked(api);

const pendingJob: ImportJob = {
  id: 1,
  category_id: null,
  type: "single",
  source: "https://example.com/recipe",
  status: "pending",
  error: null,
  error_kind: null,
  created_at: "2026-07-24T00:00:00Z",
  created_by_user_id: 1,
  created_by_email: "admin@example.com",
  dismissed_at: null,
  admin_reviewed_at: null,
};
const queuedJob: ImportJob = { ...pendingJob, id: 2, status: "queued" };
const failedJob: ImportJob = { ...pendingJob, id: 3, status: "failed", error: "boom" };
const doneJob: ImportJob = { ...pendingJob, id: 4, status: "done" };

function renderManager(onJobCreated?: () => void, reloadTrigger?: number) {
  return render(
    <LanguageProvider>
      <AuthProvider>
        <ImportManager onJobCreated={onJobCreated} reloadTrigger={reloadTrigger} />
      </AuthProvider>
    </LanguageProvider>
  );
}

// Admin by default — matches the existing fixtures ("imported by admin@example.com") and keeps
// every pre-existing test's behavior unchanged, since admins skip the usage/limit fetch entirely.
function logInAsAdmin() {
  window.localStorage.setItem(AUTH_STORAGE_KEY, "a-token");
  mockedApi.me.mockResolvedValue({
    id: 1,
    email: "admin@example.com",
    is_admin: true,
    is_super_admin: true,
    imported_recipes_count: 0,
  });
}

function logInAsRegularUser(importedRecipesCount: number, maxImportsPerUser: number) {
  window.localStorage.setItem(AUTH_STORAGE_KEY, "a-token");
  mockedApi.me.mockResolvedValue({
    id: 2,
    email: "someone@example.com",
    is_admin: false,
    is_super_admin: false,
    imported_recipes_count: importedRecipesCount,
  });
  mockedApi.getPublicSettings.mockResolvedValue({
    turnstile_site_key: "",
    google_client_id: "",
    backoffice_recipes_page_size: 10,
    max_imports_per_user: maxImportsPerUser,
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  mockedApi.listImportJobs.mockResolvedValue([pendingJob]);
  logInAsAdmin();
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

    expect(await screen.findByText("imported by admin@example.com")).toBeInTheDocument();
  });

  it("submits a URL, creating a pending job", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedApi.createImportJob.mockResolvedValue(pendingJob);

    renderManager();
    await screen.findByText("https://example.com/recipe");

    await user.type(screen.getByLabelText("Recipe URL"), "https://example.com/new");
    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() =>
      expect(mockedApi.createImportJob).toHaveBeenCalledWith("https://example.com/new")
    );
  });

  it("auto-approves a newly submitted job that lands pending (admin), so it starts right away", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedApi.createImportJob.mockResolvedValue(pendingJob);
    mockedApi.approveImportJob.mockResolvedValue({ ...pendingJob, status: "queued" });

    renderManager();
    await screen.findByText("https://example.com/recipe");

    await user.type(screen.getByLabelText("Recipe URL"), "https://example.com/new");
    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => expect(mockedApi.approveImportJob).toHaveBeenCalledWith(pendingJob.id));
  });

  it("does not call approve for a newly submitted job that's already queued (non-admin)", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedApi.createImportJob.mockResolvedValue(queuedJob);

    renderManager();
    await screen.findByText("https://example.com/recipe");

    await user.type(screen.getByLabelText("Recipe URL"), "https://example.com/new");
    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => expect(mockedApi.createImportJob).toHaveBeenCalled());
    expect(mockedApi.approveImportJob).not.toHaveBeenCalled();
  });

  it("calls onJobCreated after successfully submitting a new import", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const onJobCreated = vi.fn();
    mockedApi.createImportJob.mockResolvedValue(pendingJob);

    renderManager(onJobCreated);
    await screen.findByText("https://example.com/recipe");

    await user.type(screen.getByLabelText("Recipe URL"), "https://example.com/new");
    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => expect(onJobCreated).toHaveBeenCalledTimes(1));
  });

  it("calls onJobCreated after approving a job", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const onJobCreated = vi.fn();
    mockedApi.approveImportJob.mockResolvedValue({ ...pendingJob, status: "queued" });

    renderManager(onJobCreated);
    await screen.findByText("https://example.com/recipe");

    await user.click(screen.getByRole("button", { name: "Run import" }));

    await waitFor(() => expect(onJobCreated).toHaveBeenCalledTimes(1));
  });

  it("reloads the job list when reloadTrigger changes, picking up a job created elsewhere", async () => {
    const bookmarkJob: ImportJob = { ...pendingJob, id: 5, source: "https://example.com/bookmarked" };
    const { rerender } = renderManager(undefined, 0);
    await screen.findByText("https://example.com/recipe");
    expect(mockedApi.listImportJobs).toHaveBeenCalledTimes(1);

    mockedApi.listImportJobs.mockResolvedValue([pendingJob, bookmarkJob]);
    rerender(
      <LanguageProvider>
        <AuthProvider>
          <ImportManager reloadTrigger={1} />
        </AuthProvider>
      </LanguageProvider>
    );

    expect(await screen.findByText("https://example.com/bookmarked")).toBeInTheDocument();
  });

  it("shows a run-import button for a pending job and a retry button for a failed one", async () => {
    mockedApi.listImportJobs.mockResolvedValue([pendingJob, queuedJob, failedJob, doneJob]);

    renderManager();
    await screen.findAllByText("https://example.com/recipe");

    expect(screen.getAllByRole("button", { name: "Run import" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Retry" })).toHaveLength(1);
  });

  it("does not list a done job — its data now lives on the resulting recipe", async () => {
    mockedApi.listImportJobs.mockResolvedValue([doneJob]);

    renderManager();
    await screen.findByText("Recipe URL"); // form has rendered

    expect(screen.queryByText("https://example.com/recipe")).not.toBeInTheDocument();
    expect(screen.queryByText("In progress")).not.toBeInTheDocument();
  });

  it("approving a pending job calls the API", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedApi.approveImportJob.mockResolvedValue({ ...pendingJob, status: "queued" });

    renderManager();
    await screen.findByText("https://example.com/recipe");

    await user.click(screen.getByRole("button", { name: "Run import" }));

    await waitFor(() => expect(mockedApi.approveImportJob).toHaveBeenCalledWith(1));
  });

  it("asks for confirmation, then deletes a job once confirmed", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedApi.deleteImportJob.mockResolvedValue(undefined);

    renderManager();
    await screen.findByText("https://example.com/recipe");

    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(mockedApi.deleteImportJob).not.toHaveBeenCalled();

    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(mockedApi.deleteImportJob).toHaveBeenCalledWith(1));
  });

  it("does not delete a job when the confirm dialog is dismissed", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    renderManager();
    await screen.findByText("https://example.com/recipe");

    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));

    expect(mockedApi.deleteImportJob).not.toHaveBeenCalled();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
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

  describe("lifetime import limit", () => {
    it("does not show usage or fetch it for an admin", async () => {
      renderManager();
      await screen.findByText("Recipe URL");

      expect(screen.queryByText(/imports used/)).not.toBeInTheDocument();
      // AuthProvider itself calls `me()` once to rehydrate the logged-in profile — the
      // assertion here is that ImportManager's own usage fetch (which would be a 2nd call)
      // never happens for an admin.
      expect(mockedApi.me).toHaveBeenCalledTimes(1);
      expect(mockedApi.getPublicSettings).not.toHaveBeenCalled();
    });

    it("shows a non-admin's usage below the limit, with the button enabled", async () => {
      logInAsRegularUser(12, 30);

      renderManager();

      expect(await screen.findByText("12 / 30 imports used")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Add" })).not.toBeDisabled();
    });

    it("blurs and disables the button once the limit is reached", async () => {
      logInAsRegularUser(30, 30);

      renderManager();
      await screen.findByText("30 / 30 imports used");

      const button = screen.getByRole("button", { name: "Add" });
      expect(button).toBeDisabled();
      expect(button.className).toMatch(/blur-/);
      expect(
        await screen.findByText(/You've used up your lifetime import limit/)
      ).toBeInTheDocument();
    });

    it("does not submit when the limit is reached, even via a direct form submit", async () => {
      logInAsRegularUser(30, 30);

      const { container } = renderManager();
      await screen.findByText("30 / 30 imports used");

      // Bypasses the button's `disabled` attribute — belt-and-suspenders check that handleSubmit
      // itself also guards on `atLimit`, not just the disabled button.
      const form = container.querySelector("form")!;
      fireEvent.submit(form);

      expect(mockedApi.createImportJob).not.toHaveBeenCalled();
    });
  });
});
