import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PendingImportsPanel } from "../account/PendingImportsPanel";
import { AuthProvider, AUTH_STORAGE_KEY } from "../auth/AuthContext";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { Category, ImportJob, Recipe } from "../types";

vi.mock("../api/client", () => ({
  api: {
    listImportJobs: vi.fn(),
    acknowledgeImportedRecipe: vi.fn(),
    dismissFailedImport: vi.fn(),
    me: vi.fn(),
  },
  BASE_URL: "http://localhost:8000",
  setAuthToken: vi.fn(),
  setUnauthorizedHandler: vi.fn(),
}));

const mockedApi = vi.mocked(api);

const baseRecipe: Recipe = {
  id: 1,
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
  added_at: "2026-08-06T00:00:00Z",
  approved_at: "2026-08-06T00:00:00Z",
  available_languages: ["en"],
  processing_status: null,
  owner_username: "someone",
  is_shared: false,
  import_reviewed_at: null,
};

const categories: Category[] = [
  { id: 1, name: "Desserts", slug: "desserts" },
  { id: 2, name: "Main course", slug: "main-course" },
];

const manualRecipe: Recipe = { ...baseRecipe, id: 2, source_url: null };
const alreadyReviewedImport: Recipe = { ...baseRecipe, id: 3, import_reviewed_at: "2026-08-05T00:00:00Z" };
const instagramImport: Recipe = { ...baseRecipe, id: 4, source_url: "https://www.instagram.com/p/xyz/" };

const failedJob: ImportJob = {
  id: 10,
  category_id: 1,
  type: "single",
  source: "https://blocked.example.com/recipe",
  status: "failed",
  error: null,
  error_kind: "disallowed",
  created_at: "2026-08-06T00:00:00Z",
  created_by_username: "someone",
  dismissed_at: null,
  admin_reviewed_at: null,
};

function renderPanel(
  submissions: Recipe[],
  onAcknowledged = vi.fn(),
  onImportsPolled: (() => void) | undefined = undefined
) {
  return render(
    <MemoryRouter>
      <LanguageProvider>
        <AuthProvider>
          <PendingImportsPanel
            submissions={submissions}
            categories={categories}
            onAcknowledged={onAcknowledged}
            onImportsPolled={onImportsPolled}
          />
        </AuthProvider>
      </LanguageProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  window.localStorage.setItem(AUTH_STORAGE_KEY, "a-token");
  // "someone" matches the created_by_username on failedJob/baseRecipe's owner — the failed-jobs
  // list is now scoped to the viewer's own jobs (see PendingImportsPanel's myJobs), so tests that
  // expect a failed-job card to render need the logged-in viewer to actually own it.
  mockedApi.me.mockResolvedValue({
    id: 1,
    username: "someone",
    email: null,
    is_admin: false,
    is_super_admin: false,
    imported_recipes_count: 0,
  });
  mockedApi.listImportJobs.mockResolvedValue([]);
});

afterEach(() => {
  vi.useRealTimers();
});

