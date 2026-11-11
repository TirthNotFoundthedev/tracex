/** Keys present in `en` that are missing or blank in `hi`. */
export function findMissingTranslations(
  en: Record<string, string>,
  hi: Record<string, string | undefined>,
): string[] {
  return Object.keys(en).filter((key) => (hi[key] ?? "").trim() === "");
}
