import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api, setAuthToken, setUnauthorizedHandler } from "../api/client";
import type { User } from "../types";

export const AUTH_STORAGE_KEY = "cookbook-auth-token";

interface AuthContextValue {
  isAuthenticated: boolean;
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  // Distinct from `user === null` so a stored token isn't treated as "logged out" for the one
  // render before its rehydration GET /users/me call resolves (avoids a login-form flash on
  // every page load/refresh).
  const [isRehydrating, setIsRehydrating] = useState(true);

  const logout = () => {
    setAuthToken(null);
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    setUser(null);
  };

  // Registered once: an expired/invalid token now clears itself instead of every protected
  // form just showing "Invalid or expired token" forever until a manual re-login.
  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, []);

  // A stored token only proves *a* session existed — it doesn't carry email/is_admin on its
  // own (decoding the JWT client-side isn't worth it when the API can just answer), so every
  // fresh page load re-fetches the profile before treating the visitor as logged in.
  useEffect(() => {
    const stored = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!stored) {
      setIsRehydrating(false);
      return;
    }
    setAuthToken(stored);
    api
      .me()
      .then((profile) =>
        setUser({
          id: profile.id,
          email: profile.email,
          is_admin: profile.is_admin,
          is_super_admin: profile.is_super_admin,
        })
      )
      .catch(logout)
      .finally(() => setIsRehydrating(false));
  }, []);

  const login = async (email: string, password: string) => {
    const response = await api.login(email, password);
    setAuthToken(response.access_token);
    window.localStorage.setItem(AUTH_STORAGE_KEY, response.access_token);
    setUser(response.user);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated: user !== null, user, login, logout }}>
      {!isRehydrating && children}
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
