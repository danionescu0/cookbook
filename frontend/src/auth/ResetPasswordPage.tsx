import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { primaryButton } from "../ui/buttonStyles";

const inputClasses =
  "rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none";

const MIN_PASSWORD_LENGTH = 8;

export function ResetPasswordPage() {
  const { t } = useLanguage();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    if (!token) {
      setError(t.resetPassword.missingToken);
      return;
    }
    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      setError(t.resetPassword.passwordTooShortError);
      return;
    }
    if (newPassword !== confirmPassword) {
      setError(t.resetPassword.passwordMismatchError);
      return;
    }

    setSubmitting(true);
    try {
      const response = await api.resetPassword(token, newPassword);
      setSuccessMessage(response.detail);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  if (successMessage) {
    return (
      <section className="mx-auto max-w-sm rounded-lg bg-cream-card p-6 ring-1 ring-black/5 text-center">
        <h2 className="font-serif text-2xl font-semibold text-ink">{t.resetPassword.heading}</h2>
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
      <h2 className="font-serif text-2xl font-semibold text-ink">{t.resetPassword.heading}</h2>

      {!token && (
        <p role="alert" className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {t.resetPassword.missingToken}
        </p>
      )}

      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="reset-password-new" className="text-sm font-medium text-ink/70">
            {t.resetPassword.newPasswordLabel}
          </label>
          <input
            id="reset-password-new"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className={inputClasses}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="reset-password-confirm" className="text-sm font-medium text-ink/70">
            {t.resetPassword.confirmPasswordLabel}
          </label>
          <input
            id="reset-password-confirm"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className={inputClasses}
          />
        </div>

        {error && (
          <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <button type="submit" disabled={submitting || !token} className={primaryButton}>
          {t.resetPassword.submit}
        </button>
      </form>
    </section>
  );
}
