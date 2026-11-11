import { expect, test } from "vitest";

import { en, findMissingTranslations, hi } from "./index";

test("shared Hindi catalog has every English key with non-empty text", () => {
  expect(findMissingTranslations(en, hi)).toEqual([]);
});

test("parity check reports missing and blank Hindi keys", () => {
  expect(findMissingTranslations({ a: "A", b: "B", c: "C" }, { a: "ए", b: "  " })).toEqual([
    "b",
    "c",
  ]);
});
