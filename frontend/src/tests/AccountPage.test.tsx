import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AccountPage } from "../account/AccountPage";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { UserProfile } from "../types";

vi.mock("../api/client", () => ({
  api: {
    me: vi.fn(),
    changePassword: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

const profile: UserProfile = {
  id: 1,
  email: "someone@example.com",
  is_admin: false,
  is_super_admin: false,
  imported_recipes_count: 1,
};

function renderPage() {
  return render(
    <LanguageProvider>
      <AccountPage />
    </LanguageProvider>
  );
}

describe("AccountPage", () => {
  it("shows the logged-in user's email", async () => {
    mockedApi.me.mockResolvedValue(profile);

    renderPage();

    expect(await screen.findByText("someone@example.com")).toBeInTheDocument();
  });

  it("shows an error when the profile fails to load", async () => {
    mockedApi.me.mockRejectedValue(new Error("boom"));

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });

  it("submits the password change and shows a success message", async () => {
    mockedApi.me.mockResolvedValue(profile);
    mockedApi.changePassword.mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderPage();
    await screen.findByText("someone@example.com");

    await user.type(screen.getByLabelText("Current password"), "old-pass");
    await user.type(screen.getByLabelText("New password"), "new-password-123");
    await user.click(screen.getByRole("button", { name: "Change password" }));

    await waitFor(() =>
      expect(mockedApi.changePassword).toHaveBeenCalledWith("old-pass", "new-password-123")
    );
    expect(await screen.findByText("Password changed.")).toBeInTheDocument();
  });

  it("shows the server's error message when the password change fails", async () => {
    mockedApi.me.mockResolvedValue(profile);
    mockedApi.changePassword.mockRejectedValue(new Error("Current password is incorrect."));
    const user = userEvent.setup();

    renderPage();
    await screen.findByText("someone@example.com");

    await user.type(screen.getByLabelText("Current password"), "wrong-pass");
    await user.type(screen.getByLabelText("New password"), "new-password-123");
    await user.click(screen.getByRole("button", { name: "Change password" }));

    expect(await screen.findByText("Error: Current password is incorrect.")).toBeInTheDocument();
  });
});
