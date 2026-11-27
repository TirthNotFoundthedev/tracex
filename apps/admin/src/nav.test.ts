import { describe, expect, test } from "vitest";

import { entryForPath, navFor, type Role } from "./nav";

const ids = (role: Role) => navFor(role).map((entry) => entry.id);

describe("navigation by role", () => {
  test("ADMIN has no review queue and no network graph (both are 404 for ADMIN)", () => {
    expect(ids("ADMIN")).toEqual([
      "upload",
      "matching",
      "approvals",
      "users",
      "audit",
      "thresholds",
    ]);
  });

  test("SUPERVISOR decides links and access, reads the audit log, and has no system pages", () => {
    expect(ids("SUPERVISOR")).toEqual(["reviewQueue", "approvals", "audit", "graph"]);
  });

  test("SENIOR sees approvals, users, thresholds and the audit log, not upload or matching", () => {
    expect(ids("SENIOR")).toEqual([
      "reviewQueue",
      "approvals",
      "users",
      "audit",
      "thresholds",
      "graph",
    ]);
  });

  test("JUNIOR and INVESTIGATOR have no admin pages", () => {
    expect(ids("JUNIOR")).toEqual([]);
    expect(ids("INVESTIGATOR")).toEqual([]);
  });

  test("every entry has a path, an icon and a label key", () => {
    for (const role of ["SUPERVISOR", "SENIOR", "ADMIN"] as const) {
      for (const entry of navFor(role)) {
        expect(entry.path.startsWith("/")).toBe(true);
        expect(entry.icon.length).toBeGreaterThan(0);
        expect(entry.labelKey.startsWith("nav.")).toBe(true);
      }
    }
  });
});

describe("entryForPath", () => {
  test("finds the entry the role may open", () => {
    expect(entryForPath("SENIOR", "/thresholds")?.id).toBe("thresholds");
  });

  test("a page the role has no menu item for is not found", () => {
    expect(entryForPath("SUPERVISOR", "/upload")).toBeUndefined();
    expect(entryForPath("ADMIN", "/review")).toBeUndefined();
  });

  test("a sub-path belongs to its section", () => {
    expect(entryForPath("SUPERVISOR", "/review/abc")?.id).toBe("reviewQueue");
  });
});
