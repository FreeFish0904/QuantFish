import { createContext } from "react";

import type { Language } from "./translations";

export type I18nContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (key: string, variables?: Record<string, string | number>) => string;
};

// Shared by the provider and the `useI18n` hook so neither module has to import
// the other: a component file that also exports a hook defeats React Fast
// Refresh (`react-refresh/only-export-components`).
export const I18nContext = createContext<I18nContextValue | null>(null);

export const LANGUAGE_STORAGE_KEY = "quantfish-language";

export function parseLanguage(value: unknown): Language | null {
  return value === "en" || value === "zh" ? value : null;
}
