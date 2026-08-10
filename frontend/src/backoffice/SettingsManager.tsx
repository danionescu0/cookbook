import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { primaryButton } from "../ui/buttonStyles";
import type { AiProvider, Settings } from "../types";

const inputClasses =
  "rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none";

interface FormState {
  supportedLanguages: string;
  defaultLanguage: string;
  anthropicApiKey: string;
  calorieNinjasApiKey: string;
  rateLimit: string;
  scrapeTimeoutSeconds: string;
  maxHtmlChars: string;
  imageMaxDimension: string;
  imageMaxSizeKb: string;
  smtpHost: string;
  smtpPort: string;
  smtpUsername: string;
  smtpFromAddress: string;
  smtpPassword: string;
  smtpUseTls: boolean;
  turnstileSiteKey: string;
  turnstileSecretKey: string;
  googleClientId: string;
  publicSiteUrl: string;
  backofficeRecipesPageSize: string;
  maxImportsPerUser: string;
  contactRecipientEmail: string;
  preferredAiProvider: AiProvider;
  deepseekApiKey: string;
}

function toFormState(settings: Settings): FormState {
  return {
    supportedLanguages: settings.supported_languages,
    defaultLanguage: settings.default_language,
    anthropicApiKey: "",
    calorieNinjasApiKey: "",
    rateLimit: String(settings.default_rate_limit_requests_per_minute),
    scrapeTimeoutSeconds: String(settings.scrape_timeout_seconds),
    maxHtmlChars: String(settings.max_html_chars),
    imageMaxDimension: String(settings.image_max_dimension),
    imageMaxSizeKb: String(settings.image_max_size_kb),
    smtpHost: settings.smtp_host,
    smtpPort: String(settings.smtp_port),
    smtpUsername: settings.smtp_username,
    smtpFromAddress: settings.smtp_from_address,
    smtpPassword: "",
    smtpUseTls: settings.smtp_use_tls,
    turnstileSiteKey: settings.turnstile_site_key,
    turnstileSecretKey: "",
    googleClientId: settings.google_client_id,
    publicSiteUrl: settings.public_site_url,
    backofficeRecipesPageSize: String(settings.backoffice_recipes_page_size),
    maxImportsPerUser: String(settings.max_imports_per_user),
    contactRecipientEmail: settings.contact_recipient_email,
    preferredAiProvider: settings.preferred_ai_provider,
    deepseekApiKey: "",
  };
}

interface FieldProps {
  id: string;
  label: string;
  help: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
}

function Field({ id, label, help, value, onChange, type = "text", placeholder }: FieldProps) {
  // These are admin config values, never a login credential — but a `type="password"` field is
  // still a magnet for the browser's saved-password autofill, which will happily overwrite one
  // with an unrelated saved credential the moment the form is submitted (this is exactly how a
  // real Anthropic API key got clobbered with a login password during testing). "new-password"
  // is the value browsers actually respect for "don't suggest an existing saved password here".
  const autoComplete = type === "password" ? "new-password" : "off";
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium text-ink/70">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        className={inputClasses}
      />
      <p className="text-xs text-ink/60">{help}</p>
    </div>
  );
}

