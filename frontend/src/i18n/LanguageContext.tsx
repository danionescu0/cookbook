import { createContext, useContext, useState } from "react";
import type { ReactNode } from "react";
import { DEFAULT_LANGUAGE, isLanguage, type Language } from "./config";
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
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

function readStoredLanguage(): Language {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored && isLanguage(stored) ? stored : DEFAULT_LANGUAGE;
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(readStoredLanguage);

  const setLanguage = (next: Language) => {
    setLanguageState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t: dictionaries[language] }}>
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
