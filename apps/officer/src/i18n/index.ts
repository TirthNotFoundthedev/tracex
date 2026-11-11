import { en } from "./en";
import { hi } from "./hi";

const catalogs = { en, hi };

export type Language = keyof typeof catalogs;
export type MessageKey = keyof typeof en;

export function t(key: MessageKey, lang: Language = "en"): string {
  return catalogs[lang][key];
}
