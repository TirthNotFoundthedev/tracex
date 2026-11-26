import { findMissingTranslations } from "@tracex/ui";
import { describe, expect, test } from "vitest";

import { en } from "./en";
import { hi } from "./hi";
import { t } from "./index";

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe("officer catalogs", () => {
  test("Hindi catalog has every English key with non-empty text", () => {
    expect(findMissingTranslations(en, hi)).toEqual([]);
  });

  test("Hindi catalog has no key that English lacks", () => {
    expect(Object.keys(hi).filter((key) => !(key in en))).toEqual([]);
  });

  test.each(Object.keys(en) as (keyof typeof en)[])(
    "%s uses the same placeholders in both languages",
    (key) => {
      expect(placeholders(hi[key])).toEqual(placeholders(en[key]));
    },
  );

  test("Hindi text is not copied English", () => {
    const copied = (Object.keys(en) as (keyof typeof en)[]).filter(
      (key) => hi[key] === en[key] && /[a-z]{4}/i.test(en[key]) && key !== "title",
    );
    expect(copied).toEqual([]);
  });

  test("English text has none of the words the design rules ban (DESIGN_RULES section 7)", () => {
    const banned =
      /\b(entity|entities|same_as|confidence|score|threshold|tier|band|jurisdiction|forbidden|invalid|null|undefined|exception|query|ingest|403|404)\b/i;
    const hits = Object.entries(en).filter(([, text]) => banned.test(text));
    expect(hits).toEqual([]);
  });

  test("every screen O1 to O12 has strings, including the busy-system message", () => {
    const prefixes = [
      "signIn.",
      "cases.",
      "case.",
      "item.",
      "also.",
      "why.",
      "reject.",
      "decided.",
      "restricted.",
      "access.",
      "sent.",
      "state.",
    ];
    for (const prefix of prefixes) {
      expect(Object.keys(en).some((key) => key.startsWith(prefix))).toBe(true);
    }
    expect(en["state.runInProgress"]).toMatch(/try again/i);
  });
});

describe("t", () => {
  test("fills placeholders in both languages", () => {
    expect(t("case.title", "en", { number: "24/118" })).toBe("Case 24/118");
    expect(t("case.title", "hi", { number: "24/118" })).toBe("मामला 24/118");
  });

  test("leaves an unfilled placeholder visible rather than hiding it", () => {
    expect(t("case.title")).toBe("Case {number}");
  });
});
