const STORAGE_KEY = "cookbook-pending-share";

// Lets a visitor return to the exact /share/:token page after finishing signup/login on a
// *different* page — needed because manual signup requires email verification (SignupForm ->
// VerifyEmailPage -> LoginForm, a 3-page hop) before the visitor is actually authenticated, and
// there's no query-param-based "redirect back" mechanism anywhere else in the app to reuse. See
// App.tsx's pending-share redirect effect, the one place this is read.
export function setPendingShareToken(token: string): void {
  window.localStorage.setItem(STORAGE_KEY, token);
}

export function getPendingShareToken(): string | null {
  return window.localStorage.getItem(STORAGE_KEY);
}

export function clearPendingShareToken(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}