export function SettingsManager() {
  const { t } = useLanguage();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api
      .getSettings()
      .then((loaded) => {
        setSettings(loaded);
        setForm(toFormState(loaded));
      })
      .catch((e) => setError(String(e)));
  }, []);

  const update = (patch: Partial<FormState>) => {
    setSaved(false);
    setForm((prev) => (prev ? { ...prev, ...patch } : prev));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form) return;
    setError(null);
    setSaving(true);
    try {
      const updated = await api.updateSettings({
        supported_languages: form.supportedLanguages.trim(),
        default_language: form.defaultLanguage.trim(),
        ...(form.anthropicApiKey ? { anthropic_api_key: form.anthropicApiKey } : {}),
        ...(form.calorieNinjasApiKey ? { calorie_ninjas_api_key: form.calorieNinjasApiKey } : {}),
        default_rate_limit_requests_per_minute: Number(form.rateLimit),
        scrape_timeout_seconds: Number(form.scrapeTimeoutSeconds),
        max_html_chars: Number(form.maxHtmlChars),
        image_max_dimension: Number(form.imageMaxDimension),
        image_max_size_kb: Number(form.imageMaxSizeKb),
        smtp_host: form.smtpHost.trim(),
        smtp_port: Number(form.smtpPort),
        smtp_username: form.smtpUsername.trim(),
        smtp_from_address: form.smtpFromAddress.trim(),
        ...(form.smtpPassword ? { smtp_password: form.smtpPassword } : {}),
        smtp_use_tls: form.smtpUseTls,
        turnstile_site_key: form.turnstileSiteKey.trim(),
        ...(form.turnstileSecretKey ? { turnstile_secret_key: form.turnstileSecretKey } : {}),
        google_client_id: form.googleClientId.trim(),
        public_site_url: form.publicSiteUrl.trim(),
        backoffice_recipes_page_size: Number(form.backofficeRecipesPageSize),
        max_imports_per_user: Number(form.maxImportsPerUser),
        contact_recipient_email: form.contactRecipientEmail.trim(),
        preferred_ai_provider: form.preferredAiProvider,
        ...(form.deepseekApiKey ? { deepseek_api_key: form.deepseekApiKey } : {}),
      });
      setSettings(updated);
      setForm(toFormState(updated));
      setSaved(true);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  if (!settings || !form) {
    return (
      <section
        aria-labelledby="settings-heading"
        className="rounded-lg bg-cream-card p-5 ring-1 ring-black/5"
      >
        <h2 id="settings-heading" className="font-serif text-2xl font-semibold text-ink">
          {t.settingsManager.heading}
        </h2>
        {error && (
          <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
      </section>
    );
  }

  const secretPlaceholder = (isSet: boolean) =>
    isSet ? t.settingsManager.secretSetPlaceholder : t.settingsManager.secretUnsetPlaceholder;

  return (
    <section
      aria-labelledby="settings-heading"
      className="rounded-lg bg-cream-card p-5 ring-1 ring-black/5"
    >
      <h2 id="settings-heading" className="font-serif text-2xl font-semibold text-ink">
        {t.settingsManager.heading}
      </h2>

      <form onSubmit={handleSubmit} className="mt-4 grid gap-5 sm:grid-cols-2">
        <Field
          id="settings-supported-languages"
          label={t.settingsManager.supportedLanguagesLabel}
          help={t.settingsManager.supportedLanguagesHelp}
          value={form.supportedLanguages}
          onChange={(v) => update({ supportedLanguages: v })}
        />
        <Field
          id="settings-default-language"
          label={t.settingsManager.defaultLanguageLabel}
          help={t.settingsManager.defaultLanguageHelp}
          value={form.defaultLanguage}
          onChange={(v) => update({ defaultLanguage: v })}
        />
        <div className="flex flex-col gap-1">
          <label htmlFor="settings-preferred-ai-provider" className="text-sm font-medium text-ink/70">
            {t.settingsManager.preferredAiProviderLabel}
          </label>
          <select
            id="settings-preferred-ai-provider"
            value={form.preferredAiProvider}
            onChange={(e) => update({ preferredAiProvider: e.target.value as AiProvider })}
            className={inputClasses}
          >
            <option value="claude">{t.settingsManager.preferredAiProviderClaude}</option>
            <option value="deepseek">{t.settingsManager.preferredAiProviderDeepseek}</option>
          </select>
          <p className="text-xs text-ink/60">{t.settingsManager.preferredAiProviderHelp}</p>
        </div>
        <Field
          id="settings-anthropic-api-key"
          type="password"
          label={t.settingsManager.anthropicApiKeyLabel}
          help={t.settingsManager.anthropicApiKeyHelp}
          value={form.anthropicApiKey}
          placeholder={secretPlaceholder(settings.anthropic_api_key_is_set)}
          onChange={(v) => update({ anthropicApiKey: v })}
        />
        <Field
          id="settings-deepseek-api-key"
          type="password"
          label={t.settingsManager.deepseekApiKeyLabel}
          help={t.settingsManager.deepseekApiKeyHelp}
          value={form.deepseekApiKey}
          placeholder={secretPlaceholder(settings.deepseek_api_key_is_set)}
          onChange={(v) => update({ deepseekApiKey: v })}
        />
        <Field
          id="settings-calorie-ninjas-api-key"
          type="password"
          label={t.settingsManager.calorieNinjasApiKeyLabel}
          help={t.settingsManager.calorieNinjasApiKeyHelp}
          value={form.calorieNinjasApiKey}
          placeholder={secretPlaceholder(settings.calorie_ninjas_api_key_is_set)}
          onChange={(v) => update({ calorieNinjasApiKey: v })}
        />
        <Field
          id="settings-rate-limit"
          type="number"
          label={t.settingsManager.rateLimitLabel}
          help={t.settingsManager.rateLimitHelp}
          value={form.rateLimit}
          onChange={(v) => update({ rateLimit: v })}
        />
        <Field
          id="settings-scrape-timeout"
          type="number"
          label={t.settingsManager.scrapeTimeoutLabel}
          help={t.settingsManager.scrapeTimeoutHelp}
          value={form.scrapeTimeoutSeconds}
          onChange={(v) => update({ scrapeTimeoutSeconds: v })}
        />
        <Field
          id="settings-max-html-chars"
          type="number"
          label={t.settingsManager.maxHtmlCharsLabel}
          help={t.settingsManager.maxHtmlCharsHelp}
          value={form.maxHtmlChars}
          onChange={(v) => update({ maxHtmlChars: v })}
        />
        <Field
          id="settings-image-max-dimension"
          type="number"
          label={t.settingsManager.imageMaxDimensionLabel}
          help={t.settingsManager.imageMaxDimensionHelp}
          value={form.imageMaxDimension}
          onChange={(v) => update({ imageMaxDimension: v })}
        />
        <Field
          id="settings-image-max-size-kb"
          type="number"
          label={t.settingsManager.imageMaxSizeKbLabel}
          help={t.settingsManager.imageMaxSizeKbHelp}
          value={form.imageMaxSizeKb}
          onChange={(v) => update({ imageMaxSizeKb: v })}
        />
        <Field
          id="settings-backoffice-recipes-page-size"
          type="number"
          label={t.settingsManager.backofficeRecipesPageSizeLabel}
          help={t.settingsManager.backofficeRecipesPageSizeHelp}
          value={form.backofficeRecipesPageSize}
          onChange={(v) => update({ backofficeRecipesPageSize: v })}
        />
        <Field
          id="settings-max-imports-per-user"
          type="number"
          label={t.settingsManager.maxImportsPerUserLabel}
          help={t.settingsManager.maxImportsPerUserHelp}
          value={form.maxImportsPerUser}
          onChange={(v) => update({ maxImportsPerUser: v })}
        />
        <Field
          id="settings-public-site-url"
          label={t.settingsManager.publicSiteUrlLabel}
          help={t.settingsManager.publicSiteUrlHelp}
          value={form.publicSiteUrl}
          placeholder="https://cookbook.example.com"
          onChange={(v) => update({ publicSiteUrl: v })}
        />
        <Field
          id="settings-contact-recipient-email"
          type="email"
          label={t.settingsManager.contactRecipientEmailLabel}
          help={t.settingsManager.contactRecipientEmailHelp}
          value={form.contactRecipientEmail}
          onChange={(v) => update({ contactRecipientEmail: v })}
        />
        <Field
          id="settings-smtp-host"
          label={t.settingsManager.smtpHostLabel}
          help={t.settingsManager.smtpHostHelp}
          value={form.smtpHost}
          onChange={(v) => update({ smtpHost: v })}
        />
        <Field
          id="settings-smtp-port"
          type="number"
          label={t.settingsManager.smtpPortLabel}
          help={t.settingsManager.smtpPortHelp}
          value={form.smtpPort}
          onChange={(v) => update({ smtpPort: v })}
        />
        <Field
          id="settings-smtp-username"
          label={t.settingsManager.smtpUsernameLabel}
          help={t.settingsManager.smtpUsernameHelp}
          value={form.smtpUsername}
          onChange={(v) => update({ smtpUsername: v })}
        />
        <Field
          id="settings-smtp-from-address"
          label={t.settingsManager.smtpFromAddressLabel}
          help={t.settingsManager.smtpFromAddressHelp}
          value={form.smtpFromAddress}
          onChange={(v) => update({ smtpFromAddress: v })}
        />
        <Field
          id="settings-smtp-password"
          type="password"
          label={t.settingsManager.smtpPasswordLabel}
          help={t.settingsManager.smtpPasswordHelp}
          value={form.smtpPassword}
          placeholder={secretPlaceholder(settings.smtp_password_is_set)}
          onChange={(v) => update({ smtpPassword: v })}
        />
        <div className="flex flex-col gap-1">
          <label htmlFor="settings-smtp-use-tls" className="flex items-center gap-2 text-sm font-medium text-ink/70">
            <input
              id="settings-smtp-use-tls"
              type="checkbox"
              checked={form.smtpUseTls}
              onChange={(e) => update({ smtpUseTls: e.target.checked })}
            />
            {t.settingsManager.smtpUseTlsLabel}
          </label>
          <p className="text-xs text-ink/60">{t.settingsManager.smtpUseTlsHelp}</p>
        </div>
        <Field
          id="settings-turnstile-site-key"
          label={t.settingsManager.turnstileSiteKeyLabel}
          help={t.settingsManager.turnstileSiteKeyHelp}
          value={form.turnstileSiteKey}
          onChange={(v) => update({ turnstileSiteKey: v })}
        />
        <Field
          id="settings-turnstile-secret-key"
          type="password"
          label={t.settingsManager.turnstileSecretKeyLabel}
          help={t.settingsManager.turnstileSecretKeyHelp}
          value={form.turnstileSecretKey}
          placeholder={secretPlaceholder(settings.turnstile_secret_key_is_set)}
          onChange={(v) => update({ turnstileSecretKey: v })}
        />
        <Field
          id="settings-google-client-id"
          label={t.settingsManager.googleClientIdLabel}
          help={t.settingsManager.googleClientIdHelp}
          value={form.googleClientId}
          onChange={(v) => update({ googleClientId: v })}
        />

        <div className="sm:col-span-2">
          <button type="submit" disabled={saving} className={primaryButton}>
            {saving ? t.settingsManager.applying : t.settingsManager.apply}
          </button>
        </div>
      </form>

      {error && (
        <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
      {saved && !error && (
        <p role="status" className="mt-3 rounded-md bg-olive-light px-3 py-2 text-sm text-ink">
          {t.settingsManager.applied}
        </p>
      )}
    </section>
  );
}
