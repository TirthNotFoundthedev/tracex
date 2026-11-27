import type { EntityType } from "./entity";

/** One phone format for the whole app: "90000 14471". Masked values, UPI IDs and other text stay as they are. */
export function groupPhone(value: string): string {
  const compact = value.replace(/[\s-]/g, "");
  const prefixed = /^(\+91)(\d{10})$/.exec(compact);
  if (prefixed) return `${prefixed[1]} ${group(prefixed[2] ?? "")}`;
  return /^\d{10}$/.test(compact) ? group(compact) : value;
}

const group = (digits: string) => `${digits.slice(0, 5)} ${digits.slice(5)}`;

/** The value of an item as the officer reads it. */
export function displayValue(type: EntityType, value: string): string {
  return type === "PHONE" ? groupPhone(value) : value;
}

/** Names and places arrive in lower case from matching. A capital starts each word; other scripts stay as they are. */
export function titleCase(value: string): string {
  return value.replace(/(^|[\s(/-])(\p{Ll})/gu, (_all, before: string, letter: string) => {
    return `${before}${letter.toUpperCase()}`;
  });
}
