import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ThemeProvider, useTheme } from "./ThemeContext";

const originalLocalStorage = Object.getOwnPropertyDescriptor(window, "localStorage");

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
});
