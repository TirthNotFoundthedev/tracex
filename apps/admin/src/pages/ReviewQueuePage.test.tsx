import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test } from "vitest";

import type { AdminApi } from "../api";
import { t } from "../i18n";
import type { Role } from "../nav";
import { usePath } from "../router";
import { DISTRICT, fakeApi, json, renderPage, type Routes } from "../testing";
import { ReviewQueuePage } from "./ReviewQueuePage";

afterEach(cleanup);
beforeEach(() => window.history.replaceState(null, "", "/review"));

const LINK = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const LINK2 = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const MEENA = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const CHARU = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";

function end(n: 1 | 2, caseNumber: string) {
  return {
    entity: {
      entity_id: `e${n}`,
      case_id: `c${n}`,
      type: "PHONE",
      display_value: "9000014471",
      masked: false,
      link_count: 1,
      has_hidden_connection: false,
      needs_review: false,
      via_grant: false,
    },
    case: { case_id: `c${n}`, case_number: caseNumber, district_id: DISTRICT },
  };
}

function item(over: Record<string, unknown> = {}) {
  return {
    link_id: LINK,
    entity_type: "PHONE",
    state: "SUGGESTED",
    band: "MEDIUM",
    score: 62.5,
    ends: [end(1, "24/118"), end(2, "31/207")],
    main_reason: {
      template_key: "match.evidence.id_exact",
      params: { id_label: "phone", value: "9000014471" },
    },
    updated_at: "2026-03-12T09:00:00Z",
    waiting_since: "2026-03-01T09:00:00Z",
    allowed_actions: ["CONFIRM", "REJECT"],
    ...over,
  };
}

const source = {
  case_id: "c1",
  document_id: "d1",
  line: 14,
  page: 2,
  document_type: "call record",
};

function explanation(over: Record<string, unknown> = {}) {
  return {
    link_id: LINK,
    entity_type: "PHONE",
    state: "SUGGESTED",
    score: 62.5,
    band: "MEDIUM",
    thresholds: { high_min: 80, medium_min: 50, thresholds_version: 1 },
    ruleset_version: "engine-matching/1.0",
    gates: { passed: false, failed: [{ gate: "G1", template_key: "match.gate.below_high" }] },
    records: [
      {
        entity_id: "e1",
        case_id: "c1",
        raw_text: "90000 14471",
        normalized: "9000014471",
        extraction_confidence: 0.9,
        source,
      },
      {
        entity_id: "e2",
        case_id: "c2",
        raw_text: "9000014471",
        normalized: "9000014471",
        extraction_confidence: 0.9,
        source: { ...source, case_id: "c2", case_number: "31/207", line: 3, page: 5 },
      },
    ],
    support: [
      {
        tier: 1,
        cap: 60,
        raw: 60,
        cap_adjustment: { value: 0 },
        subtotal: 60,
        items: [
          {
            template_key: "match.evidence.id_exact",
            params: { id_label: "phone", value: "9000014471" },
            sources: [source],
          },
        ],
      },
    ],
    against: [],
    clamp_adjustment: { value: 0 },
    history: [],
    ...over,
  };
}

function detail(over: Record<string, unknown> = {}) {
  return {
    ...item(),
    thresholds_version: 1,
    ruleset_version: "engine-matching/1.0",
    created_at: "2026-03-01T09:00:00Z",
    history: [],
    allowed_actions: ["CONFIRM", "REJECT"],
    decision_block: null,
    via_grant: false,
    ...over,
  };
}

const places = json(200, {
  items: [
    {
      state_id: "s",
      name: "Rivergate State",
      districts: [{ district_id: DISTRICT, name: "Rivergate" }],
    },
  ],
});

const rejectedHistory = [
  {
    from: null,
    to: "SUGGESTED",
    at: "2026-03-01T09:00:00Z",
    actor_kind: "ENGINE",
    reason_code: "NEW",
  },
  {
    from: "SUGGESTED",
    to: "REJECTED",
    at: "2026-03-12T10:00:00Z",
    actor_kind: "USER",
    actor_user_id: MEENA,
    reason_code: "REJECTED",
    reason_text: "Different people. Ages differ by 12 years.",
  },
];

