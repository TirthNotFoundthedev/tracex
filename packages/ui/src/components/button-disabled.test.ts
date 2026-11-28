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
    for (const s of (m[1] ?? "").split(",")) out.push(s.replace(/\s+/g, " ").trim());
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

  test("a disabled button gets the disabled look from the attribute or from aria-disabled", () => {
    const rule = selectors().filter((x) => x.startsWith(".tx-button") && x.includes("disabled"));
    expect(rule).toContain(".tx-button:disabled");
    expect(rule).toContain('.tx-button[aria-disabled="true"]');
  });

  // These rules set a background or colour with more specificity than the disabled rule,
  // so they must apply to enabled buttons only.
  const overrides = [
    ".tx-topbar .tx-button",
    '.tx-restricted .tx-button[data-variant="secondary"]',
    '.tx-message[data-kind="error"] .tx-button[data-variant="secondary"]',
  ];
  test.each(overrides)("%s applies to enabled buttons only", (base) => {
    const found = selectors().filter((x) => x.startsWith(base) && !/:(hover|active)/.test(x));
    expect(found.length).toBeGreaterThan(0);
    for (const x of found) {
      expect(x).toContain(":not(:disabled)");
      expect(x).toContain(':not([aria-disabled="true"])');
    }
  });
});
