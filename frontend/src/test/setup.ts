import "@testing-library/jest-dom/vitest";
import { server } from "./server";

// Pin the jsdom locale so component tests keep the Chinese default while the
// i18n suite can still override `navigator.language` to assert detection.
Object.defineProperty(window.navigator, "language", {
  value: "zh-CN",
  configurable: true
});
Object.defineProperty(window.navigator, "languages", {
  value: ["zh-CN"],
  configurable: true
});

// Node.js 25+ exposes a built-in globalThis.localStorage stub that lacks
// Storage methods and emits a warning on access. jsdom under Vitest can
// inherit it, so we install a minimal in-memory Storage when needed.
if (
  typeof window !== "undefined" &&
  (!window.localStorage || typeof window.localStorage.clear !== "function")
) {
  const memory = new Map<string, string>();
  const storage: Storage = {
    get length() {
      return memory.size;
    },
    key(index: number): string | null {
      return Array.from(memory.keys())[index] ?? null;
    },
    getItem(key: string): string | null {
      return memory.get(String(key)) ?? null;
    },
    setItem(key: string, value: string): void {
      memory.set(String(key), String(value));
    },
    removeItem(key: string): void {
      memory.delete(String(key));
    },
    clear(): void {
      memory.clear();
    }
  };
  Object.defineProperty(window, "localStorage", {
    value: storage,
    configurable: true,
    writable: true
  });
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  window.localStorage.clear();
});
afterAll(() => server.close());
