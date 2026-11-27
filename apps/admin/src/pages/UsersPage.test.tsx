import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { createApi } from "../api";
import { messageKeyFor } from "../api/resultKeys";
import { t } from "../i18n";
import type { Role } from "../nav";
import { fakeApi, json, renderPage, type Routes } from "../testing";
import { UsersPage } from "./UsersPage";

afterEach(cleanup);

const S1 = "a0000000-0000-4000-8000-000000000001";
const S2 = "a0000000-0000-4000-8000-000000000002";
const D1 = "b0000000-0000-4000-8000-000000000001";
const D2 = "b0000000-0000-4000-8000-000000000002";
const D3 = "b0000000-0000-4000-8000-000000000003";
const RAVI = "c0000000-0000-4000-8000-000000000001";
const MEENA = "c0000000-0000-4000-8000-000000000002";
const ASHA = "c0000000-0000-4000-8000-000000000003";
const HARI = "c0000000-0000-4000-8000-000000000004";
const CHG = "d0000000-0000-4000-8000-000000000001";

const jurisdictions = json(200, {
  items: [
    {
      state_id: S1,
      name: "Northvale",
      districts: [
        { district_id: D1, name: "Rivergate" },
        { district_id: D2, name: "Lakeside" },
      ],
    },
    { state_id: S2, name: "Eastmark", districts: [{ district_id: D3, name: "Hillcrest" }] },
  ],
});

const roles = json(200, {
  items: [
    { role: "JUNIOR", name_key: "role.junior", description_key: "role.junior.d", scope: "DISTRICT" },
    { role: "INVESTIGATOR", name_key: "role.investigator", description_key: "x", scope: "DISTRICT" },
    { role: "SUPERVISOR", name_key: "role.supervisor", description_key: "x", scope: "DISTRICT" },
    { role: "SENIOR", name_key: "role.senior", description_key: "x", scope: "COVERAGE" },
    { role: "ADMIN", name_key: "role.admin", description_key: "x", scope: "NONE" },
  ],
});

const ravi = {
  user_id: RAVI,
  username: "ravi",
  display_name: "Ravi Kumar",
  role: "SUPERVISOR",
  district_id: D1,
  coverage: null,
  active: true,
  assignment_count: 3,
};
const meena = {
  user_id: MEENA,
  username: "meena",
  display_name: "Meena Rao",
  role: "SENIOR",
  district_id: null,
  coverage: { all_states: true, state_ids: [], district_ids: [] },
  active: true,
  assignment_count: 0,
};
const asha = {
  user_id: ASHA,
  username: "asha",
  display_name: "Asha Devi",
  role: "JUNIOR",
  district_id: D2,
  coverage: null,
  active: true,
  assignment_count: 1,
};
const off = { ...asha, user_id: "c0000000-0000-4000-8000-000000000009", display_name: "Old Hand", username: "old", active: false };

const page = (items: unknown[]) => json(200, { items, next_cursor: null, total: items.length });

function change(over: Record<string, unknown> = {}) {
  return {
    change_id: CHG,
    kind: "USER_ROLE",
    state: "PENDING",
    subject: { user_id: RAVI, display_name: "Ravi Kumar", role: "SUPERVISOR" },
    old_value: { role: "SUPERVISOR" },
    new_value: { role: "INVESTIGATOR" },
    proposer: { user_id: HARI, display_name: "Hari", role: "ADMIN" },
    change_hash: "a".repeat(64),
    proposed_at: "2026-03-12T14:05:00Z",
    ...over,
  };
}

function setup(role: Role, over: Routes = {}) {
  const fake = fakeApi({
    "GET /users": page([ravi, meena, asha, off]),
    "GET /pending-changes": page([]),
    "GET /jurisdictions": jurisdictions,
    "GET /roles": roles,
    "POST /pending-changes": json(201, change()),
    ...over,
  });
  renderPage(<UsersPage api={fake.api} lang="en" role={role} />);
  return fake;
}

const posts = (calls: { method: string; path: string; init: RequestInit }[]) =>
  calls.filter((c) => c.method === "POST");
const bodyOf = (call: { init: RequestInit } | undefined) =>
  JSON.parse(String(call?.init.body)) as Record<string, unknown>;

