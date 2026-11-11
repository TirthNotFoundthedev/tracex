import { findMissingTranslations } from "@tracex/ui";
import { expect, test } from "vitest";

import { en } from "./en";
import { hi } from "./hi";

test("Hindi catalog has every English key with non-empty text", () => {
  expect(findMissingTranslations(en, hi)).toEqual([]);
});