function user(id: string, name: string, role: Role) {
  return json(200, {
    user_id: id,
    user_name: name.toLowerCase(),
    display_name: name,
    role,
    district_id: DISTRICT,
    active: true,
    created_at: "2026-01-01T00:00:00Z",
  });
}

/** Queue answers by `state`; each total is the number of items listed for it. */
function queue(by: { SUGGESTED?: unknown[]; REJECTED?: unknown[]; UNDONE?: unknown[] }): Routes {
  return {
    "GET /review-queue": ({ url }) => {
      const state = (new URL(url).searchParams.get("state") ?? "SUGGESTED") as keyof typeof by;
      const items = by[state] ?? [];
      return json(200, { items, next_cursor: null, total: items.length });
    },
    "GET /jurisdictions": places,
  };
}

function Harness({ api, lang = "en" }: { api: AdminApi; lang?: "en" | "hi" }) {
  const route = usePath();
  return (
    <ReviewQueuePage
      api={api}
      lang={lang}
      path={route.path}
      search={route.search}
      navigate={route.navigate}
    />
  );
}

function open(routes: Routes, lang: "en" | "hi" = "en", start = "/review") {
  window.history.replaceState(null, "", start);
  const made = fakeApi(routes);
  renderPage(<Harness api={made.api} lang={lang} />, lang);
  return made;
}

const button = (name: string | RegExp) => screen.getByRole("button", { name });

const rejectedRow = (over: Record<string, unknown> = {}) =>
  item({
    state: "REJECTED",
    updated_at: "2026-03-12T10:00:00Z",
    allowed_actions: ["REOPEN"],
    ...over,
  });

const sentBody = (calls: { method: string; path: string; init: RequestInit }[], path: string) =>
  JSON.parse(String(calls.find((c) => c.method === "POST" && c.path === path)?.init.body));

test("lists the waiting links with the three counts and the columns of the spec", async () => {
  const { calls } = open({
    ...queue({ SUGGESTED: [item()], REJECTED: [rejectedRow({ link_id: LINK2 })], UNDONE: [] }),
  });
  expect((await screen.findAllByText("24/118")).length).toBeGreaterThan(0);
  expect(button("Waiting (1)")).toBeTruthy();
  expect(button("Rejected (1)")).toBeTruthy();
  expect(button("Undone (0)")).toBeTruthy();
  for (const header of ["Strength", "Item", "Case A", "Case B", "Main reason", "Waiting since"]) {
    expect(screen.getByRole("columnheader", { name: new RegExp(header) })).toBeTruthy();
  }
  expect(screen.getByText("31/207")).toBeTruthy();
  expect(screen.getByText("The same phone number 90000 14471 appears in both cases.")).toBeTruthy();
  expect(screen.getByText("Score: 62.5")).toBeTruthy();
  expect(screen.getByText("1 Mar 2026")).toBeTruthy();
  expect(screen.getByText("Waiting more than 7 days")).toBeTruthy();
  const list = calls.find((c) => c.path === "/review-queue");
  expect(list).toBeTruthy();
  expect(screen.getByRole("button", { name: "Waiting (1)" }).getAttribute("aria-pressed")).toBe(
    "true",
  );
});

test("the status choice is kept in the page address so Back returns to it", async () => {
  open({ ...queue({ SUGGESTED: [item()], REJECTED: [rejectedRow()] }) });
  await screen.findAllByText("24/118");
  fireEvent.click(button("Rejected (1)"));
  await waitFor(() => expect(window.location.search).toContain("show=rejected"));
  expect(
    await screen.findByText("These links were rejected. A supervisor can reopen them."),
  ).toBeTruthy();
  window.history.back();
  expect(await screen.findByText("Waiting more than 7 days")).toBeTruthy();
});

