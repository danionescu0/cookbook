import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { GoogleSignInButton } from "../auth/GoogleSignInButton";
import { TurnstileWidget } from "../auth/TurnstileWidget";
import { useLanguage } from "../i18n/LanguageContext";
import { primaryButton, secondaryButton } from "../ui/buttonStyles";

export function LoginForm() {
  const { t, language } = useLanguage();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [googleClientId, setGoogleClientId] = useState("");

  // Shown only after a login attempt reports "not verified" — resending needs its own CAPTCHA
  // solve (a fresh token), since it triggers an email send just like signup does.
  const [showResend, setShowResend] = useState(false);
  const [resendToken, setResendToken] = useState<string | null>(null);
  const [resendSubmitting, setResendSubmitting] = useState(false);
  const [resendMessage, setResendMessage] = useState<string | null>(null);
  const [resendError, setResendError] = useState<string | null>(null);
  const [siteKey, setSiteKey] = useState<string | null>(null);

  useEffect(() => {
    api
      .getPublicSettings()
      .then((settings) => setGoogleClientId(settings.google_client_id))
      .catch(() => setGoogleClientId(""));
  }, []);

  useEffect(() => {
    if (!showResend || siteKey !== null) return;
    api
      .getPublicSettings()
      .then((settings) => setSiteKey(settings.turnstile_site_key))
      .catch(() => setSiteKey(""));
  }, [showResend, siteKey]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setShowResend(false);
    setResendMessage(null);
    setSubmitting(true);
    try {
      await login(email, password);
    } catch (e) {
      if (String(e).includes("not verified")) {
        setError(t.login.unverifiedError);
        setShowResend(true);
      } else {
        setError(t.login.error);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleResend = async () => {
    if (!resendToken) return;
    setResendError(null);
    setResendSubmitting(true);
    try {
      const response = await api.resendVerification(email, resendToken);
      setResendMessage(response.detail);
      setShowResend(false);
    } catch (e) {
      setResendError(String(e));
    } finally {
      setResendSubmitting(false);
    }
  };

  return (
    <section className="mx-auto max-w-sm rounded-lg bg-cream-card p-6 ring-1 ring-black/5">
      <h2 className="font-serif text-2xl font-semibold text-ink">{t.login.heading}</h2>

      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="login-email" className="text-sm font-medium text-ink/70">
            {t.login.emailLabel}
          </label>
          <input
            id="login-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="login-password" className="text-sm font-medium text-ink/70">
            {t.login.passwordLabel}
          </label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none"
          />
        </div>

        {error && (
          <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <button type="submit" disabled={submitting} className={primaryButton}>
          {t.login.submit}
        </button>
      </form>

      {googleClientId && (
        <div className="mt-3 flex justify-center">
          <GoogleSignInButton clientId={googleClientId} language={language} onError={setError} />
        </div>
      )}

      {showResend && (
        <div className="mt-3 flex flex-col gap-2 rounded-md bg-olive-light p-3">
          <p className="text-sm text-ink/70">{t.login.resendPrompt}</p>
          {siteKey && <TurnstileWidget siteKey={siteKey} onToken={setResendToken} />}
          {resendError && (
            <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {resendError}
            </p>
          )}
          <button
            type="button"
            onClick={handleResend}
            disabled={!resendToken || resendSubmitting}
            className={secondaryButton}
          >
            {resendSubmitting ? t.login.resendSending : t.login.resendButton}
          </button>
        </div>
      )}
      {resendMessage && (
        <p role="status" className="mt-3 rounded-md bg-olive-light px-3 py-2 text-sm text-ink">
          {resendMessage}
        </p>
      )}

      <p className="mt-4 text-sm text-ink/70">
        {t.login.signupPrompt}{" "}
        <Link to="/signup" className="text-terracotta hover:underline">
          {t.login.signupLink}
        </Link>
      </p>
      <p className="mt-1 text-sm">
        <Link to="/forgot-password" className="text-terracotta hover:underline">
          {t.login.forgotPasswordLink}
        </Link>
      </p>
      <p className="mt-1 text-xs text-ink/50">{t.login.backofficeNotice}</p>
    </section>
  );
}
