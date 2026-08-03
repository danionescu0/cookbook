import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginForm } from "../backoffice/LoginForm";
import { LanguageProvider } from "../i18n/LanguageContext";
import { useAuth } from "../auth/AuthContext";
import { api } from "../api/client";

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: {
    getPublicSettings: vi.fn(),
    resendVerification: vi.fn(),
  },
}));

// The real widget waits for window.turnstile (loaded from Cloudflare's script, absent in jsdom)
// — stub it so tests can drive the "token solved" state directly instead of never resolving.
vi.mock("../auth/TurnstileWidget", () => ({
  TurnstileWidget: ({ onToken }: { onToken: (token: string) => void }) => (
    <button type="button" onClick={() => onToken("test-turnstile-token")}>
      solve captcha
    </button>
  ),
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedApi = vi.mocked(api);

function renderForm() {
  return render(
    <LanguageProvider>
      <MemoryRouter>
        <LoginForm />
      </MemoryRouter>
    </LanguageProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mockedApi.getPublicSettings.mockResolvedValue({
    turnstile_site_key: "site-key",
    backoffice_recipes_page_size: 10,
    max_imports_per_user: 30,
  });
});

describe("LoginForm", () => {
  it("submits the entered credentials", async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue({ isAuthenticated: false, user: null, login, logout: vi.fn() });
    const user = userEvent.setup();

    renderForm();
    await user.type(screen.getByLabelText("Username"), "admin");
    await user.type(screen.getByLabelText("Password"), "secret");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(login).toHaveBeenCalledWith("admin", "secret"));
  });

  it("shows an error message when login fails", async () => {
    const login = vi.fn().mockRejectedValue(new Error("nope"));
    mockedUseAuth.mockReturnValue({ isAuthenticated: false, user: null, login, logout: vi.fn() });
    const user = userEvent.setup();

    renderForm();
    await user.type(screen.getByLabelText("Username"), "admin");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid username or password."
    );
  });

  it("shows a distinct message and a resend option when the account isn't verified yet", async () => {
    const login = vi.fn().mockRejectedValue(new Error("Account not verified yet"));
    mockedUseAuth.mockReturnValue({ isAuthenticated: false, user: null, login, logout: vi.fn() });
    const user = userEvent.setup();

    renderForm();
    await user.type(screen.getByLabelText("Username"), "unverified-user");
    await user.type(screen.getByLabelText("Password"), "secret");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Account not verified yet — check your email for the verification link."
    );
    expect(await screen.findByText("Didn't get the email, or it's been a while?")).toBeInTheDocument();
  });

  it("resends the verification email once the CAPTCHA is solved", async () => {
    const login = vi.fn().mockRejectedValue(new Error("Account not verified yet"));
    mockedUseAuth.mockReturnValue({ isAuthenticated: false, user: null, login, logout: vi.fn() });
    mockedApi.resendVerification.mockResolvedValue({
      detail: "A new verification email has been sent.",
    });
    const user = userEvent.setup();

    renderForm();
    await user.type(screen.getByLabelText("Username"), "unverified-user");
    await user.type(screen.getByLabelText("Password"), "secret");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    await screen.findByText("Didn't get the email, or it's been a while?");

    const resendButton = screen.getByRole("button", { name: "Resend verification email" });
    expect(resendButton).toBeDisabled();

    await user.click(await screen.findByRole("button", { name: "solve captcha" }));
    expect(resendButton).toBeEnabled();

    await user.click(resendButton);

    await waitFor(() =>
      expect(mockedApi.resendVerification).toHaveBeenCalledWith("unverified-user", "test-turnstile-token")
    );
    expect(await screen.findByText("A new verification email has been sent.")).toBeInTheDocument();
  });

  it("shows an error if resending the verification email fails", async () => {
    const login = vi.fn().mockRejectedValue(new Error("Account not verified yet"));
    mockedUseAuth.mockReturnValue({ isAuthenticated: false, user: null, login, logout: vi.fn() });
    mockedApi.resendVerification.mockRejectedValue(new Error("CAPTCHA verification failed"));
    const user = userEvent.setup();

    renderForm();
    await user.type(screen.getByLabelText("Username"), "unverified-user");
    await user.type(screen.getByLabelText("Password"), "secret");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    await user.click(await screen.findByRole("button", { name: "solve captcha" }));
    await user.click(screen.getByRole("button", { name: "Resend verification email" }));

    await waitFor(() =>
      expect(
        screen.getAllByRole("alert").some((el) => el.textContent?.includes("CAPTCHA verification failed"))
      ).toBe(true)
    );
  });
});
