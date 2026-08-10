import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResetPasswordPage } from "../auth/ResetPasswordPage";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";

vi.mock("../api/client", () => ({
  api: {
    resetPassword: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

function renderPage(initialEntry = "/reset-password?token=abc123") {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <ResetPasswordPage />
      </MemoryRouter>
    </LanguageProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("ResetPasswordPage", () => {
  it("submits the new password with the token from the URL", async () => {
    mockedApi.resetPassword.mockResolvedValue({ detail: "Password reset — you can log in now." });
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("New password"), "newsecret1");
    await user.type(screen.getByLabelText("Confirm password"), "newsecret1");
    await user.click(screen.getByRole("button", { name: "Reset password" }));

    expect(mockedApi.resetPassword).toHaveBeenCalledWith("abc123", "newsecret1");
    expect(await screen.findByText("Password reset — you can log in now.")).toBeInTheDocument();
  });

  it("shows an error without submitting when the link has no token", async () => {
    const user = userEvent.setup();
    renderPage("/reset-password");

    expect(screen.getByText("This link is missing its reset token.")).toBeInTheDocument();

    await user.type(screen.getByLabelText("New password"), "newsecret1");
    await user.type(screen.getByLabelText("Confirm password"), "newsecret1");
    expect(screen.getByRole("button", { name: "Reset password" })).toBeDisabled();
    expect(mockedApi.resetPassword).not.toHaveBeenCalled();
  });

  it("flags a too-short password instead of submitting", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("New password"), "short");
    await user.type(screen.getByLabelText("Confirm password"), "short");
    await user.click(screen.getByRole("button", { name: "Reset password" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Password must be at least 8 characters."
    );
    expect(mockedApi.resetPassword).not.toHaveBeenCalled();
  });

  it("flags a mismatched confirmation instead of submitting", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("New password"), "newsecret1");
    await user.type(screen.getByLabelText("Confirm password"), "somethingelse");
    await user.click(screen.getByRole("button", { name: "Reset password" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Passwords don't match.");
    expect(mockedApi.resetPassword).not.toHaveBeenCalled();
  });

  it("shows the server's error on a failed reset", async () => {
    mockedApi.resetPassword.mockRejectedValue(new Error("This reset link has expired"));
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("New password"), "newsecret1");
    await user.type(screen.getByLabelText("Confirm password"), "newsecret1");
    await user.click(screen.getByRole("button", { name: "Reset password" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("This reset link has expired");
  });
});
