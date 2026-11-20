import { useCallback, useMemo, useState, type ReactNode } from "react";

import { readPreference, writePreference } from "../preferences/storage";
import { I18nContext, LANGUAGE_STORAGE_KEY, parseLanguage } from "./context";
import { translations, type Language } from "./translations";

function detectBrowserLanguage(fallback: Language): Language {
  if (typeof navigator === "undefined") {
    return fallback;
  }
  const candidate = navigator.languages?.[0] ?? navigator.language ?? "";
  if (!candidate) {
    return fallback;
  }
  return candidate.toLowerCase().startsWith("zh") ? "zh" : "en";
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
  defaultLanguage
}: {
  children: ReactNode;
  defaultLanguage?: Language;
}) {
  const [language, setLanguageState] = useState<Language>(() =>
    readPreference(
      LANGUAGE_STORAGE_KEY,
      defaultLanguage ?? detectBrowserLanguage("zh"),
      parseLanguage
    )
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
