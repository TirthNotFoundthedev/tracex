import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { fakeApi, json, renderPage, type Answer, type Routes } from "../testing";
import type { Role } from "../nav";
import { ApprovalsPage } from "./ApprovalsPage";

afterEach(cleanup);

const ME = "10000000-0000-4000-8000-000000000001";
const OTHER = "20000000-0000-4000-8000-000000000002";
const REQ = "30000000-0000-4000-8000-000000000003";
const REQ2 = "30000000-0000-4000-8000-000000000004";
const CHG = "40000000-0000-4000-8000-000000000005";
const CHG2 = "40000000-0000-4000-8000-000000000006";
const HASH = "a".repeat(64);

function request(over: Record<string, unknown> = {}) {
  return {
    view: "TO_DECIDE",
    request_id: REQ,
    status: "PENDING",
    requested_at: "2026-03-12T14:05:00Z",
    expires_at: "2026-03-19T14:05:00Z",
    reason: "Phone number 9000014471 shows up in both inquiries",
    requester: { user_id: OTHER, display_name: "Meena Rao", role: "JUNIOR" },
    far_case_id: "C-207",
    stub: {
      redacted: true,
      stub_id: "50000000-0000-4000-8000-000000000005",
      near_entity_id: "E-9",
      connection_exists: true,
      access_request: { status: "PENDING", requested_at: "2026-03-12T14:05:00Z" },
      message_key: "access.stub.connection_exists",
    },
    ...over,
  };
}

function change(over: Record<string, unknown> = {}) {
  return {
    change_id: CHG,
    kind: "USER_ROLE",
    state: "PENDING",
    subject: { user_id: OTHER, display_name: "Ravi Kumar", role: "SUPERVISOR" },
    old_value: { role: "SUPERVISOR" },
    new_value: { role: "SENIOR" },
    proposer: {
      user_id: "60000000-0000-4000-8000-000000000006",
      display_name: "Hari",
      role: "ADMIN",
    },
    change_hash: HASH,
    proposed_at: "2026-03-12T14:05:00Z",
    ...over,
  };
}

const page = (items: unknown[], total = items.length) =>
  json(200, { items, next_cursor: null, total });
const none = page([]);

function setup(role: Role, over: Routes = {}) {
  const fake = fakeApi({
    "GET /access-requests": page([request()]),
    "GET /pending-changes": page([change()]),
    "GET /jurisdictions": json(200, { items: [] }),
    ...over,
  });
  renderPage(<ApprovalsPage api={fake.api} lang="en" role={role} userId={ME} />);
  return fake;
}

async function openRow(text: string) {
  const cell = (await screen.findAllByText(text))[0] as HTMLElement;
  const row = cell.closest("tr") as HTMLElement;
  fireEvent.click(within(row).getByRole("button", { name: "Open" }));
}

const body = (calls: { method: string; path: string; init: RequestInit }[], path: string) =>
  JSON.parse(String(calls.find((c) => c.method === "POST" && c.path === path)?.init.body));