test("the Rejected table shows who, when and why, with no strength badge", async () => {
  open(
    {
      ...queue({ SUGGESTED: [], REJECTED: [rejectedRow()] }),
      [`GET /links/${LINK}`]: json(200, detail({ state: "REJECTED", history: rejectedHistory })),
      [`GET /users/${MEENA}`]: user(MEENA, "Meena Rao", "INVESTIGATOR"),
    },
    "en",
    "/review?show=rejected",
  );
  expect(await screen.findByText("Meena Rao (Investigating officer)")).toBeTruthy();
  expect(screen.getByText("12 Mar 2026")).toBeTruthy();
  expect(screen.getByText("Different people. Ages differ by 12 years.")).toBeTruthy();
  for (const header of ["Rejected by", "Rejected on", "Reason"]) {
    expect(screen.getByRole("columnheader", { name: new RegExp(header) })).toBeTruthy();
  }
  expect(screen.queryByText(/Score:/)).toBeNull();
  expect(screen.queryByText("Waiting more than 7 days")).toBeNull();
});

test("when a supervisor cannot read the person's details, the row still shows the date", async () => {
  open(
    {
      ...queue({ REJECTED: [rejectedRow()] }),
      [`GET /links/${LINK}`]: json(200, detail({ state: "REJECTED", history: rejectedHistory })),
      [`GET /users/${MEENA}`]: json(403),
    },
    "en",
    "/review?show=rejected",
  );
  expect(await screen.findByText("12 Mar 2026")).toBeTruthy();
  expect(screen.getByText("Different people. Ages differ by 12 years.")).toBeTruthy();
});

test("the Undone filter lists undone links with its own columns", async () => {
  open(
    {
      ...queue({ UNDONE: [item({ state: "UNDONE", allowed_actions: ["REOPEN"] })] }),
      [`GET /links/${LINK}`]: json(
        200,
        detail({
          state: "UNDONE",
          history: [
            {
              from: "AUTO",
              to: "UNDONE",
              at: "2026-03-12T10:00:00Z",
              actor_kind: "USER",
              actor_user_id: CHARU,
              reason_code: "UNDONE",
              reason_text: "Number was reused.",
            },
          ],
        }),
      ),
      [`GET /users/${CHARU}`]: user(CHARU, "Charu Singh", "SUPERVISOR"),
    },
    "en",
    "/review?show=undone",
  );
  expect(
    await screen.findByText("These links were undone. A supervisor can reopen them."),
  ).toBeTruthy();
  expect(await screen.findByText("Charu Singh (Supervisor)")).toBeTruthy();
  expect(screen.getByRole("columnheader", { name: /Undone by/ })).toBeTruthy();
  expect(screen.getByRole("columnheader", { name: /Undone on/ })).toBeTruthy();
  expect(screen.getByText("Number was reused.")).toBeTruthy();
});

test("empty states say what will appear, and filters that hide everything offer Clear filters", async () => {
  open({ ...queue({}) });
  expect(
    await screen.findByText("No links are waiting. New possible matches will appear here."),
  ).toBeTruthy();
  cleanup();
  open({ ...queue({}) }, "en", "/review?show=rejected");
  expect(
    await screen.findByText("No rejected links. Links that officers reject will appear here."),
  ).toBeTruthy();
  cleanup();
  open({ ...queue({}) }, "en", "/review?show=undone");
  expect(
    await screen.findByText("No undone links. Links that supervisors undo will appear here."),
  ).toBeTruthy();
  cleanup();
  open({ ...queue({}) }, "en", "/review?old=1");
  expect(
    await screen.findByText("Nothing found. Check the filters or try fewer words."),
  ).toBeTruthy();
  fireEvent.click(button("Clear filters"));
  await waitFor(() => expect(window.location.search).toBe(""));
});

