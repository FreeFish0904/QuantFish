export type PreferenceParser<T> = (value: unknown) => T | null;

export type PreferenceFieldParsers<T extends Record<string, unknown>> = {
  [K in keyof T]: PreferenceParser<T[K]>;
};

function getStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const storage = window.localStorage;
    if (
      storage &&
      typeof storage.getItem === "function" &&
      typeof storage.setItem === "function"
    ) {
      return storage;
    }
  } catch {
    return null;
  }
  return null;
}

export function readPreference<T>(
  key: string,
  fallback: T,
  parse: PreferenceParser<T>
): T {
  const storage = getStorage();
  if (!storage) {
    return fallback;
  }

  try {
    const stored = storage.getItem(key);
    if (stored === null) {
      return fallback;
    }
    return parse(JSON.parse(stored)) ?? fallback;
  } catch {
    return fallback;
  }
}

export function readObjectPreference<T extends Record<string, unknown>>(
  key: string,
  defaults: T,
  parsers: PreferenceFieldParsers<T>
): T {
  return readPreference(key, defaults, (value) => {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return null;
    }

    const stored = value as Record<string, unknown>;
    const result = { ...defaults };
    for (const key_ of Object.keys(parsers) as Array<keyof T>) {
      const parsed = parsers[key_](stored[String(key_)]);
      if (parsed !== null) {
        result[key_] = parsed;
      }
    }
    return result;
  });
}

export function writePreference<T>(key: string, value: T): void {
  const storage = getStorage();
  if (!storage) {
    return;
  }
  try {
    storage.setItem(key, JSON.stringify(value));
  } catch {
    // Preference persistence should never block the UI.
  }
}