test("a supervisor sees only Access requests and never calls the pending changes", async () => {
  const { calls } = setup("SUPERVISOR");
  expect(await screen.findByText("Meena Rao")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Access requests (1)" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: /Changes/ })).toBeNull();
  expect(calls.some((c) => c.path === "/pending-changes")).toBe(false);
});

test("an administrator sees only Changes and never calls access requests (404 for ADMIN)", async () => {
  const { calls } = setup("ADMIN");
  expect(await screen.findByText("Ravi Kumar: Supervisor to Senior officer")).toBeTruthy();
  expect(screen.queryByRole("button", { name: /Access requests/ })).toBeNull();
  expect(calls.some((c) => c.path === "/access-requests")).toBe(false);
});

test("a senior officer sees both tabs with the API totals", async () => {
  setup("SENIOR", { "GET /access-requests": page([request()], 7) });
  expect(await screen.findByRole("button", { name: "Access requests (7)" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Changes" })).toBeTruthy();
});

test("the access list asks for pending requests to decide, 50 at a time", async () => {
  const urls: URL[] = [];
  setup("SUPERVISOR", {
    "GET /access-requests": ({ url }) => {
      urls.push(new URL(url));
      return page([request()]);
    },
  });
  await screen.findByText("Meena Rao");
  const list = urls.find((u) => u.searchParams.get("limit") === "50");
  expect(list?.searchParams.get("scope")).toBe("to_decide");
  expect(list?.searchParams.get("status")).toBe("PENDING");
});

test("opening a request shows the whole reason and reads no detail from the API", async () => {
  const { calls } = setup("SUPERVISOR");
  await openRow("Meena Rao");
  expect(
    await screen.findByText("Phone number 9000014471 shows up in both inquiries"),
  ).toBeTruthy();
  expect(calls.some((c) => c.path === `/access-requests/${REQ}`)).toBe(false);
});

test("approving needs a second step and sends the chosen days", async () => {
  const { calls } = setup("SUPERVISOR", {
    [`POST /access-requests/${REQ}/approve`]: json(
      200,
      request({
        status: "APPROVED",
        grant: {
          view: "AUTHORITY",
          grant_id: "70000000-0000-4000-8000-000000000007",
          request_id: REQ,
          status: "ACTIVE",
          starts_at: "2026-03-12T15:00:00Z",
          expires_at: "2026-04-11T15:00:00Z",
          holder: { user_id: OTHER, display_name: "Meena Rao", role: "JUNIOR" },
          far_case_id: "C-207",
        },
      }),
    ),
  });
  await openRow("Meena Rao");
  fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
  expect(calls.some((c) => c.method === "POST")).toBe(false);
  expect(screen.getByText("Give Meena Rao access to case C-207 for 30 days?")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Yes, approve" }));
  expect(await screen.findByText("You gave access. It ends on 11 Apr 2026.")).toBeTruthy();
  expect(body(calls, `/access-requests/${REQ}/approve`)).toEqual({ duration_days: 30 });
});

test("choosing 90 days is what is sent and what the question says", async () => {
  const { calls } = setup("SUPERVISOR", {
    [`POST /access-requests/${REQ}/approve`]: json(200, request({ status: "APPROVED" })),
  });
  await openRow("Meena Rao");
  fireEvent.change(await screen.findByLabelText("Access ends"), { target: { value: "90" } });
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  expect(screen.getByText("Give Meena Rao access to case C-207 for 90 days?")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Yes, approve" }));
  await waitFor(() =>
    expect(body(calls, `/access-requests/${REQ}/approve`)).toEqual({ duration_days: 90 }),
  );
});

test("No, go back leaves the request untouched", async () => {
  const { calls } = setup("SUPERVISOR");
  await openRow("Meena Rao");
  fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
  fireEvent.click(screen.getByRole("button", { name: "No, go back" }));
  expect(screen.getByRole("button", { name: "Approve" })).toBeTruthy();
  expect(calls.some((c) => c.method === "POST")).toBe(false);
});

test("refusing sends the trimmed note, and the Refuse button is never the primary one", async () => {
  const { calls } = setup("SUPERVISOR", {
    [`POST /access-requests/${REQ}/deny`]: json(200, request({ status: "DENIED" })),
  });
  await openRow("Meena Rao");
  const refuse = await screen.findByRole("button", { name: "Refuse" });
  expect(refuse.getAttribute("data-variant")).not.toBe("primary");
  expect(screen.getByRole("button", { name: "Approve" }).getAttribute("data-variant")).toBe(
    "primary",
  );
  fireEvent.change(screen.getByLabelText("Reason for refusing (optional)"), {
    target: { value: "  Ask your supervisor first  " },
  });
  fireEvent.click(refuse);
  expect(await screen.findByText("You refused this request. Nothing was changed.")).toBeTruthy();
  expect(body(calls, `/access-requests/${REQ}/deny`)).toEqual({
    note: "Ask your supervisor first",
  });
});

test("refusing without a note sends an empty body", async () => {
  const { calls } = setup("SUPERVISOR", {
    [`POST /access-requests/${REQ}/deny`]: json(200, request({ status: "DENIED" })),
  });
  await openRow("Meena Rao");
  fireEvent.click(await screen.findByRole("button", { name: "Refuse" }));
  await screen.findByText("You refused this request. Nothing was changed.");
  expect(body(calls, `/access-requests/${REQ}/deny`)).toEqual({});
});

test("the note field stops at 200 characters", async () => {
  setup("SUPERVISOR");
  await openRow("Meena Rao");
  const note = await screen.findByLabelText("Reason for refusing (optional)");
  expect(note.getAttribute("maxlength")).toBe("200");
  expect(
    screen.getByText("Do not write names, numbers or places. The requester will read this."),
  ).toBeTruthy();
});

test("a request made by the viewer has no decision buttons", async () => {
  setup("SUPERVISOR", {
    "GET /access-requests": page([
      request({ requester: { user_id: ME, display_name: "Me Myself", role: "SUPERVISOR" } }),
    ]),
  });
  await openRow("Me Myself");
  expect(await screen.findByText(/You asked for this access/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Refuse" })).toBeNull();
});

test.each([
  [403, undefined, "You do not have access to do this."],
  [404, undefined, "We could not find this. Go back and try again."],
  [409, { code: "CONFLICT" }, "Someone changed this while you were looking. Please open it again."],
  [429, undefined, "The system is busy. Please wait a moment, then try again."],
  [503, undefined, "The system is paused for a safety check. Try again later."],
])("a %s answer to Approve is shown and not retried", async (status, errBody, text) => {
  const { calls } = setup("SUPERVISOR", {
    [`POST /access-requests/${REQ}/approve`]: json(status, errBody),
  });
  await openRow("Meena Rao");
  fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
  fireEvent.click(screen.getByRole("button", { name: "Yes, approve" }));
  expect(await screen.findByText(text)).toBeTruthy();
  expect(calls.filter((c) => c.method === "POST")).toHaveLength(1);
  expect(screen.queryByText(/You gave access/)).toBeNull();
});

test.each([
  [403, "You do not have access to do this."],
  [404, "We could not find this. Go back and try again."],
  [429, "The system is busy. Please wait a moment, then try again."],
  [500, "Something went wrong on our side. Nothing was changed. Try again."],
])("a %s answer when loading the list is an error, never an empty list", async (status, text) => {
  setup("SUPERVISOR", { "GET /access-requests": json(status) });
  expect(await screen.findByText(text)).toBeTruthy();
  expect(screen.queryByText("No access requests are waiting.")).toBeNull();
});

test("an empty list says so", async () => {
  setup("SUPERVISOR", { "GET /access-requests": none });
  expect(await screen.findByText("No access requests are waiting.")).toBeTruthy();
});

test("Show more adds rows, keeps them when the next page fails, and uses the API total", async () => {
  let call = 0;
  const answer: Answer = () => {
    call += 1;
    if (call === 1) return json(200, { items: [request()], next_cursor: "c".repeat(20), total: 3 });
    if (call === 2) return json(500);
    return json(200, {
      items: [
        request({
          request_id: REQ2,
          requester: { user_id: OTHER, display_name: "Charu Das", role: "JUNIOR" },
        }),
      ],
      next_cursor: null,
      total: 3,
    });
  };
  setup("SUPERVISOR", { "GET /access-requests": answer });
  expect(await screen.findByText("Showing 1 of 3")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Show more" }));
  expect(
    await screen.findByText("Something went wrong on our side. Nothing was changed. Try again."),
  ).toBeTruthy();
  expect(screen.getByText("Meena Rao")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText("Charu Das")).toBeTruthy();
  expect(screen.getByText("Meena Rao")).toBeTruthy();
});

// Changes

test("a senior officer decides a change from another administrator with a second step and the hash", async () => {
  const { calls } = setup("SENIOR", {
    [`POST /pending-changes/${CHG}/approve`]: json(200, change({ state: "APPROVED" })),
  });
  fireEvent.click(await screen.findByRole("button", { name: /Changes/ }));
  await openRow("Ravi Kumar: Supervisor to Senior officer");
  expect(await screen.findByText("Now")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Approve this change" }));
  expect(screen.getByText("Apply this change? It takes effect now.")).toBeTruthy();
  expect(calls.some((c) => c.method === "POST")).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Yes, approve" }));
  expect(await screen.findByText("You approved this change. It is now in effect.")).toBeTruthy();
  expect(body(calls, `/pending-changes/${CHG}/approve`)).toEqual({ change_hash: HASH });
  expect(calls.some((c) => c.path === `/pending-changes/${CHG}`)).toBe(false);
});

test("refusing a change sends no body and Refuse is not primary", async () => {
  const { calls } = setup("SENIOR", {
    [`POST /pending-changes/${CHG}/deny`]: json(200, change({ state: "DENIED" })),
  });
  fireEvent.click(await screen.findByRole("button", { name: /Changes/ }));
  await openRow("Ravi Kumar: Supervisor to Senior officer");
  const refuse = await screen.findByRole("button", { name: "Refuse this change" });
  expect(refuse.getAttribute("data-variant")).not.toBe("primary");
  fireEvent.click(refuse);
  expect(await screen.findByText("You refused this change. Nothing was changed.")).toBeTruthy();
  const post = calls.find((c) => c.method === "POST");
  expect(post?.path).toBe(`/pending-changes/${CHG}/deny`);
  expect(post?.init.body).toBeUndefined();
});

test("the proposer sees no buttons and the reason", async () => {
  setup("SENIOR", {
    "GET /pending-changes": page([
      change({ proposer: { user_id: ME, display_name: "Me", role: "SENIOR" } }),
    ]),
  });
  fireEvent.click(await screen.findByRole("button", { name: /Changes/ }));
  await openRow("Ravi Kumar: Supervisor to Senior officer");
  expect(
    await screen.findByText("You proposed this change. Another senior officer must decide it."),
  ).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Approve this change" })).toBeNull();
});

test("the subject sees no buttons and the reason", async () => {
  setup("SENIOR", {
    "GET /pending-changes": page([
      change({ subject: { user_id: ME, display_name: "Me", role: "SENIOR" } }),
    ]),
  });
  fireEvent.click(await screen.findByRole("button", { name: /Changes/ }));
  await openRow("Me: Supervisor to Senior officer");
  expect(
    await screen.findByText("This change is about you. Another senior officer must decide it."),
  ).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Refuse this change" })).toBeNull();
});

test("an administrator sees the status of their changes and no Approve button", async () => {
  setup("ADMIN", {
    "GET /pending-changes": page([change(), change({ change_id: CHG2, state: "DENIED" })]),
  });
  await screen.findAllByText("Waiting for a senior officer");
  expect(screen.getByText("Refused")).toBeTruthy();
  await openRow("Ravi Kumar: Supervisor to Senior officer");
  await screen.findByText("Now");
  expect(screen.queryByRole("button", { name: "Approve this change" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Refuse this change" })).toBeNull();
});

test("a senior officer asks only for the pending changes; an administrator asks for all of theirs", async () => {
  const senior = setup("SENIOR");
  await screen.findByRole("button", { name: /Changes/ });
  const asked = senior.calls.filter((c) => c.path === "/pending-changes");
  expect(asked.length).toBeGreaterThan(0);
  cleanup();
  const admin = setup("ADMIN");
  await screen.findByText("Ravi Kumar: Supervisor to Senior officer");
  expect(admin.calls.filter((c) => c.path === "/pending-changes").length).toBeGreaterThan(0);
});

test.each([
  ["CHANGE_HASH_STALE", "This change was edited after you opened it. Please open it again."],
  ["OLD_VALUE_CHANGED", "The current value changed since this was proposed. Nothing was changed."],
  ["LAST_APPROVER", "This would leave no senior officer to approve for that area."],
  ["CONFLICT", "Someone changed this while you were looking. Please open it again."],
])("a 409 %s is shown in words and not retried", async (code, text) => {
  const { calls } = setup("SENIOR", {
    [`POST /pending-changes/${CHG}/approve`]: json(409, { code }),
  });
  fireEvent.click(await screen.findByRole("button", { name: /Changes/ }));
  await openRow("Ravi Kumar: Supervisor to Senior officer");
  fireEvent.click(await screen.findByRole("button", { name: "Approve this change" }));
  fireEvent.click(screen.getByRole("button", { name: "Yes, approve" }));
  expect(await screen.findByText(text)).toBeTruthy();
  expect(calls.filter((c) => c.method === "POST")).toHaveLength(1);
});

test("a 404 on a decision shows the plain change-not-found text", async () => {
  setup("SENIOR", { [`POST /pending-changes/${CHG}/deny`]: json(404) });
  fireEvent.click(await screen.findByRole("button", { name: /Changes/ }));
  await openRow("Ravi Kumar: Supervisor to Senior officer");
  fireEvent.click(await screen.findByRole("button", { name: "Refuse this change" }));
  expect(await screen.findByText("We could not find this change.")).toBeTruthy();
});

test.each([
  [403, "You do not have access to do this."],
  [404, "We could not find this. Go back and try again."],
  [429, "The system is busy. Please wait a moment, then try again."],
])("a %s answer when loading changes is an error, never none", async (status, text) => {
  setup("ADMIN", { "GET /pending-changes": json(status) });
  expect(await screen.findByText(text)).toBeTruthy();
  expect(screen.queryByText("No changes are waiting.")).toBeNull();
});

test("changes read in plain words for every kind", async () => {
  setup("ADMIN", {
    "GET /pending-changes": page([
      change({
        change_id: "a1",
        kind: "THRESHOLDS",
        subject: null,
        old_value: { high_min: 80, medium_min: 45 },
        new_value: { high_min: 85, medium_min: 50 },
      }),
      change({
        change_id: "a2",
        kind: "USER_DISABLE",
        old_value: { active: true },
        new_value: { active: false },
      }),
      change({
        change_id: "a3",
        kind: "USER_CREATE",
        subject: null,
        old_value: null,
        new_value: { username: "new.one", display_name: "Asha Nair", role: "JUNIOR" },
      }),
      change({
        change_id: "a4",
        kind: "ASSIGNMENT_ADD",
        old_value: null,
        new_value: { case_number: "31/207" },
      }),
    ]),
  });
  expect(
    await screen.findByText("Match settings: strong match starts at 85, possible at 50"),
  ).toBeTruthy();
  expect(screen.getByText("Turn off Ravi Kumar")).toBeTruthy();
  expect(screen.getByText("Add user Asha Nair")).toBeTruthy();
  expect(screen.getByText("Give Ravi Kumar case 31/207")).toBeTruthy();
});

test("Hindi shows the same page in Hindi", async () => {
  const fake = fakeApi({
    "GET /access-requests": page([request()]),
    "GET /pending-changes": page([change()]),
    "GET /jurisdictions": json(200, { items: [] }),
  });
  renderPage(<ApprovalsPage api={fake.api} lang="hi" role="SENIOR" userId={ME} />, "hi");
  expect(await screen.findByRole("button", { name: "पहुँच के अनुरोध (1)" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "बदलाव" })).toBeTruthy();
});

test("the table is inside a labelled region and a decision returns to a refreshed list", async () => {
  let n = 0;
  setup("SUPERVISOR", {
    "GET /access-requests": () => (++n === 1 ? page([request()]) : none),
    [`POST /access-requests/${REQ}/deny`]: json(200, request({ status: "DENIED" })),
  });
  await openRow("Meena Rao");
  fireEvent.click(await screen.findByRole("button", { name: "Refuse" }));
  await screen.findByText("You refused this request. Nothing was changed.");
  fireEvent.click(screen.getByRole("button", { name: "Back to the list" }));
  expect(await screen.findByText("No access requests are waiting.")).toBeTruthy();
  expect(within(document.body).queryByText("Meena Rao")).toBeNull();
});

// Fix round: no count-only reads, stale guard, area names, sign-in name, recorded old value

const D1 = "80000000-0000-4000-8000-000000000001";
const S1 = "90000000-0000-4000-8000-000000000001";
const places = json(200, {
  items: [
    { state_id: S1, name: "Karnataka", districts: [{ district_id: D1, name: "Bengaluru Urban" }] },
  ],
});
const allStates = { all_states: true, state_ids: [], district_ids: [] };
const oneDistrict = { all_states: false, state_ids: [], district_ids: [D1] };

function areaChange(newValue: Record<string, unknown>) {
  return change({
    kind: "USER_JURISDICTION",
    old_value: { district_id: D1 },
    new_value: newValue,
  });
}

async function openChange(items: unknown[], text: string, routes: Routes = {}) {
  setup("SENIOR", { "GET /pending-changes": page(items), "GET /jurisdictions": places, ...routes });
  fireEvent.click(await screen.findByRole("button", { name: "Changes" }));
  await openRow(text);
}

test("opening the page makes exactly one list request and no count-only request", async () => {
  const senior = setup("SENIOR");
  await screen.findByText("Meena Rao");
  expect(senior.calls.filter((c) => c.path === "/access-requests")).toHaveLength(1);
  expect(senior.calls.filter((c) => c.path === "/pending-changes")).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: "Changes" }));
  await screen.findByText("Ravi Kumar: Supervisor to Senior officer");
  expect(senior.calls.filter((c) => c.path === "/pending-changes")).toHaveLength(1);
  expect(screen.getByRole("button", { name: "Changes (1)" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Access requests" })).toBeTruthy();
});

test("Back after a pending Show more: the old page never adds rows", async () => {
  let release: (r: Response) => void = () => {};
  const old = new Promise<Response>((resolve) => (release = resolve));
  let fresh = 0;
  const answer: Answer = ({ url }) => {
    if (new URL(url).searchParams.get("cursor")) return old as unknown as Response;
    fresh += 1;
    return json(200, { items: [request()], next_cursor: "c".repeat(20), total: 3 });
  };
  setup("SUPERVISOR", { "GET /access-requests": answer });
  expect(await screen.findByText("Showing 1 of 3")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Show more" }));
  await openRow("Meena Rao");
  fireEvent.click(await screen.findByRole("button", { name: "Back to the list" }));
  await waitFor(() => expect(fresh).toBe(2));
  expect(await screen.findByText("Showing 1 of 3")).toBeTruthy();
  await act(async () => {
    release(
      json(200, {
        items: [
          request({
            request_id: REQ2,
            requester: { user_id: OTHER, display_name: "Charu Das", role: "JUNIOR" },
          }),
        ],
        next_cursor: null,
        total: 9,
      }),
    );
    await old;
  });
  expect(screen.queryByText("Charu Das")).toBeNull();
  expect(screen.getByText("Showing 1 of 3")).toBeTruthy();
});

test("a one-district coverage lists the district name, not All areas", async () => {
  await openChange(
    [areaChange({ coverage: oneDistrict })],
    "Ravi Kumar: area Bengaluru Urban to Bengaluru Urban",
  );
  expect((await screen.findAllByText("Bengaluru Urban")).length).toBeGreaterThan(0);
  expect(screen.queryByText("All areas")).toBeNull();
  expect(screen.getByRole("button", { name: "Approve this change" })).toBeTruthy();
});

test("an all-state coverage says All areas", async () => {
  await openChange(
    [areaChange({ coverage: allStates })],
    "Ravi Kumar: area Bengaluru Urban to All areas",
  );
  expect((await screen.findAllByText("All areas")).length).toBeGreaterThan(0);
  expect(screen.getByRole("button", { name: "Approve this change" })).toBeTruthy();
});

test("a state in the coverage is listed by name", async () => {
  await openChange(
    [areaChange({ coverage: { all_states: false, state_ids: [S1], district_ids: [] } })],
    "Ravi Kumar: area Bengaluru Urban to Karnataka",
  );
  expect((await screen.findAllByText("Karnataka")).length).toBeGreaterThan(0);
});

test("when the area names do not load, Approve is hidden and the reason is shown, never a dash", async () => {
  await openChange(
    [areaChange({ district_id: D1 })],
    "Ravi Kumar: area unknown area to unknown area",
    { "GET /jurisdictions": json(500) },
  );
  expect(await screen.findByText(/Approve is hidden/)).toBeTruthy();
  expect(
    screen.getAllByText("Something went wrong on our side. Nothing was changed. Try again.").length,
  ).toBeGreaterThan(0);
  expect(screen.queryByRole("button", { name: "Approve this change" })).toBeNull();
  expect(screen.queryByText("—")).toBeNull();
});

test("an area id that is not in the list hides Approve with a plain line", async () => {
  await openChange(
    [areaChange({ district_id: "a0000000-0000-4000-8000-000000000009" })],
    "Ravi Kumar: area Bengaluru Urban to unknown area",
  );
  expect(await screen.findByText(/Approve is hidden/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Approve this change" })).toBeNull();
});

test("a new user shows the sign-in name, role and area", async () => {
  await openChange(
    [
      change({
        kind: "USER_CREATE",
        subject: null,
        old_value: null,
        new_value: {
          username: "meena.senior",
          display_name: "Meena Rao",
          role: "SENIOR",
          coverage: oneDistrict,
        },
      }),
    ],
    "Add user Meena Rao",
  );
  expect(await screen.findByText("Sign-in name")).toBeTruthy();
  expect(screen.getByText("meena.senior")).toBeTruthy();
  expect(screen.getByText("Bengaluru Urban")).toBeTruthy();
});

test("for turning a user on or off, Now shows the value the server recorded", async () => {
  await openChange(
    [change({ kind: "USER_DISABLE", old_value: { active: false }, new_value: { active: false } })],
    "Turn off Ravi Kumar",
  );
  await screen.findByText("Now");
  expect(screen.getAllByText("Turned off")).toHaveLength(2);
  expect(screen.queryByText("Active")).toBeNull();
});