test("the Type, Area and waiting-time filters narrow the request and stay in the address", async () => {
  const { fetchImpl } = open({ ...queue({ SUGGESTED: [item()] }) });
  await screen.findAllByText("24/118");
  await screen.findByRole("option", { name: "Rivergate" });
  fireEvent.change(screen.getByLabelText("Type"), { target: { value: "PHONE" } });
  fireEvent.change(screen.getByLabelText("Area"), { target: { value: DISTRICT } });
  fireEvent.click(screen.getByLabelText("Waiting more than 7 days"));
  await waitFor(() => {
    const urls = (fetchImpl as unknown as { mock: { calls: [string][] } }).mock.calls
      .map(([url]) => new URL(String(url)))
      .filter((url) => url.pathname === "/review-queue" && url.searchParams.get("limit") === "50");
    const last = urls.at(-1);
    expect(last?.searchParams.get("entity_type")).toBe("PHONE");
    expect(last?.searchParams.get("district_id")).toBe(DISTRICT);
    expect(last?.searchParams.get("waiting_days_min")).toBe("7");
  });
  expect(window.location.search).toContain("type=PHONE");
  expect(window.location.search).toContain(`area=${DISTRICT}`);
  expect(window.location.search).toContain("old=1");
});
test("opening a possible match shows the explanation panel in the fixed order, detail open", async () => {
  open({
    ...queue({ SUGGESTED: [item(), item({ link_id: LINK2 })] }),
    [`GET /links/${LINK}`]: json(200, detail()),
    [`GET /links/${LINK}/explanation`]: json(200, explanation()),
  });
  await screen.findAllByText("24/118");
  fireEvent.click(screen.getAllByRole("button", { name: "Open" })[0] as HTMLElement);
  expect(await screen.findByText("Please check this link")).toBeTruthy();
  expect(window.location.pathname).toBe(`/review/${LINK}`);
  expect(screen.getByText("Link 1 of 2")).toBeTruthy();
  const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
  expect(headings.indexOf("Why we think so")).toBeGreaterThan(-1);
  expect(headings.indexOf("Why it may be wrong")).toBeGreaterThan(
    headings.indexOf("Why we think so"),
  );
  expect(headings.indexOf("Where this came from")).toBeGreaterThan(
    headings.indexOf("Why it may be wrong"),
  );
  expect(screen.getByText("The evidence is not strong enough for an automatic link.")).toBeTruthy();
  expect(screen.getByText("Nothing found against this link.")).toBeTruthy();
  // Admin detail is open by default and carries the numbers.
  const more = screen.getByRole("button", { name: /More detail/ });
  expect(more.getAttribute("aria-expanded")).toBe("true");
  expect(screen.getByText("Match score: 62.5 (out of 100)")).toBeTruthy();
  expect(screen.getByText("Strong match starts at 80. Possible match starts at 50.")).toBeTruthy();
  expect(screen.getByText("Case 31/207, as stored: 9000014471")).toBeTruthy();
});

test("only Confirm is primary; Reject, Next one and Back are secondary", async () => {
  open({
    ...queue({ SUGGESTED: [item(), item({ link_id: LINK2 })] }),
    [`GET /links/${LINK}`]: json(200, detail()),
    [`GET /links/${LINK}/explanation`]: json(200, explanation()),
  });
  await screen.findAllByText("24/118");
  fireEvent.click(screen.getAllByRole("button", { name: "Open" })[0] as HTMLElement);
  await screen.findByText("Please check this link");
  expect(button("Confirm they are the same").getAttribute("data-variant")).toBe("primary");
  for (const name of ["Reject this link", "Next one", "Back to the list"]) {
    expect(button(name).getAttribute("data-variant")).not.toBe("primary");
  }
});

test("Confirm acts at once and sends the state the officer saw", async () => {
  const { calls } = open({
    ...queue({ SUGGESTED: [item(), item({ link_id: LINK2 })] }),
    [`GET /links/${LINK}`]: json(200, detail()),
    [`GET /links/${LINK}/explanation`]: json(200, explanation()),
    [`POST /links/${LINK}/confirm`]: json(
      200,
      detail({ state: "CONFIRMED", allowed_actions: ["REJECT", "UNDO"] }),
    ),
  });
  await screen.findAllByText("24/118");
  fireEvent.click(screen.getAllByRole("button", { name: "Open" })[0] as HTMLElement);
  await screen.findByText("Please check this link");
  fireEvent.click(button("Confirm they are the same"));
  expect(
    await screen.findByText("You confirmed this link. The two records are now shown as the same."),
  ).toBeTruthy();
  expect(sentBody(calls, `/links/${LINK}/confirm`)).toEqual({ expected_state: "SUGGESTED" });
});

