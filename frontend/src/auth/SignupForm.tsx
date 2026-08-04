import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { TermsOverlay } from "../legal/TermsOverlay";
import { primaryButton } from "../ui/buttonStyles";
import { TurnstileWidget } from "./TurnstileWidget";

const inputClasses =
  "rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none";

export function SignupForm() {
  const { t, language } = useLanguage();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [siteKey, setSiteKey] = useState<string | null>(null);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [showTerms, setShowTerms] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // The server's own message, not a fixed string — it differs when this email already has an
  // unconfirmed account (see api/app/routers/auth.py's signup()) and we want that distinction
  // to reach the visitor, not just a generic "check your email."
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    api
      .getPublicSettings()
      .then((settings) => setSiteKey(settings.turnstile_site_key))
      .catch(() => setSiteKey(""));
  }, []);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    if (!termsAccepted) {
      setShowTerms(true);
      return;
    }
    if (password !== confirmPassword) {
      setError(t.signup.passwordMismatchError);
      return;
    }
    if (!turnstileToken) {
      setError(t.signup.captchaRequiredError);
      return;
    }

    setSubmitting(true);
    try {
      const response = await api.signup({
        username,
        email,
        password,
        turnstile_token: turnstileToken,
        terms_accepted: termsAccepted,
        language,
      });
      setSuccessMessage(response.detail);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  if (successMessage) {
    return (
      <section className="mx-auto max-w-sm rounded-lg bg-cream-card p-6 ring-1 ring-black/5">
        <h2 className="font-serif text-2xl font-semibold text-ink">{t.signup.heading}</h2>
        <p role="status" className="mt-4 rounded-md bg-olive-light px-3 py-2 text-sm text-ink">
          {successMessage}
        </p>
        <Link to="/login" className="mt-4 inline-block text-sm text-terracotta hover:underline">
          {t.verifyEmail.loginLink}
        </Link>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-sm rounded-lg bg-cream-card p-6 ring-1 ring-black/5">
      <h2 className="font-serif text-2xl font-semibold text-ink">{t.signup.heading}</h2>

      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="signup-username" className="text-sm font-medium text-ink/70">
            {t.signup.usernameLabel}
          </label>
          <input
            id="signup-username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className={inputClasses}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="signup-email" className="text-sm font-medium text-ink/70">
            {t.signup.emailLabel}
          </label>
          <input
            id="signup-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputClasses}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="signup-password" className="text-sm font-medium text-ink/70">
            {t.signup.passwordLabel}
          </label>
          <input
            id="signup-password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClasses}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="signup-confirm-password" className="text-sm font-medium text-ink/70">
            {t.signup.confirmPasswordLabel}
          </label>
          <input
            id="signup-confirm-password"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className={inputClasses}
          />
        </div>

        {siteKey && <TurnstileWidget siteKey={siteKey} onToken={setTurnstileToken} />}

        {termsAccepted ? (
          <p className="text-sm text-olive">
            ✓ {t.signup.termsAccepted}{" "}
            <button
              type="button"
              onClick={() => setShowTerms(true)}
              className="text-terracotta hover:underline"
            >
              {t.signup.termsReviewLink}
            </button>
          </p>
        ) : (
          <p className="text-sm text-ink/70">
            {t.signup.termsPrompt}{" "}
            <button
              type="button"
              onClick={() => setShowTerms(true)}
              className="text-terracotta hover:underline"
            >
              {t.signup.termsLink}
            </button>
            .
          </p>
        )}

        {error && (
          <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <button type="submit" disabled={submitting} className={primaryButton}>
          {t.signup.submit}
        </button>
      </form>

      <p className="mt-4 text-sm text-ink/70">
        {t.signup.loginPrompt}{" "}
        <Link to="/login" className="text-terracotta hover:underline">
          {t.signup.loginLink}
        </Link>
      </p>

      {showTerms && (
        <TermsOverlay
          onAgree={() => {
            setTermsAccepted(true);
            setShowTerms(false);
          }}
          onClose={() => setShowTerms(false)}
        />
      )}
    </section>
  );
}
