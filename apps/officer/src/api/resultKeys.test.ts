import { describe, expect, test } from "vitest";

import { en } from "../i18n/en";
import { hi } from "../i18n/hi";
import { failureKeys, messageKeyFor } from "./resultKeys";

const kinds = [
  "sessionExpired",
  "notFound",
  "notAllowed",
  "tryAgainShortly",
  "conflict",
  "invalid",
  "tooManyAttempts",
  "networkError",
  "safetyPause",
  "serverError",
] as const;

describe("result kinds to i18n keys", () => {
  test("the table covers exactly the failure kinds", () => {
    expect(Object.keys(failureKeys).sort()).toEqual([...kinds].sort());
  });

  test.each(kinds)("%s has text in English and Hindi", (kind) => {
    const key = failureKeys[kind];
    expect(en[key].length).toBeGreaterThan(0);
    expect(hi[key].length).toBeGreaterThan(0);
  });

  test("notFound never uses a restricted string", () => {
    expect(messageKeyFor({ kind: "notFound" })).toBe("state.notFound");
    for (const key of Object.values(failureKeys)) expect(key.startsWith("restricted.")).toBe(false);
  });

  test("safetyPause has its own key, not the server-problem key", () => {
    expect(messageKeyFor({ kind: "safetyPause" })).not.toBe(messageKeyFor({ kind: "serverError" }));
  });
});
