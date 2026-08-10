import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { primaryButton } from "../ui/buttonStyles";
import { TurnstileWidget } from "./TurnstileWidget";

const inputClasses =
  "rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none";

export function ForgotPasswordPage() {
  const { t } = useLanguage();
  const [email, setEmail] = useState("");
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [siteKey, setSiteKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // Always the server's generic response — see api/app/routers/auth.py's forgot_password(),
  // which never distinguishes "no account with this email" to avoid account enumeration.
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

    if (!turnstileToken) {
      setError(t.signup.captchaRequiredError);
      return;
    }

    setSubmitting(true);
    try {
      const response = await api.forgotPassword(email, turnstileToken);
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
        <h2 className="font-serif text-2xl font-semibold text-ink">{t.forgotPassword.heading}</h2>
        <p role="status" className="mt-4 rounded-md bg-olive-light px-3 py-2 text-sm text-ink">
          {successMessage}
        </p>
        <Link to="/login" className="mt-4 inline-block text-sm text-terracotta hover:underline">
          {t.forgotPassword.backToLoginLink}
        </Link>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-sm rounded-lg bg-cream-card p-6 ring-1 ring-black/5">
      <h2 className="font-serif text-2xl font-semibold text-ink">{t.forgotPassword.heading}</h2>

      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="forgot-password-email" className="text-sm font-medium text-ink/70">
            {t.forgotPassword.emailLabel}
          </label>
          <input
            id="forgot-password-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputClasses}
          />
        </div>

        {siteKey && <TurnstileWidget siteKey={siteKey} onToken={setTurnstileToken} />}

        {error && (
          <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <button type="submit" disabled={submitting} className={primaryButton}>
          {t.forgotPassword.submit}
        </button>
      </form>

      <p className="mt-4 text-sm text-ink/70">
        <Link to="/login" className="text-terracotta hover:underline">
          {t.forgotPassword.backToLoginLink}
        </Link>
      </p>
    </section>
  );
}