async function openRow(name: string) {
  const cell = (await screen.findAllByText(name))[0] as HTMLElement;
  fireEvent.click(within(cell.closest("tr") as HTMLElement).getByRole("button", { name: "Open" }));
}

const field = (label: string) => screen.getByLabelText(label) as HTMLInputElement;
const pick = (label: string, value: string) =>
  fireEvent.change(field(label), { target: { value } });
const check = (name: string) => fireEvent.click(screen.getByRole("checkbox", { name }));
const save = () => fireEvent.click(screen.getByRole("button", { name: "Save user" }));
const SENT = "Sent for approval. Nothing changes until a senior officer approves it.";

// ------------------------------------------------------------------ list calls (D69, D71)

test.each(["ADMIN", "SENIOR"] as const)(
  "%s: rendering the list makes exactly four calls and reads no single user",
  async (role) => {
    const { calls } = setup(role);
    await screen.findByText("Ravi Kumar");
    expect(calls.map((c) => `${c.method} ${c.path}`).sort()).toEqual([
      "GET /jurisdictions",
      "GET /pending-changes",
      "GET /roles",
      "GET /users",
    ]);
    // Opening a row, and going back, reads nothing more: the row already has the details.
    const before = calls.length;
    await openRow("Ravi Kumar");
    await screen.findByText("Ravi Kumar", { selector: "dd" });
    expect(calls.length).toBe(before);
  },
);

test("pending tags come from one list of waiting changes, not from reads per row", async () => {
  const urls: string[] = [];
  const { calls } = setup("ADMIN", {
    "GET /pending-changes": ({ url }) => {
      urls.push(url);
      return page([change()]);
    },
  });
  const row = ((await screen.findByText("Ravi Kumar")).closest("tr")) as HTMLElement;
  expect(within(row).getByText("Change waiting for approval")).toBeTruthy();
  const other = ((await screen.findByText("Asha Devi")).closest("tr")) as HTMLElement;
  expect(within(other).queryByText("Change waiting for approval")).toBeNull();
  expect(urls).toHaveLength(1);
  expect(new URL(urls[0] as string).searchParams.get("state")).toBe("PENDING");
  expect(calls.filter((c) => c.path.startsWith("/users/"))).toEqual([]);
});

