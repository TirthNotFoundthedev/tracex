import { en } from "./en";
import { hi } from "./hi";

const catalogs = { en, hi };

export type Language = keyof typeof catalogs;
export type MessageKey = keyof typeof en;

export function isMessageKey(key: string): key is MessageKey {
  return key in en;
}

/** Text for `key`. `{name}` placeholders are replaced from `params`; an unknown placeholder is left as written. */
export function t(
  key: MessageKey,
  lang: Language = "en",
  params: Record<string, string | number> = {},
): string {
  return catalogs[lang][key].replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in params ? String(params[name]) : whole,
  );
}
