import { useCallback, useEffect, useState, useSyncExternalStore, type ReactNode } from "react";

import {
  getInitialTheme,
  resolveTheme,
  ThemeContext,
  writeStoredTheme,
  type Theme
} from "./context";

const SYSTEM_THEME_QUERY = "(prefers-color-scheme: light)";

function subscribeToSystemTheme(onChange: () => void): () => void {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return () => {};
  }
  const media = window.matchMedia(SYSTEM_THEME_QUERY);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

function getSystemTheme(): "dark" | "light" {
  return resolveTheme("system");
}

function getServerTheme(): "dark" | "light" {
  return "dark";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);
  // `resolvedTheme` is derived, not stored: for the "system" setting the answer
  // lives in the media query, so it is read through `useSyncExternalStore` and a
  // media change re-renders this component instead of an effect copying it into
  // state.
  const systemTheme = useSyncExternalStore(subscribeToSystemTheme, getSystemTheme, getServerTheme);
  const resolvedTheme = theme === "system" ? systemTheme : theme;

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    writeStoredTheme(next);
  }, []);

  const cycleTheme = useCallback(() => {
    const order: Theme[] = ["dark", "light", "system"];
    const next = order[(order.indexOf(theme) + 1) % order.length];
    setTheme(next);
  }, [theme, setTheme]);

  // The only remaining effect is the DOM side effect: keep `data-theme` on the
  // document in step with the resolved value. CSS reads it, so it has to happen
  // after the value is known but never writes React state.
  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme;
  }, [resolvedTheme]);

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme, cycleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}
