import { describe, expect, test } from "vitest";

import {
  areaNeededForRoleChange,
  buildAreaChange,
  buildCreate,
  buildRoleChange,
  coverageOf,
  EMPTY_AREA,
  type Scope,
} from "./userChange";
import type { Role } from "../nav";

const D1 = "11111111-1111-4111-8111-111111111111";
const D2 = "22222222-2222-4222-8222-222222222222";
const S1 = "33333333-3333-4333-8333-333333333333";
const SUBJECT = "44444444-4444-4444-8444-444444444444";

const SCOPE: Record<Role, Scope> = {
  JUNIOR: "DISTRICT",
  INVESTIGATOR: "DISTRICT",
  SUPERVISOR: "DISTRICT",
  SENIOR: "COVERAGE",
  ADMIN: "NONE",
};
const scopeOf = (role: Role) => SCOPE[role];

const person = { name: "Ravi Kumar", username: "ravi" };

describe("exactly one of district_id or coverage", () => {
  test("a district role sends district_id and never coverage, even when a coverage was picked first", () => {
    const built = buildCreate({
      ...person,
      role: "SUPERVISOR",
      scopeOf,
      area: { districtId: D1, all: true, stateIds: [S1], districtIds: [D2] },
    });
    expect(built).toEqual({
      ok: true,
      body: {
        kind: "USER_CREATE",
        new_value: {
          username: "ravi",
          display_name: "Ravi Kumar",
          role: "SUPERVISOR",
          district_id: D1,
        },
      },
    });
  });

  test("SENIOR sends coverage and never district_id, even when a district was picked first", () => {
    const built = buildCreate({
      ...person,
      role: "SENIOR",
      scopeOf,
      area: { districtId: D1, all: false, stateIds: [S1], districtIds: [D2] },
    });
    expect(built.ok && built.body.new_value).toEqual({
      username: "ravi",
      display_name: "Ravi Kumar",
      role: "SENIOR",
      coverage: { all_states: false, state_ids: [S1], district_ids: [D2] },
    });
    expect(built.ok && "district_id" in built.body.new_value).toBe(false);
  });

  test("neither is refused for a district role and for SENIOR", () => {
    expect(buildCreate({ ...person, role: "JUNIOR", scopeOf, area: EMPTY_AREA })).toEqual({
      ok: false,
      field: "area",
    });
    expect(buildCreate({ ...person, role: "SENIOR", scopeOf, area: EMPTY_AREA })).toEqual({
      ok: false,
      field: "area",
    });
  });

  test("an administrator has no area: neither key is sent", () => {
    const built = buildCreate({
      ...person,
      role: "ADMIN",
      scopeOf,
      area: { districtId: D1, all: true, stateIds: [S1], districtIds: [D2] },
    });
    expect(built.ok && Object.keys(built.body.new_value).sort()).toEqual([
      "display_name",
      "role",
      "username",
    ]);
  });

  test("an area change sends one of the two by the user's role", () => {
    const toDistrict = buildAreaChange({
      subjectId: SUBJECT,
      role: "SUPERVISOR",
      scopeOf,
      area: { districtId: D2, all: true, stateIds: [], districtIds: [] },
    });
    expect(toDistrict.ok && toDistrict.body.new_value).toEqual({ district_id: D2 });
    const toCoverage = buildAreaChange({
      subjectId: SUBJECT,
      role: "SENIOR",
      scopeOf,
      area: { districtId: D2, all: false, stateIds: [], districtIds: [D1] },
    });
    expect(toCoverage.ok && toCoverage.body.new_value).toEqual({
      coverage: { all_states: false, state_ids: [], district_ids: [D1] },
    });
    expect(
      buildAreaChange({ subjectId: SUBJECT, role: "JUNIOR", scopeOf, area: EMPTY_AREA }).ok,
    ).toBe(false);
  });
});

describe("a role change across the SENIOR boundary (D72)", () => {
  test("what the form must ask for", () => {
    expect(areaNeededForRoleChange("SUPERVISOR", "SENIOR", scopeOf)).toBe("coverage");
    expect(areaNeededForRoleChange("JUNIOR", "SENIOR", scopeOf)).toBe("coverage");
    expect(areaNeededForRoleChange("ADMIN", "SENIOR", scopeOf)).toBe("coverage");
    expect(areaNeededForRoleChange("SENIOR", "SUPERVISOR", scopeOf)).toBe("district");
    expect(areaNeededForRoleChange("ADMIN", "JUNIOR", scopeOf)).toBe("district");
    expect(areaNeededForRoleChange("JUNIOR", "SUPERVISOR", scopeOf)).toBe("none");
    expect(areaNeededForRoleChange("SENIOR", "ADMIN", scopeOf)).toBe("none");
    expect(areaNeededForRoleChange("SUPERVISOR", "ADMIN", scopeOf)).toBe("none");
  });

  test("to SENIOR carries coverage and not the old district", () => {
    const built = buildRoleChange({
      subjectId: SUBJECT,
      from: "SUPERVISOR",
      to: "SENIOR",
      scopeOf,
      area: { districtId: D1, all: true, stateIds: [], districtIds: [] },
    });
    expect(built).toEqual({
      ok: true,
      body: {
        kind: "USER_ROLE",
        subject_user_id: SUBJECT,
        new_value: {
          role: "SENIOR",
          coverage: { all_states: true, state_ids: [], district_ids: [] },
        },
      },
    });
  });

  test("from SENIOR to a district role carries district_id and not the old coverage", () => {
    const built = buildRoleChange({
      subjectId: SUBJECT,
      from: "SENIOR",
      to: "SUPERVISOR",
      scopeOf,
      area: { districtId: D2, all: true, stateIds: [S1], districtIds: [] },
    });
    expect(built).toEqual({
      ok: true,
      body: {
        kind: "USER_ROLE",
        subject_user_id: SUBJECT,
        new_value: { role: "SUPERVISOR", district_id: D2 },
      },
    });
  });

  test("a change that needs the area is refused without it", () => {
    const base = { subjectId: SUBJECT, scopeOf, area: EMPTY_AREA };
    expect(buildRoleChange({ ...base, from: "JUNIOR", to: "SENIOR" }).ok).toBe(false);
    expect(buildRoleChange({ ...base, from: "SENIOR", to: "JUNIOR" }).ok).toBe(false);
  });

  test("any other role change carries the role alone", () => {
    const area = { districtId: D1, all: true, stateIds: [S1], districtIds: [D2] };
    const base = { subjectId: SUBJECT, scopeOf, area };
    const a = buildRoleChange({ ...base, from: "JUNIOR", to: "SUPERVISOR" });
    const b = buildRoleChange({ ...base, from: "SENIOR", to: "ADMIN" });
    expect(a.ok && a.body.new_value).toEqual({ role: "SUPERVISOR" });
    expect(b.ok && b.body.new_value).toEqual({ role: "ADMIN" });
  });
});

describe("coverage", () => {
  test("all_states is a real boolean and id lists are unique", () => {
    const some = coverageOf({
      districtId: "",
      all: false,
      stateIds: [S1, S1],
      districtIds: [D1, D2, D1],
    });
    expect(some).toEqual({ all_states: false, state_ids: [S1], district_ids: [D1, D2] });
    const all = coverageOf({ districtId: "", all: true, stateIds: [S1], districtIds: [D1] });
    expect(all).toEqual({ all_states: true, state_ids: [], district_ids: [] });
    expect(typeof all?.all_states).toBe("boolean");
  });

  test("an empty coverage is nothing", () => {
    expect(coverageOf(EMPTY_AREA)).toBeUndefined();
  });
});
