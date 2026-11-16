import { describe, expect, it } from "vitest";

import {
  readObjectPreference,
  readPreference,
  writePreference
} from "./storage";

type TablePreferences = {
  status: string;
  myAccountOnly: boolean;
};

describe("preference storage", () => {
  it("reads and writes JSON preferences", () => {
    writePreference("quantfish-test-language", "en");

    expect(window.localStorage.getItem("quantfish-test-language")).toBe("\"en\"");
    expect(
      readPreference("quantfish-test-language", "zh", (value) =>
        value === "en" || value === "zh" ? value : null
      )
    ).toBe("en");
  });

  it("falls back when stored JSON is malformed", () => {
    window.localStorage.setItem("quantfish-test-bad-json", "{");

    expect(
      readPreference("quantfish-test-bad-json", "zh", (value) =>
        value === "en" || value === "zh" ? value : null
      )
    ).toBe("zh");
  });

  it("ignores invalid object fields without discarding valid fields", () => {
    window.localStorage.setItem(
      "quantfish-test-table",
      JSON.stringify({ status: "failed", myAccountOnly: "yes" })
    );

    const preference = readObjectPreference<TablePreferences>(
      "quantfish-test-table",
      { status: "all", myAccountOnly: false },
      {
        status: (value) => (value === "all" || value === "failed" ? value : null),
        myAccountOnly: (value) => (typeof value === "boolean" ? value : null)
      }
    );

    expect(preference).toEqual({ status: "failed", myAccountOnly: false });
  });

  it("falls back when localStorage is unavailable", () => {
    const originalLocalStorage = Object.getOwnPropertyDescriptor(window, "localStorage");
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get() {
        throw new Error("localStorage is blocked");
      }
    });

    try {
      expect(
        readPreference("quantfish-test-blocked", "zh", (value) =>
          value === "en" || value === "zh" ? value : null
        )
      ).toBe("zh");
      expect(() => writePreference("quantfish-test-blocked", "en")).not.toThrow();
    } finally {
      if (originalLocalStorage) {
        Object.defineProperty(window, "localStorage", originalLocalStorage);
      }
    }
  });
});
