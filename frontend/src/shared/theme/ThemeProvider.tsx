import { useCallback, useEffect, useState, type ReactNode } from "react";

import {
  getInitialTheme,
  resolveTheme,
  ThemeContext,
  writeStoredTheme,
  type Theme
} from "./context";

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);
  const [resolvedTheme, setResolvedTheme] = useState<"dark" | "light">(() =>
    resolveTheme(getInitialTheme())
  );

  const applyTheme = useCallback((next: Theme) => {
    const resolved = resolveTheme(next);
    setResolvedTheme(resolved);
    document.documentElement.dataset.theme = resolved;
  }, []);

  const setTheme = useCallback(
    (next: Theme) => {
      setThemeState(next);
      writeStoredTheme(next);
      applyTheme(next);
    },
    [applyTheme]
  );

  const cycleTheme = useCallback(() => {
    const order: Theme[] = ["dark", "light", "system"];
    const next = order[(order.indexOf(theme) + 1) % order.length];
    setTheme(next);
  }, [theme, setTheme]);

  useEffect(() => {
    applyTheme(theme);
  }, [applyTheme, theme]);

  useEffect(() => {
    if (theme !== "system" || typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const media = window.matchMedia("(prefers-color-scheme: light)");
    const handler = () => applyTheme("system");
    media.addEventListener("change", handler);
    return () => media.removeEventListener("change", handler);
  }, [applyTheme, theme]);

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme, cycleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}
