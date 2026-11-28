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

function cssBlocks(): { selector: string; body: string }[] {
  return [...css.matchAll(/([^{}]+)\{([^}]*)\}/g)].map((m) => ({
    selector: (m[1] ?? "").replace(/\s+/g, " ").trim(),
    body: m[2] ?? "",
  }));
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
  test.each(overrides)("%s sets colours for enabled buttons only", (base) => {
    const found = selectors().filter((x) => x.startsWith(base) && !/:(hover|active)/.test(x));
    expect(
      found.some(
        (x) => x.includes(":not(:disabled)") && x.includes(':not([aria-disabled="true"])'),
      ),
    ).toBe(true);
    for (const b of cssBlocks()) {
      if (b.selector !== base) continue;
      expect(b.body).not.toMatch(/background|border-color|(^|[\s;])color:/);
    }
  });

  // A disabled button must not change size or position: layout stays on the plain rule.
  test("size and layout stay on the unconditional rules, only colours are enabled-only", () => {
    const blocks = cssBlocks();
    for (const b of blocks) {
      if (!b.selector.includes(":not(:disabled)") || /:(hover|active)/.test(b.selector)) continue;
      if (!b.selector.includes(".tx-button")) continue;
      expect(b.body).not.toMatch(/font-size|align-self|padding|margin|min-|inline-size|block-size/);
    }
    expect(
      blocks.some((b) => b.selector === ".tx-topbar .tx-button" && /font-size/.test(b.body)),
    ).toBe(true);
    expect(
      blocks.some(
        (b) =>
          b.selector === '.tx-restricted .tx-button[data-variant="secondary"]' &&
          /align-self/.test(b.body),
      ),
    ).toBe(true);
  });
});
