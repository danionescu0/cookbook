import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BookmarkImportPanel } from "../backoffice/BookmarkImportPanel";
import { AuthProvider, AUTH_STORAGE_KEY } from "../auth/AuthContext";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { BookmarkImportResult, BookmarkParseResponse } from "../types";

vi.mock("../api/client", () => ({
  api: {
    me: vi.fn(),
    parseBookmarkFile: vi.fn(),
    importBookmarkSelection: vi.fn(),
  },
  setAuthToken: vi.fn(),
  setUnauthorizedHandler: vi.fn(),
}));

const mockedApi = vi.mocked(api);

function renderPanel(onJobCreated?: () => void) {
  return render(
    <LanguageProvider>
      <AuthProvider>
        <BookmarkImportPanel onJobCreated={onJobCreated} />
      </AuthProvider>
    </LanguageProvider>
  );
}

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

function logInAsRegularUser() {
  window.localStorage.setItem(AUTH_STORAGE_KEY, "a-token");
  mockedApi.me.mockResolvedValue({
    id: 2,
    email: "someone@example.com",
    is_admin: false,
    is_super_admin: false,
    imported_recipes_count: 8,
  });
}

const twoLinksResponse: BookmarkParseResponse = {
  links: [
    { title: "Chocolate Cake", url: "https://example.com/cake", already_imported: false },
    { title: "Soup", url: "https://example.com/soup", already_imported: false },
  ],
  remaining_quota: null,
};

async function loadFile() {
  const file = new File(["<html></html>"], "bookmarks.html", { type: "text/html" });
  // findBy*, not getBy* — AuthProvider resolves api.me() asynchronously, so the panel (and its
  // file input) isn't in the DOM on the first render.
  const input = await screen.findByLabelText(/load bookmark file/i, { selector: "input" });
  await userEvent.upload(input, file);
}

beforeEach(() => {
  vi.resetAllMocks();
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  logInAsAdmin();
});

describe("BookmarkImportPanel", () => {
  it("shows the found links as selectable checkboxes after loading a file", async () => {
    mockedApi.parseBookmarkFile.mockResolvedValue(twoLinksResponse);
    renderPanel();
    await screen.findByText("Import from bookmarks");

    await loadFile();

    expect(await screen.findByText("Chocolate Cake")).toBeInTheDocument();
    expect(screen.getByText("Soup")).toBeInTheDocument();
    expect(mockedApi.parseBookmarkFile).toHaveBeenCalledTimes(1);
  });

  it("shows an already-imported link as a disabled, badged, non-selectable row", async () => {
    mockedApi.parseBookmarkFile.mockResolvedValue({
      links: [{ title: "Cake", url: "https://example.com/cake", already_imported: true }],
      remaining_quota: null,
    });
    renderPanel();
    await loadFile();

    const checkbox = await screen.findByRole("checkbox", { name: /Cake/ });
    expect(checkbox).toBeDisabled();
    expect(screen.getByText("Already imported")).toBeInTheDocument();
  });

  it("caps selection at the non-admin's remaining quota", async () => {
    logInAsRegularUser();
    mockedApi.parseBookmarkFile.mockResolvedValue({
      links: [
        { title: "Cake", url: "https://example.com/cake", already_imported: false },
        { title: "Soup", url: "https://example.com/soup", already_imported: false },
      ],
      remaining_quota: 1,
    });
    const user = userEvent.setup();
    renderPanel();
    await loadFile();

    const cakeBox = await screen.findByRole("checkbox", { name: /Cake/ });
    const soupBox = screen.getByRole("checkbox", { name: /Soup/ });
    await user.click(cakeBox);

    expect(screen.getByText("1 / 1 selected")).toBeInTheDocument();
    expect(soupBox).toBeDisabled();
  });

  it("does not show a selection count for an admin (unlimited)", async () => {
    mockedApi.parseBookmarkFile.mockResolvedValue(twoLinksResponse);
    renderPanel();
    await loadFile();
    await screen.findByText("Chocolate Cake");

    expect(screen.queryByText(/\d+ \/ \d+ selected/)).not.toBeInTheDocument();
  });

  it("imports the selected links and reports the result, notifying the parent", async () => {
    mockedApi.parseBookmarkFile.mockResolvedValue(twoLinksResponse);
    const result: BookmarkImportResult = {
      created: [
        {
          id: 10,
          category_id: null,
          type: "bookmark",
          source: "https://example.com/cake",
          status: "queued",
          error: null,
          error_kind: null,
          created_at: "2026-08-09T00:00:00Z",
          created_by_user_id: 1,
          created_by_email: null,
          dismissed_at: null,
          admin_reviewed_at: null,
        },
      ],
      skipped_duplicate: ["https://example.com/soup"],
    };
    mockedApi.importBookmarkSelection.mockResolvedValue(result);
    const onJobCreated = vi.fn();
    const user = userEvent.setup();
    renderPanel(onJobCreated);
    await loadFile();
    await user.click(await screen.findByRole("checkbox", { name: /Chocolate Cake/ }));

    await user.click(screen.getByRole("button", { name: "Import selected" }));

    expect(mockedApi.importBookmarkSelection).toHaveBeenCalledWith(["https://example.com/cake"]);
    expect(
      await screen.findByText("Started 1 imports. 1 were already imported and skipped.")
    ).toBeInTheDocument();
    expect(onJobCreated).toHaveBeenCalledTimes(1);
  });

  it("shows the parse error and lets the admin try again", async () => {
    mockedApi.parseBookmarkFile.mockRejectedValue(new Error("bad file"));
    renderPanel();

    await loadFile();

    expect(await screen.findByRole("alert")).toHaveTextContent("bad file");
    // Back to the load-file state, not stuck on "parsing".
    expect(await screen.findByLabelText(/load bookmark file/i)).toBeInTheDocument();
  });

  it("resets back to the load-file state via 'Choose another file'", async () => {
    mockedApi.parseBookmarkFile.mockResolvedValue(twoLinksResponse);
    const user = userEvent.setup();
    renderPanel();
    await loadFile();
    await screen.findByText("Chocolate Cake");

    await user.click(screen.getByRole("button", { name: "Choose another file" }));

    expect(screen.queryByText("Chocolate Cake")).not.toBeInTheDocument();
    expect(await screen.findByLabelText(/load bookmark file/i)).toBeInTheDocument();
  });

  it("opens and closes the how-to-import dialog", async () => {
    const user = userEvent.setup();
    renderPanel();
    await screen.findByText("Import from bookmarks");

    await user.click(screen.getByRole("button", { name: "How do I export my bookmarks?" }));

    expect(screen.getByText("How to export your bookmarks")).toBeInTheDocument();
    expect(screen.getByText("Google Chrome")).toBeInTheDocument();
    expect(screen.getByText("Mozilla Firefox")).toBeInTheDocument();
    expect(screen.getByText("Safari")).toBeInTheDocument();
    expect(screen.getByText("Internet Explorer")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "OK" }));

    await waitFor(() =>
      expect(screen.queryByText("How to export your bookmarks")).not.toBeInTheDocument()
    );
  });
});
