import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { I18nProvider, useI18n } from "./";

function Consumer() {
  const { t, language, setLanguage } = useI18n();
  return (
    <div>
      <span data-testid="language">{language}</span>
      <span data-testid="brand">{t("brand.name")}</span>
      <span data-testid="page">{t("common.pageInfo", { page: 2, totalPages: 5 })}</span>
      <span data-testid="missing">{t("missing.key")}</span>
      <button onClick={() => setLanguage("zh")}>Switch to Chinese</button>
    </div>
  );
}

describe("I18nProvider", () => {
  it("supports English dot-notation keys", () => {
    render(
      <I18nProvider defaultLanguage="en">
        <Consumer />
      </I18nProvider>
    );

    expect(screen.getByTestId("language")).toHaveTextContent("en");
    expect(screen.getByTestId("brand")).toHaveTextContent("QuantFish");
    expect(screen.getByTestId("page")).toHaveTextContent("Page 2 of 5");
    expect(screen.getByTestId("missing")).toHaveTextContent("[missing.key]");
  });

  it("switches to Chinese and interpolates variables", async () => {
    render(
      <I18nProvider defaultLanguage="en">
        <Consumer />
      </I18nProvider>
    );

    await userEvent.click(screen.getByRole("button", { name: /switch to chinese/i }));

    expect(screen.getByTestId("language")).toHaveTextContent("zh");
    expect(screen.getByTestId("brand")).toHaveTextContent("QuantFish");
    expect(screen.getByTestId("page")).toHaveTextContent("第 2 页，共 5 页");
  });

  it("restores a stored language preference on mount", () => {
    window.localStorage.setItem("quantfish-language", "\"en\"");

    render(
      <I18nProvider>
        <Consumer />
      </I18nProvider>
    );

    expect(screen.getByTestId("language")).toHaveTextContent("en");
    expect(screen.getByTestId("brand")).toHaveTextContent("QuantFish");
  });

  it("persists language changes for the next provider instance", async () => {
    const { unmount } = render(
      <I18nProvider defaultLanguage="en">
        <Consumer />
      </I18nProvider>
    );

    await userEvent.click(screen.getByRole("button", { name: /switch to chinese/i }));
    expect(window.localStorage.getItem("quantfish-language")).toBe("\"zh\"");

    unmount();
    render(
      <I18nProvider defaultLanguage="en">
        <Consumer />
      </I18nProvider>
    );

    expect(screen.getByTestId("language")).toHaveTextContent("zh");
  });

  it("follows the browser language when no preference is stored", () => {
    Object.defineProperty(window.navigator, "language", { value: "en-US", configurable: true });
    Object.defineProperty(window.navigator, "languages", { value: ["en-US"], configurable: true });

    try {
      render(
        <I18nProvider>
          <Consumer />
        </I18nProvider>
      );

      expect(screen.getByTestId("language")).toHaveTextContent("en");
      expect(screen.getByTestId("page")).toHaveTextContent("Page 2 of 5");
    } finally {
      Object.defineProperty(window.navigator, "language", { value: "zh-CN", configurable: true });
      Object.defineProperty(window.navigator, "languages", { value: ["zh-CN"], configurable: true });
    }
  });
});
