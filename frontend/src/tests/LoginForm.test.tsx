import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginForm } from "../backoffice/LoginForm";
import { LanguageProvider } from "../i18n/LanguageContext";
import { useAuth } from "../auth/AuthContext";

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);

function renderForm() {
  return render(
    <LanguageProvider>
      <LoginForm />
    </LanguageProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("LoginForm", () => {
  it("submits the entered credentials", async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue({ isAuthenticated: false, login, logout: vi.fn() });
    const user = userEvent.setup();

    renderForm();
    await user.type(screen.getByLabelText("Username"), "admin");
    await user.type(screen.getByLabelText("Password"), "secret");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(login).toHaveBeenCalledWith("admin", "secret"));
  });

  it("shows an error message when login fails", async () => {
    const login = vi.fn().mockRejectedValue(new Error("nope"));
    mockedUseAuth.mockReturnValue({ isAuthenticated: false, login, logout: vi.fn() });
    const user = userEvent.setup();

    renderForm();
    await user.type(screen.getByLabelText("Username"), "admin");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid username or password."
    );
  });
});
