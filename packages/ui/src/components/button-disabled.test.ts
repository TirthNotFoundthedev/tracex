import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, test } from "vitest";

/**
 * jsdom does not apply :hover, so the check reads the stylesheet: a hover or active rule on a
 * button must skip disabled buttons, or it beats `.tx-button:disabled` on specificity and a
 * disabled primary button turns navy under the pointer (TIR-99).
 */
const css = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "ui.css"), "utf8");

function selectors(): string[] {
  const out: string[] = [];
  for (const m of css.matchAll(/([^{}]+)\{/g)) {
    for (const s of (m[1] ?? "").split(",")) out.push(s.trim());
  }
  return out;
}

describe("disabled buttons keep the disabled look (TIR-99)", () => {
  const interactive = selectors().filter(
    (s) => s.includes(".tx-button") && /:(hover|active)\b/.test(s),
  );

  test("there are hover rules to check", () => {
    expect(interactive.length).toBeGreaterThanOrEqual(3);
  });

  test.each(interactive)("%s skips disabled buttons", (selector) => {
    expect(selector).toContain(":not(:disabled)");
    expect(selector).toContain(':not([aria-disabled="true"])');
  });
});
