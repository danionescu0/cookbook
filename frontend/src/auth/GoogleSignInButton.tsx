import { useEffect, useRef, useState } from "react";
import { useAuth } from "./AuthContext";
import { TermsOverlay } from "../legal/TermsOverlay";

interface GoogleCredentialResponse {
  credential: string;
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (options: {
            client_id: string;
            callback: (response: GoogleCredentialResponse) => void;
          }) => void;
          renderButton: (container: HTMLElement, options: { theme: string; size: string }) => void;
        };
      };
    };
  }
}

interface GoogleSignInButtonProps {
  clientId: string;
  language: string;
  onError: (message: string) => void;
}

// Renders Google's own "Sign in with Google" button (via the Google Identity Services script tag
// in index.html) and drives both login and implicit signup through the same POST /auth/google
// endpoint — see api/app/routers/auth.py's google_signin() for which of the two actually happens.
export function GoogleSignInButton({ clientId, language, onError }: GoogleSignInButtonProps) {
  const { loginWithGoogle } = useAuth();
  const containerRef = useRef<HTMLDivElement>(null);
  const idTokenRef = useRef<string | null>(null);
  const [showTerms, setShowTerms] = useState(false);

  // A ref updated on every render (not a `callback` effect dependency) so the button-render
  // effect below only needs to depend on `clientId` — a new inline `onError`/changed `language`
  // on a later render shouldn't tear down and re-render the actual Google button. Same pattern
  // TurnstileWidget uses for its own onToken callback.
  const handleCredentialRef = useRef<(response: GoogleCredentialResponse) => void>(() => {});
  useEffect(() => {
    handleCredentialRef.current = (response) => {
      idTokenRef.current = response.credential;
      loginWithGoogle(response.credential, false, language).catch((e: unknown) => {
        if (String(e).includes("Terms and Conditions")) {
          setShowTerms(true);
        } else {
          onError(String(e));
        }
      });
    };
  });

  useEffect(() => {
    if (!clientId || !containerRef.current) return;

    let cancelled = false;
    const renderButton = () => {
      if (cancelled || !window.google || !containerRef.current) return;
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: (response) => handleCredentialRef.current(response),
      });
      window.google.accounts.id.renderButton(containerRef.current, {
        theme: "outline",
        size: "large",
      });
    };

    if (window.google) {
      renderButton();
      return () => {
        cancelled = true;
      };
    }

    // The script tag in index.html is `async defer` — it may not be loaded yet when this
    // component first mounts, so poll briefly rather than assuming it's ready.
    const interval = setInterval(() => {
      if (window.google) {
        clearInterval(interval);
        renderButton();
      }
    }, 100);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [clientId]);

  if (!clientId) return null;

  return (
    <>
      <div ref={containerRef} />
      {showTerms && (
        <TermsOverlay
          onAgree={() => {
            setShowTerms(false);
            const idToken = idTokenRef.current;
            if (!idToken) return;
            loginWithGoogle(idToken, true, language).catch((e: unknown) => onError(String(e)));
          }}
          onClose={() => setShowTerms(false)}
        />
      )}
    </>
  );
}
