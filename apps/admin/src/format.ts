import type { Language } from "./i18n";

/** "12 Mar 2026, 14:05" style date and time in the page language. */
export function dateTime(iso: string, lang: Language): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(lang === "hi" ? "hi-IN" : "en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
