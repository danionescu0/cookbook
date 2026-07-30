import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AUTH_STORAGE_KEY, AuthProvider, useAuth } from "../auth/AuthContext";
import { api } from "../api/client";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    api: { login: vi.fn(), me: vi.fn() },
  };
});

const mockedApi = vi.mocked(api);

function Consumer() {
  const { isAuthenticated, user, login, logout } = useAuth();
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
      <span data-testid="username">{user?.username ?? ""}</span>
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

  it("rehydrates from a previously stored token via GET /users/me", async () => {
    window.localStorage.setItem(AUTH_STORAGE_KEY, "stored-token");
    mockedApi.me.mockResolvedValue({
      id: 1,
      username: "admin",
      email: null,
      is_admin: true,
      is_super_admin: true,
    });

    renderConsumer();

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("in"));
    expect(screen.getByTestId("username")).toHaveTextContent("admin");
  });

  it("logs out automatically if the stored token is rejected", async () => {
    window.localStorage.setItem(AUTH_STORAGE_KEY, "stored-token");
    mockedApi.me.mockRejectedValue(new Error("Invalid or expired token"));

    renderConsumer();

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("out"));
    expect(window.localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
  });

  it("login success updates state and persists the token", async () => {
    const user = userEvent.setup();
    mockedApi.login.mockResolvedValue({
      access_token: "new-token",
      token_type: "bearer",
      user: { id: 1, username: "admin", is_admin: true, is_super_admin: true },
    });
    renderConsumer();

    await user.click(screen.getByRole("button", { name: "log in" }));

    expect(screen.getByTestId("status")).toHaveTextContent("in");
    expect(screen.getByTestId("username")).toHaveTextContent("admin");
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
    mockedApi.me.mockResolvedValue({
      id: 1,
      username: "admin",
      email: null,
      is_admin: true,
      is_super_admin: true,
    });
    const user = userEvent.setup();
    renderConsumer();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("in"));

    await user.click(screen.getByRole("button", { name: "log out" }));

    expect(screen.getByTestId("status")).toHaveTextContent("out");
    expect(window.localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
  });
});
