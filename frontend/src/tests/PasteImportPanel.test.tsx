import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PasteImportPanel } from "../backoffice/PasteImportPanel";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { ImportJob } from "../types";

vi.mock("../api/client", () => ({
  api: {
    createTextImportJob: vi.fn(),
  },
  setAuthToken: vi.fn(),
  setUnauthorizedHandler: vi.fn(),
}));

const mockedApi = vi.mocked(api);

function renderPanel(onJobCreated?: () => void) {
  return render(
    <LanguageProvider>
      <PasteImportPanel onJobCreated={onJobCreated} />
    </LanguageProvider>
  );
}

const LONG_ENOUGH_TEXT =
  "Grandma's lemon tart: 2 cups flour, 1 cup butter, 3 lemons. Mix the dough, bake at 180C.";

const createdJob: ImportJob = {
  id: 42,
  category_id: null,
  type: "paste",
  source: LONG_ENOUGH_TEXT.slice(0, 40),
  status: "queued",
  error: null,
  error_kind: null,
  created_at: "2026-09-29T00:00:00Z",
  created_by_user_id: 2,
  created_by_email: null,
  dismissed_at: null,
  admin_reviewed_at: null,
};

beforeEach(() => {
  vi.resetAllMocks();
});

describe("PasteImportPanel", () => {
  it("renders the heading and textarea", () => {
    renderPanel();

    expect(screen.getByText("Paste a recipe")).toBeInTheDocument();
    expect(screen.getByLabelText("Recipe text")).toBeInTheDocument();
  });

  it("disables the submit button under the minimum length", async () => {
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByLabelText("Recipe text"), "too short");

    expect(screen.getByRole("button", { name: "Import pasted text" })).toBeDisabled();
    expect(
      screen.getByText("A little more detail is needed before this can be imported.")
    ).toBeInTheDocument();
  });

  it("posts the pasted text and both checkbox values, then clears on success", async () => {
    mockedApi.createTextImportJob.mockResolvedValue(createdJob);
    const onJobCreated = vi.fn();
    const user = userEvent.setup();
    renderPanel(onJobCreated);

    await user.type(screen.getByLabelText("Recipe text"), LONG_ENOUGH_TEXT);
    await user.click(
      screen.getByLabelText("Fill in missing details from the web (also looks for a photo of the dish)")
    );
    await user.click(screen.getByRole("button", { name: "Import pasted text" }));

    expect(mockedApi.createTextImportJob).toHaveBeenCalledWith(LONG_ENOUGH_TEXT, true);
    expect(onJobCreated).toHaveBeenCalledTimes(1);
    expect((screen.getByLabelText("Recipe text") as HTMLTextAreaElement).value).toBe("");
  });

  it("surfaces a server error without clearing the textarea", async () => {
    mockedApi.createTextImportJob.mockRejectedValue(new Error("Pasted text must be longer."));
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByLabelText("Recipe text"), LONG_ENOUGH_TEXT);
    await user.click(screen.getByRole("button", { name: "Import pasted text" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Pasted text must be longer.");
    expect((screen.getByLabelText("Recipe text") as HTMLTextAreaElement).value).toBe(
      LONG_ENOUGH_TEXT
    );
  });
});
