import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SignupForm } from "../auth/SignupForm";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";

vi.mock("../api/client", () => ({
  api: {
    getPublicSettings: vi.fn(),
    signup: vi.fn(),
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

function renderForm() {
  return render(
    <LanguageProvider>
      <MemoryRouter>
        <SignupForm />
      </MemoryRouter>
    </LanguageProvider>
  );
}

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Email"), "newuser@example.com");
  await user.type(screen.getByLabelText("Password"), "supersecret1");
  await user.type(screen.getByLabelText("Confirm password"), "supersecret1");
  await user.click(await screen.findByRole("button", { name: "solve captcha" }));
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

describe("SignupForm", () => {
  it("shows the terms overlay instead of submitting when terms haven't been accepted yet", async () => {
    const user = userEvent.setup();
    renderForm();
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Sign up" }));

    expect(screen.getByRole("dialog", { name: "Terms and Conditions" })).toBeInTheDocument();
    expect(mockedApi.signup).not.toHaveBeenCalled();
  });

  it("opens the overlay from the inline terms link without needing to submit first", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.click(screen.getByRole("button", { name: "Terms and Conditions" }));

    expect(screen.getByRole("dialog", { name: "Terms and Conditions" })).toBeInTheDocument();
  });

  it("keeps the agree button unavailable until the content has been scrolled to the end", async () => {
    // jsdom always reports 0 for scrollHeight/clientHeight/scrollTop, which would otherwise make
    // "reached the end" trivially true the instant the overlay mounts. Patch Element.prototype
    // for the duration of this test so the overlay sees a real, scrollable viewport instead.
    const originalScrollHeight = Object.getOwnPropertyDescriptor(Element.prototype, "scrollHeight")!;
    const originalClientHeight = Object.getOwnPropertyDescriptor(Element.prototype, "clientHeight")!;
    const originalScrollTop = Object.getOwnPropertyDescriptor(Element.prototype, "scrollTop")!;
    let scrollTop = 0;
    Object.defineProperty(Element.prototype, "scrollHeight", { configurable: true, get: () => 1000 });
    Object.defineProperty(Element.prototype, "clientHeight", { configurable: true, get: () => 200 });
    Object.defineProperty(Element.prototype, "scrollTop", {
      configurable: true,
      get: () => scrollTop,
      set: (v: number) => {
        scrollTop = v;
      },
    });

    try {
      const user = userEvent.setup();
      renderForm();
      await user.click(screen.getByRole("button", { name: "Terms and Conditions" }));

      expect(screen.queryByRole("button", { name: "I have read and agree" })).not.toBeInTheDocument();
      expect(screen.getByText("Scroll to the bottom to continue.")).toBeInTheDocument();

      const scrollable = screen.getByTestId("terms-scroll-container");
      scrollTop = 800;
      fireEvent.scroll(scrollable);

      expect(await screen.findByRole("button", { name: "I have read and agree" })).toBeInTheDocument();
    } finally {
      Object.defineProperty(Element.prototype, "scrollHeight", originalScrollHeight);
      Object.defineProperty(Element.prototype, "clientHeight", originalClientHeight);
      Object.defineProperty(Element.prototype, "scrollTop", originalScrollTop);
    }
  });

  it("submits with terms_accepted true once the overlay has been agreed to", async () => {
    mockedApi.signup.mockResolvedValue({ detail: "Account created." });
    const user = userEvent.setup();
    renderForm();
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Sign up" }));
    await user.click(await screen.findByRole("button", { name: "I have read and agree" }));
    expect(screen.getByText(/Terms and Conditions accepted\./)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Sign up" }));

    await waitFor(() =>
      expect(mockedApi.signup).toHaveBeenCalledWith({
        email: "newuser@example.com",
        password: "supersecret1",
        turnstile_token: "test-turnstile-token",
        terms_accepted: true,
        language: "en",
      })
    );
  });

  it("shows a forgot-password link instead of a dead-end error when the email is already registered", async () => {
    mockedApi.signup.mockRejectedValue(new Error("That email is already registered"));
    const user = userEvent.setup();
    renderForm();
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Sign up" }));
    await user.click(await screen.findByRole("button", { name: "I have read and agree" }));
    await user.click(screen.getByRole("button", { name: "Sign up" }));

    expect(await screen.findByRole("link", { name: "Forgot your password?" })).toHaveAttribute(
      "href",
      "/forgot-password"
    );
  });

  it("flags an invalid email on blur", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.type(screen.getByLabelText("Email"), "not-an-email");
    await user.tab();

    expect(await screen.findByRole("alert")).toHaveTextContent("Please enter a valid email address.");
  });

  it("flags a too-short password on blur", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.type(screen.getByLabelText("Password"), "short");
    await user.tab();

    expect(await screen.findByRole("alert")).toHaveTextContent("Password must be at least 8 characters.");
  });

  it("flags a mismatched confirm-password on blur", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.type(screen.getByLabelText("Password"), "supersecret1");
    await user.type(screen.getByLabelText("Confirm password"), "somethingelse");
    await user.tab();

    expect(await screen.findByRole("alert")).toHaveTextContent("Passwords don't match.");
  });

  it("leaves untouched empty fields alone on blur", async () => {
    const user = userEvent.setup();
    renderForm();

    screen.getByLabelText("Email").focus();
    await user.tab();

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("closes the overlay without accepting when the close button is used", async () => {
    const user = userEvent.setup();
    renderForm();
    await user.click(screen.getByRole("button", { name: "Terms and Conditions" }));

    await user.click(screen.getByRole("button", { name: "Close" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Terms and Conditions" })).toBeInTheDocument();
  });
});
