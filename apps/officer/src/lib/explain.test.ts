import { describe, expect, test } from "vitest";

import { renderTemplate } from "./explain";

describe("reason sentences show values the way an officer reads them", () => {
  test("names and places are written with capitals", () => {
    expect(
      renderTemplate(
        "match.evidence.per_name_sim",
        { name_a: "arjun mehra", name_b: "arjun mehra" },
        "en",
      ),
    ).toBe("Names sound alike: Arjun Mehra / Arjun Mehra");
    expect(renderTemplate("match.evidence.per_locality", { place: "shivpuri" }, "en")).toBe(
      "Both are linked to the same area: Shivpuri.",
    );
  });

  test("dates of birth use the full date format in both languages, never 1990-04-12", () => {
    expect(
      renderTemplate(
        "match.evidence.per_dob_conflict",
        { dob_a: "1990-04-12", dob_b: "1978-09-30" },
        "en",
      ),
    ).toBe("Dates of birth differ: 12 April 1990 and 30 September 1978.");
    const hindi = renderTemplate("match.evidence.per_dob_match", { dob: "1990-04-12" }, "hi");
    expect(hindi).toContain("12 अप्रैल 1990");
    expect(hindi).not.toContain("1990-04-12");
  });

  test("a phone number in a sentence has the same grouping as in a title", () => {
    expect(
      renderTemplate("match.evidence.id_exact", { id_label: "PHONE", value: "9000046120" }, "en"),
    ).toBe("The same phone number 90000 46120 appears in both cases.");
  });
});
