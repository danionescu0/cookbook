import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ContactPage } from "../contact/ContactPage";
import { AuthProvider, AUTH_STORAGE_KEY } from "../auth/AuthContext";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";

vi.mock("../api/client", () => ({
  api: {
    getPublicSettings: vi.fn(),
    submitContactMessage: vi.fn(),
    me: vi.fn(),
  },
  setAuthToken: vi.fn(),
  setUnauthorizedHandler: vi.fn(),
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
      <AuthProvider>
        <ContactPage />
      </AuthProvider>
    </LanguageProvider>
  );
}

function logInAsRegularUser() {
  window.localStorage.setItem(AUTH_STORAGE_KEY, "a-token");
  mockedApi.me.mockResolvedValue({
    id: 2,
    email: "someone@example.com",
    is_admin: false,
    is_super_admin: false,
    imported_recipes_count: 0,
  });
}

async function fillRequiredFields(
  user: ReturnType<typeof userEvent.setup>,
  { email = "ana@example.com", phone = "" }: { email?: string; phone?: string } = {}
) {
  await user.type(await screen.findByLabelText("Name"), "Ana");
  if (email) await user.type(screen.getByLabelText("Email"), email);
  if (phone) await user.type(screen.getByLabelText("Phone"), phone);
  await user.type(screen.getByLabelText("Message"), "x".repeat(50));
}

beforeEach(() => {
  vi.resetAllMocks();
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  mockedApi.getPublicSettings.mockResolvedValue({
    turnstile_site_key: "site-key",
    google_client_id: "",
    backoffice_recipes_page_size: 10,
    max_imports_per_user: 30,
  });
});

describe("ContactPage", () => {
  it("requires the captcha to be solved when logged out", async () => {
    const user = userEvent.setup();
    renderPage();
    await fillRequiredFields(user);

    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(await screen.findByText("Please complete the CAPTCHA.")).toBeInTheDocument();
    expect(mockedApi.submitContactMessage).not.toHaveBeenCalled();
  });

  it("submits successfully when logged out after solving the captcha", async () => {
    const user = userEvent.setup();
    mockedApi.submitContactMessage.mockResolvedValue({ id: 1 });
    renderPage();
    await fillRequiredFields(user);
    await user.click(await screen.findByRole("button", { name: "solve captcha" }));

    await user.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() =>
      expect(mockedApi.submitContactMessage).toHaveBeenCalledWith({
        name: "Ana",
        email: "ana@example.com",
        message: "x".repeat(50),
        turnstile_token: "test-turnstile-token",
      })
    );
    expect(
      await screen.findByText("Thanks — your message has been sent. We'll get back to you soon.")
    ).toBeInTheDocument();
  });

  it("does not require a captcha when logged in", async () => {
    logInAsRegularUser();
    const user = userEvent.setup();
    mockedApi.submitContactMessage.mockResolvedValue({ id: 1 });
    renderPage();
    await fillRequiredFields(user);

    await user.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => expect(mockedApi.submitContactMessage).toHaveBeenCalledTimes(1));
    const payload = mockedApi.submitContactMessage.mock.calls[0][0];
    expect(payload.turnstile_token).toBeUndefined();
  });

  it("does not fetch the turnstile site key at all when logged in", async () => {
    logInAsRegularUser();
    renderPage();
    await screen.findByLabelText("Name");

    expect(mockedApi.getPublicSettings).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "solve captcha" })).not.toBeInTheDocument();
  });

  it("requires at least an email or a phone number", async () => {
    logInAsRegularUser();
    const user = userEvent.setup();
    renderPage();
    await user.type(await screen.findByLabelText("Name"), "Ana");
    await user.type(screen.getByLabelText("Message"), "x".repeat(50));

    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(
        await screen.findAllByText("Provide at least an email or a phone number.")
    ).not.toHaveLength(0);
    expect(mockedApi.submitContactMessage).not.toHaveBeenCalled();
  });

  it("accepts a phone number without an email", async () => {
    logInAsRegularUser();
    const user = userEvent.setup();
    mockedApi.submitContactMessage.mockResolvedValue({ id: 1 });
    renderPage();
    await fillRequiredFields(user, { email: "", phone: "555-1234" });

    await user.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() =>
      expect(mockedApi.submitContactMessage).toHaveBeenCalledWith(
        expect.objectContaining({ phone: "555-1234" })
      )
    );
  });

  it("rejects a message shorter than 50 characters", async () => {
    logInAsRegularUser();
    const user = userEvent.setup();
    renderPage();
    await user.type(await screen.findByLabelText("Name"), "Ana");
    await user.type(screen.getByLabelText("Email"), "ana@example.com");
    await user.type(screen.getByLabelText("Message"), "too short");

    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(
      await screen.findByText("Message must be at least 50 characters.")
    ).toBeInTheDocument();
    expect(mockedApi.submitContactMessage).not.toHaveBeenCalled();
  });

  it("shows the server error message on failure", async () => {
    logInAsRegularUser();
    const user = userEvent.setup();
    mockedApi.submitContactMessage.mockRejectedValue(new Error("Request failed (500)"));
    renderPage();
    await fillRequiredFields(user);

    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(await screen.findByText("Error: Request failed (500)")).toBeInTheDocument();
  });
});
