import type { Language } from "../../shared/i18n";

export function formatDateTime(value: string, language: Language = "en"): string {
  const dateTime = new Intl.DateTimeFormat(language === "zh" ? "zh-CN" : "en-US", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short"
  });
  return dateTime.format(new Date(value));
}

export function formatScore(value: number, _language: Language = "en"): string {
  return value.toFixed(1);
}

export function formatPercent(value: number, _language: Language = "en"): string {
  return `${(value * 100).toFixed(1)}%`;
}
