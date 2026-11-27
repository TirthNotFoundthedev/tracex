import { describe, expect, test } from "vitest";

import { t } from "../i18n";
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
    expect(t(key, "en").length).toBeGreaterThan(0);
    expect(t(key, "hi").length).toBeGreaterThan(0);
    expect(t(key, "en")).not.toMatch(/\{\w+\}/);
  });

  test("run in progress and safety pause use the shared strings", () => {
    expect(messageKeyFor({ kind: "tryAgainShortly" })).toBe("error.runInProgress");
    expect(messageKeyFor({ kind: "safetyPause" })).toBe("error.safetyPause");
  });

  test("notFound never uses access wording (D65)", () => {
    expect(messageKeyFor({ kind: "notFound" })).toBe("state.notFound");
    for (const lang of ["en", "hi"] as const) {
      expect(t("state.notFound", lang)).not.toMatch(/access|permission|police area|पहुँच|थाना/i);
    }
    for (const key of Object.values(failureKeys)) expect(key.startsWith("restricted.")).toBe(false);
  });

  test("a changed-meanwhile conflict is not the busy-system message", () => {
    expect(messageKeyFor({ kind: "conflict", code: "NOT_PENDING" })).toBe("state.changedMeanwhile");
  });

  test("safetyPause has its own key, not the server-problem key", () => {
    expect(messageKeyFor({ kind: "safetyPause" })).not.toBe(messageKeyFor({ kind: "serverError" }));
  });
});
