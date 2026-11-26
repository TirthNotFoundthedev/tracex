import { en } from "./en";
import { hi } from "./hi";

export { en, hi };
export { findMissingTranslations } from "./parity";

export const catalogs = { en, hi };

export type Language = keyof typeof catalogs;
export type SharedMessageKey = keyof typeof en;

export function tShared(key: SharedMessageKey, lang: Language = "en"): string {
  return catalogs[lang][key];
}

/** Fill `{name}` slots. A slot with no value stays visible so a missing value is noticed. */
export function format(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (whole, name: string) => {
    const value = values[name];
    return value === undefined ? whole : String(value);
  });
}