test("Reject needs a reason of 3 to 1000 characters and sends expected_state", async () => {
  const { calls } = open({
    ...queue({ SUGGESTED: [item()] }),
    [`GET /links/${LINK}`]: json(200, detail()),
    [`GET /links/${LINK}/explanation`]: json(200, explanation()),
    [`POST /links/${LINK}/reject`]: json(
      200,
      detail({ state: "REJECTED", allowed_actions: ["REOPEN"] }),
    ),
  });
  await screen.findAllByText("24/118");
  fireEvent.click(button("Open"));
  await screen.findByText("Please check this link");
  fireEvent.click(button("Reject this link"));
  expect(screen.getByText("Reject this link?")).toBeTruthy();
  expect(screen.getByLabelText(/Why are you rejecting it\?/)).toBeTruthy();
  fireEvent.click(button("Yes, reject"));
  expect(calls.some((c) => c.path.endsWith("/reject"))).toBe(false);
  fireEvent.change(screen.getByLabelText(/Why are you rejecting it\?/), {
    target: { value: "ab" },
  });
  fireEvent.click(button("Yes, reject"));
  expect(calls.some((c) => c.path.endsWith("/reject"))).toBe(false);
  fireEvent.change(screen.getByLabelText(/Why are you rejecting it\?/), {
    target: { value: "Different people" },
  });
  fireEvent.click(button("Yes, reject"));
  expect(
    await screen.findByText(
      "You rejected this link. A supervisor can reopen it from the Rejected list.",
    ),
  ).toBeTruthy();
  expect(sentBody(calls, `/links/${LINK}/reject`)).toEqual({
    reason: "Different people",
    expected_state: "SUGGESTED",
  });
});

test("No, go back leaves the reject step with nothing sent", async () => {
  const { calls } = open({
    ...queue({ SUGGESTED: [item()] }),
    [`GET /links/${LINK}`]: json(200, detail()),
    [`GET /links/${LINK}/explanation`]: json(200, explanation()),
  });
  await screen.findAllByText("24/118");
  fireEvent.click(button("Open"));
  await screen.findByText("Please check this link");
  fireEvent.click(button("Reject this link"));
  fireEvent.click(button("No, go back"));
  expect(await screen.findByText("Please check this link")).toBeTruthy();
  expect(calls.some((c) => c.method === "POST")).toBe(false);
});

