import { format, tShared, type Language, type SharedMessageKey } from "@tracex/ui";

import { en } from "./en";
import { hi } from "./hi";

const catalogs = { en, hi };

export type { Language };
export type MessageKey = keyof typeof en;
/** Any string the admin panel can show: its own, or one that packages/ui owns. */
export type AnyMessageKey = MessageKey | SharedMessageKey;

function isOwn(key: AnyMessageKey): key is MessageKey {
  return key in en;
}

/** Text for `key` in `lang`. Shared keys come from packages/ui. `{name}` slots are filled from `params`. */
export function t(
  key: AnyMessageKey,
  lang: Language = "en",
  params: Record<string, string | number> = {},
): string {
  const text = isOwn(key) ? catalogs[lang][key] : tShared(key, lang);
  return format(text, params);
}
