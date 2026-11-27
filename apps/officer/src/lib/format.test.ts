import { describe, expect, test } from "vitest";

import { formatDate } from "./format";

describe("formatDate", () => {
  test("English writes the month in full", () => {
    expect(formatDate("2026-11-27", "en")).toBe("27 November 2026");
    expect(formatDate("2026-03-03T10:00:00Z", "en")).toBe("3 March 2026");
  });

  test("Hindi writes the month in full, with no abbreviation sign", () => {
    expect(formatDate("2026-11-27", "hi")).toBe("27 नवंबर 2026");
    expect(formatDate("2026-11-27", "hi")).not.toContain("॰");
  });

  test("a date without time is not moved by the time zone", () => {
    expect(formatDate("1990-04-12", "en")).toBe("12 April 1990");
  });

  test("a value that is not a date comes back as it was", () => {
    expect(formatDate("not a date", "en")).toBe("not a date");
  });
});
