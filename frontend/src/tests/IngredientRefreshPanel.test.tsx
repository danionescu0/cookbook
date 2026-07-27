import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { IngredientRefreshPanel } from "../backoffice/IngredientRefreshPanel";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";

vi.mock("../api/client", () => ({
  api: {
    getIngredientRefreshStatus: vi.fn(),
    createIngredientRefreshJob: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

function renderPanel() {
  return render(
    <LanguageProvider>
      <IngredientRefreshPanel />
    </LanguageProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  mockedApi.getIngredientRefreshStatus.mockResolvedValue({
    status: "never_run",
    error: null,
    ingredients_updated: null,
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("IngredientRefreshPanel", () => {
  it("shows 'never run' on first load", async () => {
    renderPanel();

    expect(await screen.findByText("Never run yet.")).toBeInTheDocument();
  });

  it("clicking the button creates a job and shows its status", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedApi.createIngredientRefreshJob.mockResolvedValue({
      id: 1,
      status: "queued",
      error: null,
      ingredients_updated: null,
    });

    renderPanel();
    await screen.findByText("Never run yet.");

    await user.click(screen.getByRole("button", { name: "Reparse all ingredients" }));

    await waitFor(() => expect(mockedApi.createIngredientRefreshJob).toHaveBeenCalled());
    expect(await screen.findByText("Queued…")).toBeInTheDocument();
  });

  it("polls while active and shows the updated count once done", async () => {
    mockedApi.createIngredientRefreshJob.mockResolvedValue({
      id: 1,
      status: "queued",
      error: null,
      ingredients_updated: null,
    });
    mockedApi.getIngredientRefreshStatus
      .mockResolvedValueOnce({ status: "never_run", error: null, ingredients_updated: null })
      .mockResolvedValueOnce({ status: "processing", error: null, ingredients_updated: null })
      .mockResolvedValue({ status: "done", error: null, ingredients_updated: 7 });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    renderPanel();
    await screen.findByText("Never run yet.");
    await user.click(screen.getByRole("button", { name: "Reparse all ingredients" }));
    await screen.findByText("Queued…");

    await act(() => vi.advanceTimersByTimeAsync(3000));
    expect(await screen.findByText("Reparsing ingredients…")).toBeInTheDocument();

    await act(() => vi.advanceTimersByTimeAsync(3000));
    expect(await screen.findByText("Done. — 7 ingredient(s) updated")).toBeInTheDocument();

    // Settled — no further polling.
    const callsAfterDone = mockedApi.getIngredientRefreshStatus.mock.calls.length;
    await act(() => vi.advanceTimersByTimeAsync(3000));
    expect(mockedApi.getIngredientRefreshStatus.mock.calls.length).toBe(callsAfterDone);
  });

  it("shows the job's error message when it fails", async () => {
    mockedApi.createIngredientRefreshJob.mockResolvedValue({
      id: 1,
      status: "failed",
      error: "No CalorieNinjas API key configured — set one in Backoffice > Settings first.",
      ingredients_updated: null,
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    renderPanel();
    await screen.findByText("Never run yet.");
    await user.click(screen.getByRole("button", { name: "Reparse all ingredients" }));

    expect(
      await screen.findByText(
        "No CalorieNinjas API key configured — set one in Backoffice > Settings first."
      )
    ).toBeInTheDocument();
  });

  it("disables the button while a refresh is active", async () => {
    mockedApi.getIngredientRefreshStatus.mockResolvedValue({
      status: "processing",
      error: null,
      ingredients_updated: null,
    });

    renderPanel();

    expect(await screen.findByRole("button", { name: "Reparsing…" })).toBeDisabled();
  });
});