test("the table shows name, user ID, role in words, area and status; no role codes anywhere", async () => {
  setup("ADMIN");
  const row = ((await screen.findByText("Ravi Kumar")).closest("tr")) as HTMLElement;
  expect(within(row).getByText("ravi")).toBeTruthy();
  expect(within(row).getByText("Supervisor")).toBeTruthy();
  expect(within(row).getByText("Rivergate")).toBeTruthy();
  expect(within(row).getByText("Active")).toBeTruthy();
  const senior = ((await screen.findByText("Meena Rao")).closest("tr")) as HTMLElement;
  expect(within(senior).getByText("All areas")).toBeTruthy();
  const old = ((await screen.findByText("Old Hand")).closest("tr")) as HTMLElement;
  expect(within(old).getByText("Turned off")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Add user" }));
  expect(document.body.textContent).not.toMatch(
    /\b(JUNIOR|INVESTIGATOR|SUPERVISOR|SENIOR|ADMIN)\b/,
  );
  expect(screen.getByText(/no case access/)).toBeTruthy();
});

test("a senior officer reads the users but has no way to change them", async () => {
  const { calls } = setup("SENIOR");
  await openRow("Ravi Kumar");
  expect(screen.queryByRole("button", { name: "Add user" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Save user" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Turn off this user" })).toBeNull();
  expect(posts(calls)).toEqual([]);
});

// ------------------------------------------------------------------ one of district_id or coverage

async function fillNewUser(role: string) {
  fireEvent.click(await screen.findByRole("button", { name: "Add user" }));
  fireEvent.change(field("Name"), { target: { value: "Sunil Rao" } });
  fireEvent.change(field("User ID"), { target: { value: "sunil" } });
  pick("Role", role);
}

test("create, district role: sends district_id and no coverage", async () => {
  const { calls } = setup("ADMIN");
  await fillNewUser("SUPERVISOR");
  pick("Area", D2);
  save();
  expect(await screen.findByText(SENT)).toBeTruthy();
  expect(bodyOf(posts(calls)[0])).toEqual({
    kind: "USER_CREATE",
    new_value: { username: "sunil", display_name: "Sunil Rao", role: "SUPERVISOR", district_id: D2 },
  });
});

test("create, SENIOR: sends coverage and no district_id; all_states is a boolean; ids are unique", async () => {
  const { calls } = setup("ADMIN");
  await fillNewUser("SENIOR");
  check("Northvale");
  check("Hillcrest");
  save();
  await screen.findByText(SENT);
  const value = (bodyOf(posts(calls)[0]).new_value ?? {}) as Record<string, unknown>;
  expect(value).toEqual({
    username: "sunil",
    display_name: "Sunil Rao",
    role: "SENIOR",
    coverage: { all_states: false, state_ids: [S1], district_ids: [D3] },
  });
  expect("district_id" in value).toBe(false);
});

test("create, SENIOR with All areas: all_states true and empty lists", async () => {
  const { calls } = setup("ADMIN");
  await fillNewUser("SENIOR");
  check("Northvale");
  check("All areas");
  save();
  await screen.findByText(SENT);
  const value = (bodyOf(posts(calls)[0]).new_value ?? {}) as { coverage?: unknown };
  expect(value.coverage).toEqual({ all_states: true, state_ids: [], district_ids: [] });
});

test("create: a district picked first is not sent after the role changes to SENIOR", async () => {
  const { calls } = setup("ADMIN");
  await fillNewUser("SUPERVISOR");
  pick("Area", D1);
  pick("Role", "SENIOR");
  check("All areas");
  save();
  await screen.findByText(SENT);
  const value = (bodyOf(posts(calls)[0]).new_value ?? {}) as Record<string, unknown>;
  expect("district_id" in value).toBe(false);
  expect("coverage" in value).toBe(true);
});

test("create: neither is never sent. A district role without an area, and SENIOR without one, stay in the browser", async () => {
  const { calls } = setup("ADMIN");
  await fillNewUser("JUNIOR");
  save();
  expect(await screen.findByText("Please choose an area.")).toBeTruthy();
  pick("Role", "SENIOR");
  save();
  expect(await screen.findByText("Please choose at least one area.")).toBeTruthy();
  expect(posts(calls)).toEqual([]);
});

test("create: an administrator has no area field and sends neither key", async () => {
  const { calls } = setup("ADMIN");
  await fillNewUser("ADMIN");
  expect(screen.queryByLabelText("Area")).toBeNull();
  expect(screen.queryByRole("group", { name: "Area" })).toBeNull();
  save();
  await screen.findByText(SENT);
  expect(bodyOf(posts(calls)[0])).toEqual({
    kind: "USER_CREATE",
    new_value: { username: "sunil", display_name: "Sunil Rao", role: "ADMIN" },
  });
});

test("create: a blank name or user ID stays in the browser", async () => {
  const { calls } = setup("ADMIN");
  fireEvent.click(await screen.findByRole("button", { name: "Add user" }));
  pick("Role", "ADMIN");
  save();
  expect(await screen.findByText("Please fill in: Name.")).toBeTruthy();
  expect(screen.getByText("Please fill in: User ID.")).toBeTruthy();
  expect(posts(calls)).toEqual([]);
});

// ------------------------------------------------------------------ role change across SENIOR (D72)

test("to SENIOR: the form asks for coverage, refuses without it, and sends coverage and no district_id", async () => {
  const { calls } = setup("ADMIN");
  await openRow("Ravi Kumar");
  pick("Role", "SENIOR");
  expect(screen.getByRole("group", { name: "Area" })).toBeTruthy();
  expect(screen.queryByLabelText("Area")).toBeNull();
  save();
  expect(await screen.findByText("Please choose at least one area.")).toBeTruthy();
  expect(posts(calls)).toEqual([]);
  check("Rivergate");
  check("Rivergate"); // off
  check("Rivergate"); // on again: still one entry
  check("Eastmark");
  save();
  await screen.findByText(SENT);
  expect(bodyOf(posts(calls)[0])).toEqual({
    kind: "USER_ROLE",
    subject_user_id: RAVI,
    new_value: {
      role: "SENIOR",
      coverage: { all_states: false, state_ids: [S2], district_ids: [D1] },
    },
  });
});

test("from SENIOR to a district role: the form asks for a district, and sends district_id and no coverage", async () => {
  const { calls } = setup("ADMIN");
  await openRow("Meena Rao");
  pick("Role", "SUPERVISOR");
  expect(screen.queryByRole("group", { name: "Area" })).toBeNull();
  save();
  expect(await screen.findByText("Please choose an area.")).toBeTruthy();
  expect(posts(calls)).toEqual([]);
  pick("Area", D2);
  save();
  await screen.findByText(SENT);
  expect(bodyOf(posts(calls)[0])).toEqual({
    kind: "USER_ROLE",
    subject_user_id: MEENA,
    new_value: { role: "SUPERVISOR", district_id: D2 },
  });
});

test("between two district roles, or to an administrator: the role alone is sent", async () => {
  const { calls } = setup("ADMIN");
  await openRow("Asha Devi");
  pick("Role", "SUPERVISOR");
  save();
  await screen.findByText(SENT);
  expect(bodyOf(posts(calls)[0])).toEqual({
    kind: "USER_ROLE",
    subject_user_id: ASHA,
    new_value: { role: "SUPERVISOR" },
  });
});

test("an area change for a district user sends district_id alone; for a SENIOR, coverage alone", async () => {
  const first = setup("ADMIN");
  await openRow("Ravi Kumar");
  pick("Area", D2);
  save();
  await screen.findByText(SENT);
  expect(bodyOf(posts(first.calls)[0])).toEqual({
    kind: "USER_JURISDICTION",
    subject_user_id: RAVI,
    new_value: { district_id: D2 },
  });
  cleanup();

  const second = setup("ADMIN");
  await openRow("Meena Rao");
  // Her coverage is filled in from the list: All areas.
  expect((screen.getByRole("checkbox", { name: "All areas" }) as HTMLInputElement).checked).toBe(
    true,
  );
  check("All areas");
  check("Hillcrest");
  save();
  await screen.findByText(SENT);
  expect(bodyOf(posts(second.calls)[0])).toEqual({
    kind: "USER_JURISDICTION",
    subject_user_id: MEENA,
    new_value: { coverage: { all_states: false, state_ids: [], district_ids: [D3] } },
  });
});

test("nothing to save when nothing changed", async () => {
  const { calls } = setup("ADMIN");
  await openRow("Ravi Kumar");
  const button = screen.getByRole("button", { name: "Save user" }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  expect(posts(calls)).toEqual([]);
});

// ------------------------------------------------------------------ proposals, not saves (D35)

test("a save by an administrator is a proposal: Sent for approval, and the tag stays on the form and the row", async () => {
  setup("ADMIN");
  await openRow("Ravi Kumar");
  pick("Role", "INVESTIGATOR");
  save();
  expect(await screen.findByText(SENT)).toBeTruthy();
  expect(screen.getByText("Change waiting for approval")).toBeTruthy();
  expect((screen.getByRole("button", { name: "Save user" }) as HTMLButtonElement).disabled).toBe(
    true,
  );
  fireEvent.click(screen.getByRole("button", { name: "Back to the list" }));
  const row = ((await screen.findByText("Ravi Kumar")).closest("tr")) as HTMLElement;
  expect(within(row).getByText("Change waiting for approval")).toBeTruthy();
});

test("a user with a waiting change opens with the tag and the message, and cannot be changed again", async () => {
  setup("ADMIN", { "GET /pending-changes": page([change()]) });
  await openRow("Ravi Kumar");
  expect(screen.getByText(SENT)).toBeTruthy();
  expect(screen.getByText("Change waiting for approval")).toBeTruthy();
  expect(
    (screen.getByRole("button", { name: "Turn off this user" }) as HTMLButtonElement).disabled,
  ).toBe(true);
});

test("a new user waiting for approval is listed with the tag", async () => {
  setup("ADMIN", {
    "GET /pending-changes": page([
      change({
        kind: "USER_CREATE",
        subject: null,
        old_value: null,
        new_value: { username: "sunil", display_name: "Sunil Rao", role: "ADMIN" },
      }),
    ]),
  });
  expect(await screen.findByText("Add user Sunil Rao")).toBeTruthy();
  expect(screen.getAllByText("Change waiting for approval").length).toBeGreaterThan(0);
});

test("turn off: a second step, then a USER_DISABLE proposal", async () => {
  const { calls } = setup("ADMIN");
  await openRow("Ravi Kumar");
  fireEvent.click(screen.getByRole("button", { name: "Turn off this user" }));
  expect(screen.getByText("Turn off Ravi Kumar?")).toBeTruthy();
  expect(
    screen.getByText("They will not be able to sign in once a senior officer approves."),
  ).toBeTruthy();
  expect(posts(calls)).toEqual([]);
  fireEvent.click(screen.getByRole("button", { name: "No, go back" }));
  expect(posts(calls)).toEqual([]);
  fireEvent.click(screen.getByRole("button", { name: "Turn off this user" }));
  fireEvent.click(screen.getByRole("button", { name: "Yes, send for approval" }));
  expect(await screen.findByText(SENT)).toBeTruthy();
  expect(bodyOf(posts(calls)[0])).toEqual({ kind: "USER_DISABLE", subject_user_id: RAVI });
});

test("a turned-off user can be turned on again by proposal", async () => {
  const { calls } = setup("ADMIN");
  await openRow("Old Hand");
  fireEvent.click(screen.getByRole("button", { name: "Turn on this user" }));
  fireEvent.click(screen.getByRole("button", { name: "Yes, send for approval" }));
  await screen.findByText(SENT);
  expect(bodyOf(posts(calls)[0]).kind).toBe("USER_ENABLE");
});

// ------------------------------------------------------------------ failures go through FailureView

test.each([
  [401, "sessionExpired"],
  [403, "notAllowed"],
  [404, "notFound"],
  [409, "conflict"],
  [422, "invalid"],
  [429, "tooManyAttempts"],
  [503, "safetyPause"],
  [500, "serverError"],
] as const)("a %s when the list loads shows the shared message", async (status, kind) => {
  const message = t(messageKeyFor({ kind } as never), "en");
  setup("ADMIN", { "GET /users": json(status, { code: "X" }) });
  // 401 first tries a refresh; the fake has no session, so it ends as an expired session.
  expect(await screen.findByText(message)).toBeTruthy();
});

test("a network failure when the list loads shows the no-connection message", async () => {
  const failing = (() => Promise.reject(new TypeError("offline"))) as unknown as typeof fetch;
  const api = createApi({ baseUrl: "http://api.test", fetch: failing });
  renderPage(<UsersPage api={api} lang="en" role="ADMIN" />);
  expect(await screen.findByText(t("state.noConnection", "en"))).toBeTruthy();
});

test("a failed reference list (areas) also shows through FailureView, with Try again", async () => {
  setup("ADMIN", { "GET /jurisdictions": json(503) });
  expect(await screen.findByText(t("error.safetyPause", "en"))).toBeTruthy();
  expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
});

test.each([
  [404, "state.notFound"],
  [422, "state.somethingMissing"],
  [503, "error.safetyPause"],
  [409, "state.changedMeanwhile"],
  [403, "state.notAllowed"],
] as const)("a %s on Save shows the shared message and keeps the form", async (status, key) => {
  setup("ADMIN", { "POST /pending-changes": json(status, { code: "X" }) });
  await openRow("Ravi Kumar");
  pick("Role", "INVESTIGATOR");
  save();
  expect(await screen.findByText(t(key, "en"))).toBeTruthy();
  expect(screen.queryByText(SENT)).toBeNull();
  await waitFor(() =>
    expect((screen.getByRole("button", { name: "Save user" }) as HTMLButtonElement).disabled).toBe(
      false,
    ),
  );
});

test("a 422 on a new user marks the field the API names", async () => {
  setup("ADMIN", {
    "POST /pending-changes": json(422, {
      code: "VALIDATION_FAILED",
      field_errors: [{ field: "username", code: "invalid" }],
    }),
  });
  await fillNewUser("ADMIN");
  save();
  await waitFor(() => expect(field("User ID").getAttribute("aria-invalid")).toBe("true"));
});

// ------------------------------------------------------------------ Hindi

test("Hindi: the page and the form draw in Hindi", async () => {
  const fake = fakeApi({
    "GET /users": page([ravi]),
    "GET /pending-changes": page([]),
    "GET /jurisdictions": jurisdictions,
    "GET /roles": roles,
  });
  renderPage(<UsersPage api={fake.api} lang="hi" role="ADMIN" />, "hi");
  expect(await screen.findByRole("button", { name: t("users.add", "hi") })).toBeTruthy();
  expect(screen.getByText(t("users.col.name", "hi"))).toBeTruthy();
});