test("a strong automatic link offers Undo instead of Reject, with its reason step", async () => {
  const { calls } = open(
    {
      ...queue({ SUGGESTED: [] }),
      [`GET /links/${LINK}`]: json(
        200,
        detail({ state: "AUTO", band: "HIGH", allowed_actions: ["UNDO"] }),
      ),
      [`GET /links/${LINK}/explanation`]: json(
        200,
        explanation({ state: "AUTO", gates: { passed: true, failed: [] } }),
      ),
      [`POST /links/${LINK}/undo`]: json(
        200,
        detail({ state: "UNDONE", allowed_actions: ["REOPEN"] }),
      ),
    },
    "en",
    `/review/${LINK}`,
  );
  expect(await screen.findByText("Why these are linked")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Reject this link" })).toBeNull();
  expect(
    screen.getByText("This was linked automatically. You can undo it if it is wrong."),
  ).toBeTruthy();
  fireEvent.click(button("Undo this link"));
  fireEvent.change(screen.getByLabelText(/Why are you undoing it\?/), {
    target: { value: "Number was reused" },
  });
  fireEvent.click(button("Yes, undo"));
  expect(
    await screen.findByText(
      "You undid this link. A supervisor can reopen it from the Undone list.",
    ),
  ).toBeTruthy();
  expect(sentBody(calls, `/links/${LINK}/undo`)).toEqual({
    reason: "Number was reused",
    expected_state: "AUTO",
  });
});

test("a rejected link opens with its history above the panel and one primary button: Reopen", async () => {
  open(
    {
      ...queue({ REJECTED: [rejectedRow()] }),
      [`GET /links/${LINK}`]: json(
        200,
        detail({ state: "REJECTED", allowed_actions: ["REOPEN"], history: rejectedHistory }),
      ),
      [`GET /links/${LINK}/explanation`]: json(200, explanation({ state: "REJECTED" })),
      [`GET /users/${MEENA}`]: user(MEENA, "Meena Rao", "INVESTIGATOR"),
    },
    "en",
    `/review/${LINK}?show=rejected`,
  );
  expect(
    await screen.findByText("Rejected by Meena Rao (Investigating officer) on 12 Mar 2026"),
  ).toBeTruthy();
  expect(screen.getByText("Reason: Different people. Ages differ by 12 years.")).toBeTruthy();
  expect(button("Reopen this link").getAttribute("data-variant")).toBe("primary");
  expect(button("Back to the list").getAttribute("data-variant")).not.toBe("primary");
  expect(screen.queryByRole("button", { name: "Confirm they are the same" })).toBeNull();
});

test("Reopen: the second step needs a reason, then sends it with expected_state", async () => {
  const { calls } = open(
    {
      ...queue({ REJECTED: [rejectedRow()] }),
      [`GET /links/${LINK}`]: json(
        200,
        detail({ state: "REJECTED", allowed_actions: ["REOPEN"], history: rejectedHistory }),
      ),
      [`GET /links/${LINK}/explanation`]: json(200, explanation({ state: "REJECTED" })),
      [`GET /users/${MEENA}`]: user(MEENA, "Meena Rao", "INVESTIGATOR"),
      [`POST /links/${LINK}/reopen`]: json(200, detail({ state: "SUGGESTED" })),
    },
    "en",
    `/review/${LINK}?show=rejected`,
  );
  await screen.findByText(/Rejected by Meena Rao/);
  fireEvent.click(button("Reopen this link"));
  expect(screen.getByText("Reopen this link?")).toBeTruthy();
  expect(
    screen.getByText(
      'It goes back to "Links to check". A person must then confirm or reject it. Matching runs will not change it.',
    ),
  ).toBeTruthy();
  fireEvent.click(button("Yes, reopen"));
  expect(calls.some((c) => c.path.endsWith("/reopen"))).toBe(false);
  fireEvent.change(screen.getByLabelText(/Why are you reopening it\?/), {
    target: { value: "New call record found" },
  });
  fireEvent.click(button("Yes, reopen"));
  expect(
    await screen.findByText('You reopened this link. It is back in "Links to check".'),
  ).toBeTruthy();
  expect(sentBody(calls, `/links/${LINK}/reopen`)).toEqual({
    reason: "New call record found",
    expected_state: "REJECTED",
  });
  expect(button("Open it").getAttribute("data-variant")).toBe("primary");
  expect(button("Back to the list").getAttribute("data-variant")).not.toBe("primary");
});

test("a reopened link carries the Reopened tag, its history and the rerun line", async () => {
  open(
    {
      ...queue({ SUGGESTED: [item()] }),
      [`GET /links/${LINK}`]: json(
        200,
        detail({
          history: [
            ...rejectedHistory,
            {
              from: "REJECTED",
              to: "SUGGESTED",
              at: "2026-03-14T10:00:00Z",
              actor_kind: "USER",
              actor_user_id: CHARU,
              reason_code: "REOPENED",
              reason_text: "New call record found",
            },
          ],
        }),
      ),
      [`GET /links/${LINK}/explanation`]: json(200, explanation()),
      [`GET /users/${MEENA}`]: user(MEENA, "Meena Rao", "INVESTIGATOR"),
      [`GET /users/${CHARU}`]: user(CHARU, "Charu Singh", "SUPERVISOR"),
    },
    "en",
    `/review/${LINK}`,
  );
  expect(
    await screen.findByText(
      "Reopened by Charu Singh on 14 Mar 2026. Earlier it was rejected or undone by Meena Rao on 12 Mar 2026.",
    ),
  ).toBeTruthy();
  expect(screen.getByText("Reopened")).toBeTruthy();
  expect(
    screen.getByText("Matching runs do not change this link. Only a person can."),
  ).toBeTruthy();
  expect(button("Confirm they are the same")).toBeTruthy();
});

test("buttons come only from allowed_actions; a block code gives its line instead", async () => {
  open(
    {
      ...queue({}),
      [`GET /links/${LINK}`]: json(
        200,
        detail({ allowed_actions: [], decision_block: "CROSS_AREA_SENIOR_ONLY" }),
      ),
      [`GET /links/${LINK}/explanation`]: json(200, explanation()),
    },
    "en",
    `/review/${LINK}`,
  );
  expect(
    await screen.findByText(
      "This link joins two police areas. Only a senior officer can decide it.",
    ),
  ).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Confirm they are the same" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Reject this link" })).toBeNull();
  expect(screen.queryByRole("button", { name: /Reopen/ })).toBeNull();
});

