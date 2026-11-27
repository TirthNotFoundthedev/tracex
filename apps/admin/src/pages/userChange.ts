import type { components } from "../api/schema";
import type { Role } from "../nav";

type Schemas = components["schemas"];
export type Coverage = Schemas["Coverage"];
type Create = Schemas["ProposeUserCreate"];
type RoleChange = Schemas["ProposeUserRole"];
type AreaChange = Schemas["ProposeUserJurisdiction"];

/** From GET /roles: what a role works through. DISTRICT: one district. COVERAGE: a set of areas. NONE: no area. */
export type Scope = "DISTRICT" | "COVERAGE" | "NONE";
export type ScopeOf = (role: Role) => Scope;

/** What the person has picked in the form. Both kinds can hold values while the role is being changed. */
export interface AreaDraft {
  districtId: string;
  all: boolean;
  stateIds: string[];
  districtIds: string[];
}

export const EMPTY_AREA: AreaDraft = { districtId: "", all: false, stateIds: [], districtIds: [] };

export type Built<T> =
  { ok: true; body: T } | { ok: false; field: "name" | "username" | "role" | "area" };

/**
 * The coverage as the contract wants it: `all_states` is a real boolean, the id lists have no duplicates.
 * "All areas" empties the lists. Nothing picked is `undefined`, so a caller cannot send an empty coverage.
 */
export function coverageOf(draft: AreaDraft): Coverage | undefined {
  if (draft.all) return { all_states: true, state_ids: [], district_ids: [] };
  const state_ids = [...new Set(draft.stateIds)];
  const district_ids = [...new Set(draft.districtIds)];
  if (state_ids.length === 0 && district_ids.length === 0) return undefined;
  return { all_states: false, state_ids, district_ids };
}

/**
 * The one place that decides which area key goes on the wire. The contract's oneOf is not enforced by the
 * generated type, so this builds exactly one of `district_id` or `coverage` by scope, or none for NONE,
 * and says "missing" when the person has not picked what the scope needs (never a request with neither).
 */
function areaKeys(
  scope: Scope,
  area: AreaDraft,
): { district_id: string } | { coverage: Coverage } | Record<string, never> | undefined {
  if (scope === "DISTRICT") return area.districtId ? { district_id: area.districtId } : undefined;
  if (scope === "COVERAGE") {
    const coverage = coverageOf(area);
    return coverage ? { coverage } : undefined;
  }
  return {};
}

const USERNAME_PATTERN = /^[a-z0-9._-]+$/;
const USERNAME_MIN = 3;
const USERNAME_MAX = 64;
const NAME_MAX = 120;

/** The limits the sign-in name and the display name must meet before a proposal is sent. */
export const usernameFits = (username: string) =>
  username.length >= USERNAME_MIN &&
  username.length <= USERNAME_MAX &&
  USERNAME_PATTERN.test(username);
export const nameFits = (name: string) => name.length > 0 && name.length <= NAME_MAX;

export function buildCreate(input: {
  name: string;
  username: string;
  role: Role | "";
  scopeOf: ScopeOf;
  area: AreaDraft;
}): Built<Create> {
  const display_name = input.name.trim();
  const username = input.username.trim();
  if (!display_name || !nameFits(display_name)) return { ok: false, field: "name" };
  if (!usernameFits(username)) return { ok: false, field: "username" };
  if (!input.role) return { ok: false, field: "role" };
  const keys = areaKeys(input.scopeOf(input.role), input.area);
  if (!keys) return { ok: false, field: "area" };
  return {
    ok: true,
    body: { kind: "USER_CREATE", new_value: { username, display_name, role: input.role, ...keys } },
  };
}

/**
 * What a role change must carry (D72, access spec section 3.2): coverage when the new role is SENIOR; a
 * district when a SENIOR or ADMIN becomes a district role; nothing otherwise.
 */
export function areaNeededForRoleChange(
  from: Role,
  to: Role,
  scopeOf: ScopeOf,
): "coverage" | "district" | "none" {
  const target = scopeOf(to);
  if (target === "COVERAGE") return "coverage";
  if (target === "DISTRICT" && scopeOf(from) !== "DISTRICT") return "district";
  return "none";
}

export function buildRoleChange(input: {
  subjectId: string;
  from: Role;
  to: Role;
  scopeOf: ScopeOf;
  area: AreaDraft;
}): Built<RoleChange> {
  const needed = areaNeededForRoleChange(input.from, input.to, input.scopeOf);
  const keys =
    needed === "coverage"
      ? areaKeys("COVERAGE", input.area)
      : needed === "district"
        ? areaKeys("DISTRICT", input.area)
        : {};
  if (!keys) return { ok: false, field: "area" };
  return {
    ok: true,
    body: {
      kind: "USER_ROLE",
      subject_user_id: input.subjectId,
      new_value: { role: input.to, ...keys },
    },
  };
}

export function buildAreaChange(input: {
  subjectId: string;
  role: Role;
  scopeOf: ScopeOf;
  area: AreaDraft;
}): Built<AreaChange> {
  const scope = input.scopeOf(input.role);
  // An administrator has no area to change.
  if (scope === "NONE") return { ok: false, field: "area" };
  const keys = areaKeys(scope, input.area);
  if (!keys) return { ok: false, field: "area" };
  return {
    ok: true,
    body: {
      kind: "USER_JURISDICTION",
      subject_user_id: input.subjectId,
      new_value: keys as AreaChange["new_value"],
    },
  };
}
