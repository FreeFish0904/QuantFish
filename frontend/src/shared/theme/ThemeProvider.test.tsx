import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ThemeProvider, useTheme } from ".";

const originalLocalStorage = Object.getOwnPropertyDescriptor(window, "localStorage");
const originalMatchMedia = Object.getOwnPropertyDescriptor(window, "matchMedia");

function ThemeProbe() {
  const { cycleTheme, resolvedTheme, theme } = useTheme();

  return (
    <button onClick={cycleTheme} type="button">
      {theme}:{resolvedTheme}
    </button>
  );
}

afterEach(() => {
  if (originalLocalStorage) {
    Object.defineProperty(window, "localStorage", originalLocalStorage);
  }
  if (originalMatchMedia) {
    Object.defineProperty(window, "matchMedia", originalMatchMedia);
  } else {
    delete (window as { matchMedia?: unknown }).matchMedia;
  }
  document.documentElement.removeAttribute("data-theme");
});

describe("ThemeProvider", () => {
  it("falls back when localStorage access is blocked", async () => {
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get() {
        throw new Error("localStorage is blocked");
      }
    });

    expect(() => {
      render(
        <ThemeProvider>
          <ThemeProbe />
        </ThemeProvider>
      );
    }).not.toThrow();

    const user = userEvent.setup();
    await expect(user.click(screen.getByRole("button"))).resolves.toBeUndefined();
    expect(screen.getByRole("button")).toHaveTextContent("dark:dark");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  });

  it("follows the OS preference while the theme is system", () => {
    const listeners = new Set<() => void>();
    let prefersLight = false;
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: (query: string) => ({
        media: query,
        matches: prefersLight,
        addEventListener: (_event: string, listener: () => void) => listeners.add(listener),
        removeEventListener: (_event: string, listener: () => void) => listeners.delete(listener)
      })
    });

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>
    );
    expect(screen.getByRole("button")).toHaveTextContent("system:dark");

    // The media query is the source of truth for "system", so flipping it has to
    // re-render the provider without any effect copying the value into state.
    act(() => {
      prefersLight = true;
      for (const listener of listeners) {
        listener();
      }
    });

    expect(screen.getByRole("button")).toHaveTextContent("system:light");
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
  });
});
