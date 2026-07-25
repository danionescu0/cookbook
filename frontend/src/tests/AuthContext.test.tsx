import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AUTH_STORAGE_KEY, AuthProvider, useAuth } from "../auth/AuthContext";
import { api } from "../api/client";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    api: { login: vi.fn() },
  };
});

const mockedApi = vi.mocked(api);

function Consumer() {
  const { isAuthenticated, login, logout } = useAuth();
  const handleLogin = async () => {
    try {
      await login("admin", "secret");
    } catch {
      // ignored — mirrors LoginForm's own catch
    }
  };
  return (
    <div>
      <span data-testid="status">{isAuthenticated ? "in" : "out"}</span>
      <button type="button" onClick={handleLogin}>
        log in
      </button>
      <button type="button" onClick={logout}>
        log out
      </button>
    </div>
  );
}

function renderConsumer() {
  return render(
    <AuthProvider>
      <Consumer />
    </AuthProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  window.localStorage.clear();
});

describe("AuthProvider", () => {
  it("starts unauthenticated when nothing is stored", () => {
    renderConsumer();

    expect(screen.getByTestId("status")).toHaveTextContent("out");
  });

  it("reads a previously stored token on mount", () => {
    window.localStorage.setItem(AUTH_STORAGE_KEY, "stored-token");

    renderConsumer();

    expect(screen.getByTestId("status")).toHaveTextContent("in");
  });

  it("login success updates state and persists the token", async () => {
    const user = userEvent.setup();
    mockedApi.login.mockResolvedValue({ access_token: "new-token", token_type: "bearer" });
    renderConsumer();

    await user.click(screen.getByRole("button", { name: "log in" }));

    expect(screen.getByTestId("status")).toHaveTextContent("in");
    expect(window.localStorage.getItem(AUTH_STORAGE_KEY)).toBe("new-token");
  });

  it("login failure keeps the user unauthenticated", async () => {
    const user = userEvent.setup();
    mockedApi.login.mockRejectedValue(new Error("Invalid username or password"));
    renderConsumer();

    await user.click(screen.getByRole("button", { name: "log in" }));

    expect(screen.getByTestId("status")).toHaveTextContent("out");
    expect(window.localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
  });

  it("logout clears state and storage", async () => {
    window.localStorage.setItem(AUTH_STORAGE_KEY, "stored-token");
    const user = userEvent.setup();
    renderConsumer();
    expect(screen.getByTestId("status")).toHaveTextContent("in");

    await user.click(screen.getByRole("button", { name: "log out" }));

    expect(screen.getByTestId("status")).toHaveTextContent("out");
    expect(window.localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
  });
});
