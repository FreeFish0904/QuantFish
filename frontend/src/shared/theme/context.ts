import { createContext } from "react";

export type Theme = "dark" | "light" | "system";

const STORAGE_KEY = "quantfish-theme";

export type ThemeContextValue = {
  theme: Theme;
  resolvedTheme: "dark" | "light";
  setTheme: (theme: Theme) => void;
  cycleTheme: () => void;
};

// The provider and the `useTheme` hook both need the context object; keeping it
// in its own module lets each of them export only one kind of thing, which is
// what React Fast Refresh requires (`react-refresh/only-export-components`).
export const ThemeContext = createContext<ThemeContextValue | null>(null);

export function getStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const ls = window.localStorage;
    if (
      ls !== null &&
      typeof ls === "object" &&
      typeof ls.getItem === "function" &&
      typeof ls.setItem === "function"
    ) {
      return ls;
    }
  } catch {
    return null;
  }
  return null;
}

export function readStoredTheme(): Theme | null {
  const storage = getStorage();
  if (!storage) {
    return null;
  }
  try {
    const stored = storage.getItem(STORAGE_KEY) as Theme | null;
    if (stored === "dark" || stored === "light" || stored === "system") {
      return stored;
    }
  } catch {
    return null;
  }
  return null;
}

export function getInitialTheme(): Theme {
  return readStoredTheme() ?? "system";
}

export function resolveTheme(theme: Theme): "dark" | "light" {
  if (theme !== "system") {
    return theme;
  }
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return "dark";
  }
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function writeStoredTheme(theme: Theme): void {
  const storage = getStorage();
  if (!storage) {
    return;
  }
  try {
    storage.setItem(STORAGE_KEY, theme);
  } catch {
    // ignore storage errors
  }
}