test("a rejected link the viewer cannot reopen shows the role line, never a greyed button", async () => {
  open(
    {
      ...queue({}),
      [`GET /links/${LINK}`]: json(
        200,
        detail({
          state: "REJECTED",
          allowed_actions: [],
          decision_block: "ROLE_VIEW_ONLY",
          history: rejectedHistory,
        }),
      ),
      [`GET /links/${LINK}/explanation`]: json(200, explanation({ state: "REJECTED" })),
      [`GET /users/${MEENA}`]: json(403),
    },
    "en",
    `/review/${LINK}`,
  );
  expect(await screen.findByText("Only a supervisor can reopen a link.")).toBeTruthy();
  expect(screen.queryByRole("button", { name: /Reopen/ })).toBeNull();
  // Without a name the history still says what happened and when.
  expect(screen.getByText("Rejected on 12 Mar 2026")).toBeTruthy();
});

test("a link the viewer cannot see is the plain not-found state, never access wording", async () => {
  open(
    {
      ...queue({}),
      [`GET /links/${LINK}`]: json(404, { code: "NOT_FOUND" }),
      [`GET /links/${LINK}/explanation`]: json(404, { code: "NOT_FOUND" }),
    },
    "en",
    `/review/${LINK}`,
  );
  expect(await screen.findByText("We could not find this. Go back and try again.")).toBeTruthy();
  expect(screen.queryByText(/access/i)).toBeNull();
  expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  fireEvent.click(button("Back to the list"));
  await waitFor(() => expect(window.location.pathname).toBe("/review"));
});

test("a decision that finds the link gone shows not-found as well", async () => {
  open(
    {
      ...queue({ SUGGESTED: [item()] }),
      [`GET /links/${LINK}`]: json(200, detail()),
      [`GET /links/${LINK}/explanation`]: json(200, explanation()),
      [`POST /links/${LINK}/confirm`]: json(404, { code: "NOT_FOUND" }),
    },
    "en",
    `/review/${LINK}`,
  );
  await screen.findByText("Please check this link");
  fireEvent.click(button("Confirm they are the same"));
  expect(await screen.findByText("We could not find this. Go back and try again.")).toBeTruthy();
});

test("409 RUN_IN_PROGRESS uses the shared busy-system string", async () => {
  open(
    {
      ...queue({ SUGGESTED: [item()] }),
      [`GET /links/${LINK}`]: json(200, detail()),
      [`GET /links/${LINK}/explanation`]: json(200, explanation()),
      [`POST /links/${LINK}/confirm`]: json(409, { code: "RUN_IN_PROGRESS" }),
    },
    "en",
    `/review/${LINK}`,
  );
  await screen.findByText("Please check this link");
  fireEvent.click(button("Confirm they are the same"));
  expect(
    await screen.findByText("A matching run is in progress. Try again in a few minutes."),
  ).toBeTruthy();
});

test("409 STATE_MISMATCH says someone changed it and offers the list", async () => {
  open(
    {
      ...queue({ SUGGESTED: [item()] }),
      [`GET /links/${LINK}`]: json(200, detail()),
      [`GET /links/${LINK}/explanation`]: json(200, explanation()),
      [`POST /links/${LINK}/confirm`]: json(409, { code: "STATE_MISMATCH" }),
    },
    "en",
    `/review/${LINK}`,
  );
  await screen.findByText("Please check this link");
  fireEvent.click(button("Confirm they are the same"));
  expect(
    await screen.findByText("Someone changed this while you were looking. Please open it again."),
  ).toBeTruthy();
  fireEvent.click(button("Show the list"));
  await waitFor(() => expect(window.location.pathname).toBe("/review"));
});

