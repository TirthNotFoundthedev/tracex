import { describe, expect, test } from "vitest";

import { displayValue, groupPhone, titleCase } from "./value";

describe("groupPhone", () => {
  test("ten digits are shown as two groups of five, whatever the stored spacing", () => {
    expect(groupPhone("9000014471")).toBe("90000 14471");
    expect(groupPhone("90000 14471")).toBe("90000 14471");
    expect(groupPhone("90000-14471")).toBe("90000 14471");
  });

  test("a +91 prefix is kept and the rest is grouped", () => {
    expect(groupPhone("+919000014471")).toBe("+91 90000 14471");
  });

  test("masked values, UPI IDs and other text come back unchanged", () => {
    expect(groupPhone("98xxxx1234")).toBe("98xxxx1234");
    expect(groupPhone("9000053742@upi")).toBe("9000053742@upi");
    expect(groupPhone("12345")).toBe("12345");
  });
});

describe("displayValue", () => {
  test("only phone items are grouped", () => {
    expect(displayValue("PHONE", "9000014471")).toBe("90000 14471");
    expect(displayValue("ACCOUNT", "5010000055501")).toBe("5010000055501");
    expect(displayValue("PERSON", "Arjun Mehra")).toBe("Arjun Mehra");
  });
});

describe("titleCase", () => {
  test("lower case stored names and places start each word with a capital", () => {
    expect(titleCase("arjun mehra")).toBe("Arjun Mehra");
    expect(titleCase("shivpuri")).toBe("Shivpuri");
    expect(titleCase("mohd. irfan")).toBe("Mohd. Irfan");
  });

  test("Hindi text is not changed", () => {
    expect(titleCase("अर्जुन मेहरा")).toBe("अर्जुन मेहरा");
  });
});