describe("PendingImportsPanel", () => {
  it("renders nothing when there's nothing pending review or dismissal", async () => {
    const { container } = renderPanel([manualRecipe, alreadyReviewedImport]);

    await waitFor(() => expect(mockedApi.listImportJobs).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a card for a just-finished import with an Edit link", async () => {
    renderPanel([baseRecipe]);

    expect((await screen.findAllByText("Imported cake"))[0]).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Edit" })).toHaveAttribute("href", "/recipes/1/edit");
  });

  it("shows which category Claude picked for a pending import", async () => {
    renderPanel([{ ...baseRecipe, category_id: 2 }]);

    expect(await screen.findByText("AI-selected category: Main course")).toBeInTheDocument();
  });

  it("warns about Instagram's play button only for an Instagram import", async () => {
    renderPanel([instagramImport]);
    expect(await screen.findByText(/play button/)).toBeInTheDocument();
  });

  it("does not show the Instagram warning for a non-Instagram import", async () => {
    renderPanel([baseRecipe]);
    await screen.findAllByText("Imported cake");
    expect(screen.queryByText(/play button/)).not.toBeInTheDocument();
  });

  it("acknowledging a pending import calls the API and removes it via the callback", async () => {
    const onAcknowledged = vi.fn();
    const acknowledged = { ...baseRecipe, import_reviewed_at: "2026-08-06T01:00:00Z" };
    mockedApi.acknowledgeImportedRecipe.mockResolvedValue(acknowledged);
    const user = userEvent.setup();

    renderPanel([baseRecipe], onAcknowledged);
    await screen.findAllByText("Imported cake");

    await user.click(screen.getByRole("button", { name: "OK, got it" }));

    await waitFor(() => expect(mockedApi.acknowledgeImportedRecipe).toHaveBeenCalledWith(1));
    expect(onAcknowledged).toHaveBeenCalledWith(acknowledged);
  });

  it("shows a failed import with a generic disallowed message and lets it be dismissed", async () => {
    mockedApi.listImportJobs.mockResolvedValue([failedJob]);
    mockedApi.dismissFailedImport.mockResolvedValue({ ...failedJob, dismissed_at: "now" });
    const user = userEvent.setup();

    renderPanel([]);

    expect(await screen.findByText("This site doesn't allow us to import from it.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add it manually instead" })).toHaveAttribute(
      "href",
      "/submit-recipe"
    );

    await user.click(screen.getByRole("button", { name: "OK" }));
    await waitFor(() => expect(mockedApi.dismissFailedImport).toHaveBeenCalledWith(10));
    await waitFor(() => expect(screen.queryByText(/doesn't allow/)).not.toBeInTheDocument());
  });

  it("shows the generic technical message for an unspecified error kind", async () => {
    mockedApi.listImportJobs.mockResolvedValue([{ ...failedJob, error_kind: "technical" }]);

    renderPanel([]);

    expect(
      await screen.findByText("Something went wrong on our side — an admin will take a look.")
    ).toBeInTheDocument();
  });

  it("ignores an already-dismissed failed job", async () => {
    mockedApi.listImportJobs.mockResolvedValue([{ ...failedJob, dismissed_at: "2026-08-06T00:00:00Z" }]);

    const { container } = renderPanel([]);

    await waitFor(() => expect(mockedApi.listImportJobs).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("does not show another user's failed job, even when the viewer is an admin", async () => {
    // GET /imports returns every user's jobs for an admin caller (needed for backoffice
    // moderation) — this panel is a personal review widget on the Account page, not a moderation
    // tool, so an admin viewing their own account must not see someone else's failure mixed in.
    mockedApi.me.mockResolvedValue({
      id: 2,
      username: "the-admin",
      email: null,
      is_admin: true,
      is_super_admin: true,
      imported_recipes_count: 0,
    });
    mockedApi.listImportJobs.mockResolvedValue([failedJob]); // created_by_username: "someone"

    const { container } = renderPanel([]);

    await waitFor(() => expect(mockedApi.listImportJobs).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("asks the parent to refetch recipes on every poll while a job is still active, so a just-finished import shows up without a page reload", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const queuedJob: ImportJob = { ...failedJob, id: 11, status: "queued", error_kind: null };
    mockedApi.listImportJobs.mockResolvedValue([queuedJob]);
    const onImportsPolled = vi.fn();

    renderPanel([], vi.fn(), onImportsPolled);
    await waitFor(() => expect(mockedApi.listImportJobs).toHaveBeenCalledTimes(1));
    expect(onImportsPolled).not.toHaveBeenCalled();

    await act(() => vi.advanceTimersByTimeAsync(3000));

    expect(mockedApi.listImportJobs).toHaveBeenCalledTimes(2);
    expect(onImportsPolled).toHaveBeenCalledTimes(1);
  });
});
