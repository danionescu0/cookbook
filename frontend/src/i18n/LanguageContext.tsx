import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api/client";
import { DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, isLanguage, type Language } from "./config";
import en from "./translations/en";
import ro from "./translations/ro";
import type { Translation } from "./translations/en";

const dictionaries: Record<Language, Translation> = { en, ro };

export const LANGUAGE_STORAGE_KEY = "cookbook-language";
const STORAGE_KEY = LANGUAGE_STORAGE_KEY;

interface LanguageContextValue {
  language: Language;
  setLanguage: (language: Language) => void;
  t: Translation;
  // Which languages this deployment actually has enabled (Backoffice > Settings), narrowed to
  // the ones we have a translation dictionary for — SUPPORTED_LANGUAGES until that resolves (or
  // if it fails/is unmocked in a test), since a new language needs a matching translations/*.ts
  // file added in code regardless of what the DB setting says.
  supportedLanguages: Language[];
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

function readStoredLanguage(): Language {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored && isLanguage(stored) ? stored : DEFAULT_LANGUAGE;
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(readStoredLanguage);
  const [supportedLanguages, setSupportedLanguages] = useState<Language[]>([...SUPPORTED_LANGUAGES]);

  useEffect(() => {
    // Guarded rather than called unconditionally: many existing tests mock `../api/client` with
    // only the methods they need, so `getLanguages` may not exist on the mock at all.
    const fetchLanguages = api.getLanguages;
    if (!fetchLanguages) return;
    fetchLanguages()
      .then((data) => {
        const supported = data.supported.filter(isLanguage);
        if (supported.length > 0) setSupportedLanguages(supported);
      })
      .catch(() => {
        // Offline/unreachable — the hardcoded fallback keeps the app functional.
      });
  }, []);

  const setLanguage = (next: Language) => {
    setLanguageState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  };

  return (
    <LanguageContext.Provider
      value={{ language, setLanguage, t: dictionaries[language], supportedLanguages }}
    >
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }
  return context;
}
