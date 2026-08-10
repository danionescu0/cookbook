import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ForgotPasswordPage } from "../auth/ForgotPasswordPage";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";

vi.mock("../api/client", () => ({
  api: {
    getPublicSettings: vi.fn(),
    forgotPassword: vi.fn(),
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

const mockedApi = vi.mocked(api);

function renderPage() {
  return render(
    <LanguageProvider>
      <MemoryRouter>
        <ForgotPasswordPage />
      </MemoryRouter>
    </LanguageProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mockedApi.getPublicSettings.mockResolvedValue({
    turnstile_site_key: "site-key",
    google_client_id: "",
    backoffice_recipes_page_size: 10,
    max_imports_per_user: 30,
  });
});

describe("ForgotPasswordPage", () => {
  it("submits the email and shows the server's generic response", async () => {
    mockedApi.forgotPassword.mockResolvedValue({
      detail: "If that email has an account, we've sent a password reset link.",
    });
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("Email"), "someone@example.com");
    await user.click(await screen.findByRole("button", { name: "solve captcha" }));
    await user.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(mockedApi.forgotPassword).toHaveBeenCalledWith("someone@example.com", "test-turnstile-token");
    expect(
      await screen.findByText("If that email has an account, we've sent a password reset link.")
    ).toBeInTheDocument();
  });

  it("requires the captcha to be solved before submitting", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("Email"), "someone@example.com");
    await user.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Please complete the CAPTCHA.");
    expect(mockedApi.forgotPassword).not.toHaveBeenCalled();
  });

  it("shows an error when the request fails", async () => {
    mockedApi.forgotPassword.mockRejectedValue(new Error("CAPTCHA verification failed"));
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("Email"), "someone@example.com");
    await user.click(await screen.findByRole("button", { name: "solve captcha" }));
    await user.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("CAPTCHA verification failed");
  });
});
