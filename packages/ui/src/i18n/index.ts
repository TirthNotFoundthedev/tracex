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
