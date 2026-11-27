import { readFileSync } from "node:fs";
import { expect, test } from "vitest";

const css = readFileSync(`${import.meta.dirname}/app.css`, "utf8");

/** Body of the first rule whose selector text matches `selector`. */
function rule(selector: string, from = 0): string {
  const at = css.indexOf(selector, from);
  expect(at, `rule ${selector}`).toBeGreaterThanOrEqual(0);
  return css.slice(css.indexOf("{", at) + 1, css.indexOf("}", at));
}

/** Everything from the first phone media query after `anchor`. */
function phone(anchor: string): string {
  const from = css.indexOf(anchor);
  expect(from, `anchor ${anchor}`).toBeGreaterThanOrEqual(0);
  const at = css.indexOf("@media (max-width: 40em)", from);
  expect(at, `phone query after ${anchor}`).toBeGreaterThanOrEqual(0);
  return css.slice(at, css.indexOf("\n}\n", at));
}

test("body has no browser margin and uses the token font, colour and background", () => {
  const body = rule("\nbody {");
  expect(body).toMatch(/margin:\s*0/);
  expect(body).toMatch(/font-family:\s*var\(--font-sans\)/);
  expect(body).toMatch(/color:\s*var\(--color-ink\)/);
  expect(body).toMatch(/background:\s*var\(--color-paper\)/);
});

test("the table caption repeats the page title, so it is visually hidden but stays readable", () => {
  const caption = rule(".admin-main .tx-table__caption");
  expect(caption).toMatch(/position:\s*absolute/);
  expect(caption).toMatch(/clip-path:\s*inset\(50%\)/);
});

test("the three score zones wrap or stack on a phone", () => {
  expect(rule(".admin-zones {")).toMatch(/flex-wrap:\s*wrap/);
  expect(phone(".admin-zones {")).toMatch(/\.admin-zone\b/);
});

test("link actions stack one per row on a phone, in order, full width", () => {
  const block = phone(".admin-actions {");
  expect(block).toMatch(/\.admin-actions\s*\{[^}]*flex-direction:\s*column/);
  expect(block).toMatch(/\.admin-actions \.tx-button\s*\{[^}]*inline-size:\s*100%/);
});

test("the menu collapses on a phone and its button shows only there", () => {
  expect(rule(".admin-menu__toggle {")).toMatch(/display:\s*none/);
  const block = phone(".admin-menu__toggle {");
  expect(block).toMatch(/\.admin-menu__toggle\s*\{[^}]*display:\s*block/);
  expect(block).toMatch(/\.admin-menu\[data-open="false"\] \.tx-sidenav\s*\{[^}]*display:\s*none/);
});

test("case numbers and dates in tables do not break", () => {
  expect(rule(".admin-nowrap {")).toMatch(/white-space:\s*nowrap/);
});
