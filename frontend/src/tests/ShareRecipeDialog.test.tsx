import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "../i18n/LanguageContext";
import { ShareRecipeDialog } from "../sharing/ShareRecipeDialog";
import { api } from "../api/client";
import type { Recipe, RecipeShare } from "../types";

vi.mock("../api/client", () => ({
  api: {
    listRecipeShares: vi.fn(),
    createRecipeShare: vi.fn(),
    revokeRecipeShare: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

const recipe: Recipe = {
  id: 7,
  title: "Lemon Tart",
  slug: "lemon-tart",
  description: "",
  ingredients: [],
  steps: [],
  tips: [],
  images: [],
  language: "en",
  category_id: 1,
  source_url: null,
  status: "approved",
  added_at: "2026-08-20T00:00:00Z",
  approved_at: "2026-08-20T00:00:00Z",
  available_languages: ["en"],
  processing_status: null,
  owner_user_id: 1,
  owner_email: null,
  is_shared: false,
  import_reviewed_at: null,
  shared_from_recipe_id: null,
};

function share(overrides: Partial<RecipeShare> = {}): RecipeShare {
  return {
    id: 1,
    token: "tok1",
    created_at: "2026-08-29T00:00:00Z",
    expires_at: new Date(Date.now() + 20 * 60 * 60 * 1000).toISOString(),
    revoked_at: null,
    ...overrides,
  };
}

function renderDialog(onClose = vi.fn(), recipeOverride: Recipe = recipe) {
  return render(
    <LanguageProvider>
      <ShareRecipeDialog recipe={recipeOverride} onClose={onClose} />
    </LanguageProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  // jsdom's `navigator.clipboard` is a getter-only accessor with no real implementation.
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
    configurable: true,
  });
});

describe("ShareRecipeDialog", () => {
  it("shows a placeholder when the recipe has no share links yet", async () => {
    mockedApi.listRecipeShares.mockResolvedValue([]);

    renderDialog();

    expect(await screen.findByText("No links yet — create one to send this recipe.")).toBeInTheDocument();
  });

  it("generates a new link and adds it to the list", async () => {
    mockedApi.listRecipeShares.mockResolvedValue([]);
    mockedApi.createRecipeShare.mockResolvedValue(share());
    const user = userEvent.setup();

    renderDialog();
    await screen.findByText("No links yet — create one to send this recipe.");

    await user.click(screen.getByRole("button", { name: "Create a link" }));

    expect(mockedApi.createRecipeShare).toHaveBeenCalledWith(7);
    expect(await screen.findByText("Copy link")).toBeInTheDocument();
    expect(screen.getByText("Revoke")).toBeInTheDocument();
  });

  it("copies the share link and shows a confirmation", async () => {
    mockedApi.listRecipeShares.mockResolvedValue([share()]);
    const user = userEvent.setup();
    // userEvent.setup() installs its own clipboard emulation, overwriting the plain vi.fn() from
    // beforeEach — redefine it again, after setup(), so the assertion below sees a real spy.
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });

    renderDialog();
    await user.click(await screen.findByText("Copy link"));

    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/share/tok1`);
    expect(await screen.findByText("Copied!")).toBeInTheDocument();
  });

  it("revokes a link, replacing its actions with a revoked message", async () => {
    mockedApi.listRecipeShares.mockResolvedValue([share()]);
    mockedApi.revokeRecipeShare.mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderDialog();
    await user.click(await screen.findByText("Revoke"));

    expect(mockedApi.revokeRecipeShare).toHaveBeenCalledWith(7, 1);
    expect(await screen.findByText("This link was revoked by its sender.")).toBeInTheDocument();
    expect(screen.queryByText("Copy link")).not.toBeInTheDocument();
    expect(screen.queryByText("Revoke")).not.toBeInTheDocument();
  });

  it("shows the permanent public link instead of the generate/list flow for a public recipe", async () => {
    renderDialog(vi.fn(), { ...recipe, is_shared: true, status: "approved" });

    expect(await screen.findByText(/This recipe is public/)).toBeInTheDocument();
    expect(
      screen.getByDisplayValue(`${window.location.origin}/en/recipes/7-lemon-tart`)
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create a link" })).not.toBeInTheDocument();
    expect(mockedApi.listRecipeShares).not.toHaveBeenCalled();
  });

  it("copies the permanent public link for a public recipe", async () => {
    const user = userEvent.setup();
    // userEvent.setup() installs its own clipboard emulation — define ours after, same as the
    // "copies the share link" test above.
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });

    renderDialog(vi.fn(), { ...recipe, is_shared: true, status: "approved" });
    await user.click(await screen.findByRole("button", { name: "Copy link" }));

    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/en/recipes/7-lemon-tart`);
    expect(await screen.findByText("Copied!")).toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    mockedApi.listRecipeShares.mockResolvedValue([]);
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderDialog(onClose);
    await screen.findByText("No links yet — create one to send this recipe.");

    await user.keyboard("{Escape}");

    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});
