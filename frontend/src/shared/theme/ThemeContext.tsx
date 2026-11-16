import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode
} from "react";

export type Theme = "dark" | "light" | "system";

const STORAGE_KEY = "quantfish-theme";

function getStorage(): Storage | null {
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

function readStoredTheme(): Theme | null {
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

function getInitialTheme(): Theme {
  return readStoredTheme() ?? "system";
}

function resolveTheme(theme: Theme): "dark" | "light" {
  if (theme !== "system") {
    return theme;
  }
  if (
    typeof window === "undefined" ||
    typeof window.matchMedia !== "function"
  ) {
    return "dark";
  }
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

type ThemeContextValue = {
  theme: Theme;
  resolvedTheme: "dark" | "light";
  setTheme: (theme: Theme) => void;
  cycleTheme: () => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

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
      const storage = getStorage();
      if (storage) {
        try {
          storage.setItem(STORAGE_KEY, next);
        } catch {
          // ignore storage errors
        }
      }
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

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
