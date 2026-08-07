import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { TurnstileWidget } from "../auth/TurnstileWidget";
import { useLanguage } from "../i18n/LanguageContext";
import { primaryButton } from "../ui/buttonStyles";

const inputClasses =
  "rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_MESSAGE_LENGTH = 50;

type FieldName = "name" | "email" | "phone" | "message";

// Reachable both logged in and logged out — see the api's get_optional_current_user. A logged-in
// visitor skips the CAPTCHA entirely (already an authenticated account); an anonymous one must
// solve one, same as signup.
export function ContactPage() {
  const { t } = useLanguage();
  const { isAuthenticated } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [message, setMessage] = useState("");
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [siteKey, setSiteKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<FieldName, string>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    if (isAuthenticated) return;
    api
      .getPublicSettings()
      .then((settings) => setSiteKey(settings.turnstile_site_key))
      .catch(() => setSiteKey(""));
  }, [isAuthenticated]);

  // Format-only checks for a field that already has a value — required-ness (name, message,
  // email-or-phone) is a submit-time concern below, not a blur one, matching SignupForm's
  // reasoning: tabbing through untouched fields shouldn't light up the whole form in red.
  const validateField = (field: FieldName, value: string): string | null => {
    switch (field) {
      case "email":
        return value && !EMAIL_PATTERN.test(value) ? t.contact.emailInvalidError : null;
      case "message":
        return value && value.trim().length < MIN_MESSAGE_LENGTH
          ? t.contact.messageTooShortError
          : null;
      default:
        return null;
    }
  };

  const handleBlur = (field: FieldName, value: string) => {
    setFieldErrors((prev) => ({ ...prev, [field]: validateField(field, value) ?? undefined }));
  };

  const clearFieldError = (field: FieldName) => {
    if (fieldErrors[field]) {
      setFieldErrors((prev) => ({ ...prev, [field]: undefined }));
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    const nextFieldErrors: Partial<Record<FieldName, string>> = {
      email: validateField("email", email) ?? undefined,
      message: validateField("message", message) ?? undefined,
    };
    if (!name.trim()) nextFieldErrors.name = t.contact.nameRequiredError;
    if (!message.trim()) nextFieldErrors.message = t.contact.messageRequiredError;
    if (!email.trim() && !phone.trim()) {
      nextFieldErrors.email = t.contact.emailOrPhoneRequiredError;
      nextFieldErrors.phone = t.contact.emailOrPhoneRequiredError;
    }
    const cleanedErrors = Object.fromEntries(
      Object.entries(nextFieldErrors).filter(([, value]) => value)
    );
    if (Object.keys(cleanedErrors).length > 0) {
      setFieldErrors(cleanedErrors);
      return;
    }

    if (!isAuthenticated && !turnstileToken) {
      setError(t.contact.captchaRequiredError);
      return;
    }

    setSubmitting(true);
    try {
      await api.submitContactMessage({
        name: name.trim(),
        ...(email.trim() ? { email: email.trim() } : {}),
        ...(phone.trim() ? { phone: phone.trim() } : {}),
        message: message.trim(),
        ...(turnstileToken ? { turnstile_token: turnstileToken } : {}),
      });
      setSubmitted(true);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <section className="mx-auto max-w-sm rounded-lg bg-cream-card p-6 ring-1 ring-black/5">
        <h2 className="font-serif text-2xl font-semibold text-ink">{t.contact.heading}</h2>
        <p role="status" className="mt-4 rounded-md bg-olive-light px-3 py-2 text-sm text-ink">
          {t.contact.successMessage}
        </p>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-sm rounded-lg bg-cream-card p-6 ring-1 ring-black/5">
      <h2 className="font-serif text-2xl font-semibold text-ink">{t.contact.heading}</h2>
      <p className="mt-1 text-sm text-ink/60">{t.contact.intro}</p>

      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="contact-name" className="text-sm font-medium text-ink/70">
            {t.contact.nameLabel}
          </label>
          <input
            id="contact-name"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              clearFieldError("name");
            }}
            onBlur={(e) => handleBlur("name", e.target.value)}
            aria-invalid={Boolean(fieldErrors.name)}
            className={inputClasses}
          />
          {fieldErrors.name && (
            <p role="alert" className="text-xs text-red-700">
              {fieldErrors.name}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="contact-email" className="text-sm font-medium text-ink/70">
            {t.contact.emailLabel}
          </label>
          <input
            id="contact-email"
            type="email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              clearFieldError("email");
              clearFieldError("phone");
            }}
            onBlur={(e) => handleBlur("email", e.target.value)}
            aria-invalid={Boolean(fieldErrors.email)}
            className={inputClasses}
          />
          {fieldErrors.email && (
            <p role="alert" className="text-xs text-red-700">
              {fieldErrors.email}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="contact-phone" className="text-sm font-medium text-ink/70">
            {t.contact.phoneLabel}
          </label>
          <input
            id="contact-phone"
            type="tel"
            value={phone}
            onChange={(e) => {
              setPhone(e.target.value);
              clearFieldError("phone");
              clearFieldError("email");
            }}
            aria-invalid={Boolean(fieldErrors.phone)}
            className={inputClasses}
          />
          {fieldErrors.phone && (
            <p role="alert" className="text-xs text-red-700">
              {fieldErrors.phone}
            </p>
          )}
          <p className="text-xs text-ink/60">{t.contact.emailOrPhoneHelp}</p>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="contact-message" className="text-sm font-medium text-ink/70">
            {t.contact.messageLabel}
          </label>
          <textarea
            id="contact-message"
            value={message}
            onChange={(e) => {
              setMessage(e.target.value);
              clearFieldError("message");
            }}
            onBlur={(e) => handleBlur("message", e.target.value)}
            aria-invalid={Boolean(fieldErrors.message)}
            rows={5}
            className={inputClasses}
          />
          <p className="text-xs text-ink/60">
            {t.contact.messageHelp.replace("{min}", String(MIN_MESSAGE_LENGTH))}
          </p>
          {fieldErrors.message && (
            <p role="alert" className="text-xs text-red-700">
              {fieldErrors.message}
            </p>
          )}
        </div>

        {!isAuthenticated && siteKey && (
          <TurnstileWidget siteKey={siteKey} onToken={setTurnstileToken} />
        )}

        {error && (
          <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <button type="submit" disabled={submitting} className={primaryButton}>
          {t.contact.submit}
        </button>
      </form>
    </section>
  );
}
