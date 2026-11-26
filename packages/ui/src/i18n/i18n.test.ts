import { expect, test } from "vitest";

import { en, findMissingTranslations, hi, tShared } from "./index";

test("shared Hindi catalog has every English key with non-empty text", () => {
  expect(findMissingTranslations(en, hi)).toEqual([]);
});

test("shared strings exist for 409 run in progress and the 503 safety pause, in both languages", () => {
  expect(tShared("error.runInProgress", "en")).toBe(
    "A matching run is in progress. Try again in a few minutes.",
  );
  expect(tShared("error.safetyPause", "en")).toBe(
    "The system is paused for a safety check. Try again later.",
  );
  for (const key of ["error.runInProgress", "error.safetyPause"] as const) {
    expect(tShared(key, "hi").trim()).not.toBe("");
    expect(tShared(key, "hi")).not.toBe(tShared(key, "en"));
  }
});

test("parity check reports missing and blank Hindi keys", () => {
  expect(findMissingTranslations({ a: "A", b: "B", c: "C" }, { a: "ए", b: "  " })).toEqual([
    "b",
    "c",
  ]);
});
