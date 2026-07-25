export const SUPPORTED_LANGUAGES = ["ro", "en"] as const;

export type Language = (typeof SUPPORTED_LANGUAGES)[number];

export const DEFAULT_LANGUAGE: Language = "ro";

export const LANGUAGE_LABELS: Record<Language, string> = {
  ro: "Română",
  en: "English",
};

export function isLanguage(value: string): value is Language {
  return (SUPPORTED_LANGUAGES as readonly string[]).includes(value);
}
