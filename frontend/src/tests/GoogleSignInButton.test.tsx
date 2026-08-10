import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GoogleSignInButton } from "../auth/GoogleSignInButton";
import { LanguageProvider } from "../i18n/LanguageContext";
import { useAuth } from "../auth/AuthContext";

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);

function renderButton(onError = vi.fn()) {
  return render(
    <LanguageProvider>
      <GoogleSignInButton clientId="test-client-id" language="en" onError={onError} />
    </LanguageProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  window.google = undefined;
});

describe("GoogleSignInButton", () => {
  it("renders nothing when clientId is empty", () => {
    const loginWithGoogle = vi.fn();
    mockedUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      loginWithGoogle,
      logout: vi.fn(),
    });

    const { container } = render(
      <LanguageProvider>
        <GoogleSignInButton clientId="" language="en" onError={vi.fn()} />
      </LanguageProvider>
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("initializes and renders Google's button once the script is available", async () => {
    const loginWithGoogle = vi.fn();
    mockedUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      loginWithGoogle,
      logout: vi.fn(),
    });
    const initialize = vi.fn();
    const renderButtonFn = vi.fn();
    window.google = { accounts: { id: { initialize, renderButton: renderButtonFn } } };

    renderButton();

    await waitFor(() => expect(initialize).toHaveBeenCalledWith({
      client_id: "test-client-id",
      callback: expect.any(Function),
    }));
    expect(renderButtonFn).toHaveBeenCalled();
  });

  it("calls loginWithGoogle with the credential on a successful sign-in", async () => {
    const loginWithGoogle = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      loginWithGoogle,
      logout: vi.fn(),
    });
    const initialize = vi.fn();
    window.google = { accounts: { id: { initialize, renderButton: vi.fn() } } };

    renderButton();
    await waitFor(() => expect(initialize).toHaveBeenCalled());

    const callback = initialize.mock.calls[0][0].callback;
    callback({ credential: "google-id-token" });

    await waitFor(() =>
      expect(loginWithGoogle).toHaveBeenCalledWith("google-id-token", false, "en")
    );
  });

  it("shows the Terms overlay and resubmits with terms_accepted when a new account needs it", async () => {
    const loginWithGoogle = vi
      .fn()
      .mockRejectedValueOnce(new Error("Please accept the Terms and Conditions to continue"))
      .mockResolvedValueOnce(undefined);
    mockedUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      loginWithGoogle,
      logout: vi.fn(),
    });
    const initialize = vi.fn();
    window.google = { accounts: { id: { initialize, renderButton: vi.fn() } } };
    const user = userEvent.setup();

    renderButton();
    await waitFor(() => expect(initialize).toHaveBeenCalled());
    initialize.mock.calls[0][0].callback({ credential: "google-id-token" });

    const agreeButton = await screen.findByRole("button", { name: "I have read and agree" });
    await user.click(agreeButton);

    await waitFor(() =>
      expect(loginWithGoogle).toHaveBeenNthCalledWith(2, "google-id-token", true, "en")
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("calls onError for any other failure", async () => {
    const loginWithGoogle = vi.fn().mockRejectedValue(new Error("boom"));
    const onError = vi.fn();
    mockedUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      loginWithGoogle,
      logout: vi.fn(),
    });
    const initialize = vi.fn();
    window.google = { accounts: { id: { initialize, renderButton: vi.fn() } } };

    renderButton(onError);
    await waitFor(() => expect(initialize).toHaveBeenCalled());
    initialize.mock.calls[0][0].callback({ credential: "google-id-token" });

    await waitFor(() => expect(onError).toHaveBeenCalledWith("Error: boom"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
