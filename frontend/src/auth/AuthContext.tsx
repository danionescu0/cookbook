import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api, setAuthToken, setUnauthorizedHandler } from "../api/client";

export const AUTH_STORAGE_KEY = "cookbook-auth-token";

interface AuthContextValue {
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => {
    const stored = window.localStorage.getItem(AUTH_STORAGE_KEY);
    setAuthToken(stored);
    return stored;
  });

  const logout = () => {
    setAuthToken(null);
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    setToken(null);
  };

  // Registered once: an expired/invalid token now clears itself instead of every protected
  // form just showing "Invalid or expired token" forever until a manual re-login.
  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, []);

  const login = async (username: string, password: string) => {
    const response = await api.login(username, password);
    setAuthToken(response.access_token);
    window.localStorage.setItem(AUTH_STORAGE_KEY, response.access_token);
    setToken(response.access_token);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated: token !== null, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
