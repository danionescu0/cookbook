import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { primaryButton } from "../ui/buttonStyles";
import type { Settings } from "../types";

const inputClasses =
  "rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none";

interface FormState {
  supportedLanguages: string;
  defaultLanguage: string;
  adminPassword: string;
  anthropicApiKey: string;
  rateLimit: string;
  scrapeTimeoutSeconds: string;
  maxHtmlChars: string;
  imageMaxDimension: string;
  imageMaxSizeKb: string;
}

function toFormState(settings: Settings): FormState {
  return {
    supportedLanguages: settings.supported_languages,
    defaultLanguage: settings.default_language,
    adminPassword: "",
    anthropicApiKey: "",
    rateLimit: String(settings.default_rate_limit_requests_per_minute),
    scrapeTimeoutSeconds: String(settings.scrape_timeout_seconds),
    maxHtmlChars: String(settings.max_html_chars),
    imageMaxDimension: String(settings.image_max_dimension),
    imageMaxSizeKb: String(settings.image_max_size_kb),
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
        ...(form.adminPassword ? { admin_password: form.adminPassword } : {}),
        ...(form.anthropicApiKey ? { anthropic_api_key: form.anthropicApiKey } : {}),
        default_rate_limit_requests_per_minute: Number(form.rateLimit),
        scrape_timeout_seconds: Number(form.scrapeTimeoutSeconds),
        max_html_chars: Number(form.maxHtmlChars),
        image_max_dimension: Number(form.imageMaxDimension),
        image_max_size_kb: Number(form.imageMaxSizeKb),
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
        <Field
          id="settings-admin-password"
          type="password"
          label={t.settingsManager.adminPasswordLabel}
          help={t.settingsManager.adminPasswordHelp}
          value={form.adminPassword}
          placeholder={secretPlaceholder(settings.admin_password_is_set)}
          onChange={(v) => update({ adminPassword: v })}
        />
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
