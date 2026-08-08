import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { HowToImportBookmarksDialog } from "../backoffice/HowToImportBookmarksDialog";
import { LanguageProvider } from "../i18n/LanguageContext";

function renderDialog(onClose: () => void) {
  return render(
    <LanguageProvider>
      <HowToImportBookmarksDialog onClose={onClose} />
    </LanguageProvider>
  );
}

describe("HowToImportBookmarksDialog", () => {
  it("shows export instructions for all four browsers", () => {
    renderDialog(vi.fn());

    expect(screen.getByText("Google Chrome")).toBeInTheDocument();
    expect(screen.getByText("Mozilla Firefox")).toBeInTheDocument();
    expect(screen.getByText("Safari")).toBeInTheDocument();
    expect(screen.getByText("Internet Explorer")).toBeInTheDocument();
  });

  it("calls onClose when the OK button is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderDialog(onClose);

    await user.click(screen.getByRole("button", { name: "OK" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose on Escape", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderDialog(onClose);

    await user.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
