import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { readPreference, writePreference } from "../preferences/storage";
import { translations, type Language } from "./translations";

type I18nContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (key: string, variables?: Record<string, string | number>) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);
const LANGUAGE_STORAGE_KEY = "quantfish-language";

function parseLanguage(value: unknown): Language | null {
  return value === "en" || value === "zh" ? value : null;
}

function getNestedValue(obj: Record<string, unknown>, path: string): unknown {
  return path.split(".").reduce<unknown>((current, key) => {
    if (current === null || current === undefined) {
      return undefined;
    }
    return (current as Record<string, unknown>)[key];
  }, obj);
}

function interpolate(template: string, variables: Record<string, string | number> = {}): string {
  return template.replace(/\{(\w+)\}/g, (_, name) => {
    const value = variables[name];
    return value !== undefined ? String(value) : `{${name}}`;
  });
}

export function I18nProvider({
  children,
  defaultLanguage = "zh"
}: {
  children: ReactNode;
  defaultLanguage?: Language;
}) {
  const [language, setLanguageState] = useState<Language>(() =>
    readPreference(LANGUAGE_STORAGE_KEY, defaultLanguage, parseLanguage)
  );

  const setLanguage = useCallback((next: Language) => {
    setLanguageState(next);
    writePreference(LANGUAGE_STORAGE_KEY, next);
  }, []);

  const t = useCallback(
    (key: string, variables?: Record<string, string | number>) => {
      const dictionary = translations[language] as Record<string, unknown>;
      const value = getNestedValue(dictionary, key);
      if (typeof value !== "string") {
        return `[${key}]`;
      }
      return interpolate(value, variables);
    },
    [language]
  );

  const value = useMemo(
    () => ({ language, setLanguage, t }),
    [language, setLanguage, t]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return context;
}
