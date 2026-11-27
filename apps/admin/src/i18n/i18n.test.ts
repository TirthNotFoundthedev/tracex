import { en as sharedEn, findMissingTranslations } from "@tracex/ui";
import { describe, expect, test } from "vitest";

import { en } from "./en";
import { hi } from "./hi";
import { t } from "./index";

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
const keys = Object.keys(en) as (keyof typeof en)[];

describe("admin catalogs", () => {
  test("Hindi catalog has every English key with non-empty text", () => {
    expect(findMissingTranslations(en, hi)).toEqual([]);
  });

  test("Hindi catalog has no key that English lacks", () => {
    expect(Object.keys(hi).filter((key) => !(key in en))).toEqual([]);
  });

  test.each(keys)("%s uses the same placeholders in both languages", (key) => {
    expect(placeholders(hi[key])).toEqual(placeholders(en[key]));
  });

  test("no key repeats a string that packages/ui already owns", () => {
    expect(keys.filter((key) => key in sharedEn)).toEqual([]);
  });

  test("Hindi text is not copied English", () => {
    const copied = keys.filter(
      (key) => hi[key] === en[key] && /[a-z]{4}/i.test(en[key]) && key !== "title",
    );
    expect(copied).toEqual([]);
  });

  test("English text has none of the words the design rules ban (DESIGN_RULES section 7)", () => {
    // Admin may say "threshold", "score" and "strength"; the rest stay banned.
    const banned =
      /\b(entity|entities|same_as|confidence|tier|band|jurisdiction|forbidden|invalid|null|undefined|exception|query|ingest|403|404)\b/i;
    expect(Object.entries(en).filter(([, text]) => banned.test(text))).toEqual([]);
  });

  test("every screen A1 to A8 and the shell has strings", () => {
    const prefixes = [
      "nav.",
      "signIn.",
      "state.",
      "common.",
      "upload.",
      "matching.",
      "queue.",
      "approvals.",
      "users.",
      "audit.",
      "thresholds.",
      "graphPage.",
    ];
    for (const prefix of prefixes) {
      expect(keys.some((key) => key.startsWith(prefix))).toBe(true);
    }
  });

  test("the spec's reopen and approvals wording is kept word for word", () => {
    expect(en["queue.reopen.yes"]).toBe("Yes, reopen");
    expect(en["approvals.sent"]).toBe(
      "Sent for approval. Nothing changes until a senior officer approves it.",
    );
    expect(en["matching.noStop"]).toBe("A run cannot be stopped. Please wait.");
  });

  test("the Matching page offers no cancel text", () => {
    const hits = keys.filter((key) => key.startsWith("matching.") && /\bcancel\b/i.test(en[key]));
    expect(hits).toEqual([]);
  });
});

describe("t", () => {
  test("fills placeholders in both languages", () => {
    expect(t("queue.position", "en", { n: 3, total: 14 })).toBe("Link 3 of 14");
    expect(t("queue.position", "hi", { n: 3, total: 14 })).toBe("लिंक 3 / 14");
  });

  test("leaves an unfilled placeholder visible", () => {
    expect(t("queue.position")).toBe("Link {n} of {total}");
  });

  test("reads a shared key from packages/ui", () => {
    expect(t("role.senior", "en")).toBe("Senior officer");
    expect(t("error.safetyPause", "hi").length).toBeGreaterThan(0);
  });
});