test("any 503 on a decision shows the safety-pause string", async () => {
  open(
    {
      ...queue({ SUGGESTED: [item()] }),
      [`GET /links/${LINK}`]: json(200, detail()),
      [`GET /links/${LINK}/explanation`]: json(200, explanation()),
      [`POST /links/${LINK}/reject`]: json(503),
    },
    "en",
    `/review/${LINK}`,
  );
  await screen.findByText("Please check this link");
  fireEvent.click(button("Reject this link"));
  fireEvent.change(screen.getByLabelText(/Why are you rejecting it\?/), {
    target: { value: "Different people" },
  });
  fireEvent.click(button("Yes, reject"));
  expect(
    await screen.findByText("The system is paused for a safety check. Try again later."),
  ).toBeTruthy();
});

test("a failed list load shows the failure with Try again", async () => {
  let n = 0;
  open({
    "GET /review-queue": () =>
      n++ < 3 ? json(503) : json(200, { items: [item()], next_cursor: null, total: 1 }),
    "GET /jurisdictions": places,
  });
  expect(
    await screen.findByText("The system is paused for a safety check. Try again later."),
  ).toBeTruthy();
  fireEvent.click(button("Try again"));
  expect((await screen.findAllByText("24/118")).length).toBeGreaterThan(0);
});

test("the list shows Show more past the first page", async () => {
  open({
    "GET /review-queue": ({ url }) => {
      const params = new URL(url).searchParams;
      if (params.get("limit") === "1")
        return json(200, { items: [], next_cursor: null, total: 80 });
      return params.get("cursor")
        ? json(200, { items: [item({ link_id: LINK2 })], next_cursor: null, total: 80 })
        : json(200, { items: [item()], next_cursor: "next-page", total: 80 });
    },
    "GET /jurisdictions": places,
  });
  await screen.findAllByText("24/118");
  fireEvent.click(button("Show more"));
  await waitFor(() => expect(screen.getAllByRole("button", { name: "Open" }).length).toBe(2));
});

test("Next one opens the following link in the list", async () => {
  open({
    ...queue({ SUGGESTED: [item(), item({ link_id: LINK2 })] }),
    [`GET /links/${LINK}`]: json(200, detail()),
    [`GET /links/${LINK}/explanation`]: json(200, explanation()),
    [`GET /links/${LINK2}`]: json(200, detail({ link_id: LINK2 })),
    [`GET /links/${LINK2}/explanation`]: json(200, explanation({ link_id: LINK2 })),
  });
  await screen.findAllByText("24/118");
  fireEvent.click(screen.getAllByRole("button", { name: "Open" })[0] as HTMLElement);
  await screen.findByText("Link 1 of 2");
  fireEvent.click(button("Next one"));
  expect(await screen.findByText("Link 2 of 2")).toBeTruthy();
  expect(window.location.pathname).toBe(`/review/${LINK2}`);
});

test("the page and the panel read in Hindi", async () => {
  open(
    {
      ...queue({ SUGGESTED: [item()], REJECTED: [] }),
      [`GET /links/${LINK}`]: json(200, detail()),
      [`GET /links/${LINK}/explanation`]: json(200, explanation()),
    },
    "hi",
  );
  expect(await screen.findByRole("button", { name: "प्रतीक्षा में (1)" })).toBeTruthy();
  expect(screen.getByText(t("queue.show", "hi"))).toBeTruthy();
  fireEvent.click(screen.getAllByRole("button", { name: "खोलें" })[0] ?? button("Open"));
  expect(await screen.findByText("कृपया इस लिंक को जाँचें")).toBeTruthy();
  expect(t("queue.panel.possible", "hi")).not.toBe(t("queue.panel.possible", "en"));
  expect(screen.getByRole("button", { name: t("queue.confirm", "hi") })).toBeTruthy();
  expect(
    within(document.body).getByText(t("queue.more.score", "hi", { score: "62.5" })),
  ).toBeTruthy();
});
