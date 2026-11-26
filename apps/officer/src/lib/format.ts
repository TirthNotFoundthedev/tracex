import type { Language } from "../i18n";

const LOCALE: Record<Language, string> = { en: "en-IN", hi: "hi-IN" };

/** "3 Mar 2026" from a date ("2026-03-03") or a date-time. A date without time is read as local, not UTC. */
export function formatDate(value: string, lang: Language): string {
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  const date = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(LOCALE[lang], {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}
