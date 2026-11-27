import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { useEffect, useState } from "react";
import { afterEach, beforeEach, expect, test } from "vitest";

import { createApi, type AdminApi } from "../api";
import { t } from "../i18n";
import type { Role } from "../nav";
import { usePath } from "../router";
import { DISTRICT, fakeApi, json, renderPage, type Answer, type Routes } from "../testing";
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
    actor: { user_id: MEENA, display_name: "Meena Rao", role: "INVESTIGATOR" },
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

const linkCalls = (calls: { method: string; path: string }[]) =>
  calls.filter((c) => c.path.startsWith("/links/") || c.path.startsWith("/users/"));

const decision = (over: Record<string, unknown> = {}) => ({
  to: "REJECTED",
  at: "2026-03-12T10:00:00Z",
  actor: { user_id: MEENA, display_name: "Meena Rao", role: "INVESTIGATOR" },
  reason_text: "Different people. Ages differ by 12 years.",
  ...over,
});

test("the Rejected table shows By, Reason and the decision date from last_decision, with no per-row call", async () => {
  const { calls } = open(
    {
      ...queue({ SUGGESTED: [], REJECTED: [rejectedRow({ last_decision: decision() })] }),
      [`GET /links/${LINK}`]: json(200, detail({ state: "REJECTED", history: rejectedHistory })),
    },
    "en",
    "/review?show=rejected",
  );
  expect((await screen.findAllByText("24/118")).length).toBeGreaterThan(0);
  for (const header of ["Item", "Case A", "Case B", "By", "Reason", "Rejected on"]) {
    expect(screen.getByRole("columnheader", { name: new RegExp(`^${header}`) })).toBeTruthy();
  }
  for (const header of ["Last change", "Strength"]) {
    expect(screen.queryByRole("columnheader", { name: new RegExp(header) })).toBeNull();
  }
  expect(screen.getByText("Meena Rao")).toBeTruthy();
  expect(screen.getByText("Different people. Ages differ by 12 years.")).toBeTruthy();
  expect(screen.getByText("12 Mar 2026")).toBeTruthy();
  expect(linkCalls(calls)).toEqual([]);
});

test("exactly one list request is made for the view; the other three only count", async () => {
  const { fetchImpl } = open(
    queue({ REJECTED: [rejectedRow({ last_decision: decision() })] }),
    "en",
    "/review?show=rejected",
  );
  await screen.findByText("Meena Rao");
  const urls = (fetchImpl as unknown as { mock: { calls: [string][] } }).mock.calls
    .map(([url]) => new URL(String(url)))
    .filter((url) => url.pathname === "/review-queue");
  expect(urls.filter((url) => url.searchParams.get("limit") === "50").length).toBe(1);
  expect(urls.filter((url) => url.searchParams.get("limit") === "1").length).toBe(3);
});

test("when the actor is null the By cell says A person, never blank and never an id", async () => {
  open(
    queue({ REJECTED: [rejectedRow({ last_decision: decision({ actor: null }) })] }),
    "en",
    "/review?show=rejected",
  );
  expect(await screen.findByText("A person")).toBeTruthy();
  expect(document.body.textContent).not.toContain(MEENA);
});

test("when the actor is null the By cell reads in Hindi", async () => {
  open(
    queue({
      UNDONE: [
        rejectedRow({ state: "UNDONE", last_decision: decision({ to: "UNDONE", actor: null }) }),
      ],
    }),
    "hi",
    "/review?show=undone",
  );
  expect(await screen.findByText("कोई व्यक्ति")).toBeTruthy();
});

test("a long reason stays on one line with an ellipsis; the full text is in the cell title", async () => {
  const long = "Different people. ".repeat(40).trim();
  open(
    queue({ REJECTED: [rejectedRow({ last_decision: decision({ reason_text: long }) })] }),
    "en",
    "/review?show=rejected",
  );
  const cell = await screen.findByText(long);
  expect(cell.className).toContain("admin-cell-clip");
  expect(cell.getAttribute("title")).toBe(long);
});

test("a missing reason shows plain wording, not an empty cell", async () => {
  open(
    queue({ REJECTED: [rejectedRow({ last_decision: decision({ reason_text: null }) })] }),
    "en",
    "/review?show=rejected",
  );
  expect(await screen.findByText("No reason given")).toBeTruthy();
});

test("the Undone table has By, Reason and Undone on", async () => {
  const { calls } = open(
    queue({
      UNDONE: [
        item({
          state: "UNDONE",
          allowed_actions: ["REOPEN"],
          last_decision: decision({ to: "UNDONE", reason_text: "Wrong match." }),
        }),
      ],
    }),
    "en",
    "/review?show=undone",
  );
  expect(
    await screen.findByText("These links were undone. A supervisor can reopen them."),
  ).toBeTruthy();
  for (const header of ["By", "Reason", "Undone on"]) {
    expect(screen.getByRole("columnheader", { name: new RegExp(`^${header}`) })).toBeTruthy();
  }
  expect(screen.getByText("Wrong match.")).toBeTruthy();
  expect(linkCalls(calls)).toEqual([]);
});

test("the Waiting table is unchanged: no By or Reason columns", async () => {
  open(queue({ SUGGESTED: [item({ last_decision: null })] }));
  await screen.findAllByText("24/118");
  for (const header of ["Strength", "Item", "Case A", "Case B", "Main reason", "Waiting since"]) {
    expect(screen.getByRole("columnheader", { name: new RegExp(header) })).toBeTruthy();
  }
  for (const header of ["By", "Rejected on", "Undone on", "Last change"]) {
    expect(screen.queryByRole("columnheader", { name: new RegExp(`^${header}`) })).toBeNull();
  }
});

test("many rejected rows still make no per-row call", async () => {
  const rows = Array.from({ length: 50 }, (_, i) =>
    rejectedRow({
      link_id: `00000000-0000-4000-8000-${String(i).padStart(12, "0")}`,
      last_decision: decision(),
    }),
  );
  const { calls } = open(queue({ REJECTED: rows }), "en", "/review?show=rejected");
  await waitFor(() => expect(screen.getAllByRole("button", { name: "Open" }).length).toBe(50));
  expect(linkCalls(calls)).toEqual([]);
});

test("opening a rejected link makes one link call and shows who, when and why in the panel", async () => {
  const { calls } = open(
    {
      ...queue({ REJECTED: [rejectedRow()] }),
      [`GET /links/${LINK}`]: json(
        200,
        detail({ state: "REJECTED", allowed_actions: ["REOPEN"], history: rejectedHistory }),
      ),
      [`GET /links/${LINK}/explanation`]: json(200, explanation({ state: "REJECTED" })),
    },
    "en",
    "/review?show=rejected",
  );
  await screen.findAllByText("24/118");
  fireEvent.click(button("Open"));
  expect(
    await screen.findByText("Rejected by Meena Rao (Investigating officer) on 12 Mar 2026"),
  ).toBeTruthy();
  expect(screen.getByText("Reason: Different people. Ages differ by 12 years.")).toBeTruthy();
  expect(calls.filter((c) => c.path === `/links/${LINK}`).length).toBe(1);
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
              actor: { user_id: CHARU, display_name: "Charu Singh", role: "SUPERVISOR" },
              reason_code: "REOPENED",
              reason_text: "New call record found",
            },
          ],
        }),
      ),
      [`GET /links/${LINK}/explanation`]: json(200, explanation()),
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

const panelCalls = (calls: { path: string }[]) => calls.filter((c) => c.path.startsWith("/users/"));

const openRejected = (history: unknown[]) =>
  open(
    {
      ...queue({ REJECTED: [rejectedRow()] }),
      [`GET /links/${LINK}`]: json(
        200,
        detail({ state: "REJECTED", allowed_actions: ["REOPEN"], history }),
      ),
      [`GET /links/${LINK}/explanation`]: json(200, explanation({ state: "REJECTED" })),
    },
    "en",
    `/review/${LINK}?show=rejected`,
  );

test("the panel names the deciding person from the link and makes no user call", async () => {
  const { calls } = openRejected(rejectedHistory);
  expect(
    await screen.findByText("Rejected by Meena Rao (Investigating officer) on 12 Mar 2026"),
  ).toBeTruthy();
  expect(panelCalls(calls)).toEqual([]);
});

test("when the link's actor is null the panel words the line without a name and makes no user call", async () => {
  const history = rejectedHistory.map((e) => ("actor" in e ? { ...e, actor: null } : e));
  const { calls } = openRejected(history);
  expect(await screen.findByText("Rejected on 12 Mar 2026")).toBeTruthy();
  expect(document.body.textContent).not.toContain(MEENA);
  expect(panelCalls(calls)).toEqual([]);
});

/** A fake `fetch` whose queue answers can be held back by the test and released later. */
function heldApi(answer: (url: URL) => { hold?: boolean; response: Response }) {
  const held: (() => void)[] = [];
  const fetchImpl = ((input: RequestInfo | URL) => {
    const url = new URL(String(input));
    if (url.pathname === "/jurisdictions") return Promise.resolve(places.clone());
    if (url.pathname !== "/review-queue") return Promise.resolve(json(404));
    const { hold, response } = answer(url);
    if (!hold) return Promise.resolve(response);
    return new Promise<Response>((resolve) => held.push(() => resolve(response)));
  }) as unknown as typeof fetch;
  return {
    api: createApi({ baseUrl: "http://api.test", fetch: fetchImpl }),
    release: () => held.splice(0).forEach((f) => f()),
  };
}

const page = (items: unknown[], extra: Record<string, unknown> = {}) =>
  json(200, { items, next_cursor: null, total: items.length, ...extra });

test("a late answer for an earlier filter does not overwrite the list for the current one", async () => {
  const { api, release } = heldApi((url) =>
    url.searchParams.get("limit") === "1"
      ? { response: page([]) }
      : url.searchParams.get("entity_type") === "PHONE"
        ? { response: page([item({ link_id: LINK2 })]) }
        : {
            hold: true,
            response: page([item({ ends: [end(1, "OLD/1"), end(2, "OLD/2")] })]),
          },
  );
  window.history.replaceState(null, "", "/review");
  renderPage(<Harness api={api} />);
  await screen.findByRole("option", { name: "Rivergate" });
  fireEvent.change(screen.getByLabelText("Type"), { target: { value: "PHONE" } });
  expect((await screen.findAllByText("24/118")).length).toBeGreaterThan(0);
  await act(async () => release());
  expect(screen.queryByText("OLD/1")).toBeNull();
  expect(screen.getAllByText("24/118").length).toBeGreaterThan(0);
});

test("a late Show more answer for an earlier filter is not added to the new list", async () => {
  const { api, release } = heldApi((url) => {
    if (url.searchParams.get("limit") === "1") return { response: page([]) };
    if (url.searchParams.get("cursor"))
      return {
        hold: true,
        response: page([item({ link_id: LINK2, ends: [end(1, "LATE/1"), end(2, "LATE/2")] })]),
      };
    return url.searchParams.get("entity_type") === "PHONE"
      ? { response: page([item()]) }
      : { response: page([item()], { next_cursor: "next-page", total: 80 }) };
  });
  window.history.replaceState(null, "", "/review");
  renderPage(<Harness api={api} />);
  await screen.findAllByText("24/118");
  await screen.findByRole("option", { name: "Rivergate" });
  fireEvent.click(button("Show more"));
  fireEvent.change(screen.getByLabelText("Type"), { target: { value: "PHONE" } });
  await waitFor(() => expect(window.location.search).toContain("type=PHONE"));
  await screen.findAllByText("24/118");
  await act(async () => release());
  expect(screen.queryByText("LATE/1")).toBeNull();
  expect(screen.getAllByRole("button", { name: "Open" }).length).toBe(1);
});

test("when Show more fails the loaded rows stay and the failure shows under them", async () => {
  let failing = true;
  open({
    "GET /review-queue": ({ url }) => {
      const params = new URL(url).searchParams;
      if (params.get("limit") === "1")
        return json(200, { items: [], next_cursor: null, total: 80 });
      if (params.get("cursor"))
        return failing
          ? json(503)
          : json(200, { items: [item({ link_id: LINK2 })], next_cursor: null, total: 80 });
      return json(200, { items: [item()], next_cursor: "next-page", total: 80 });
    },
    "GET /jurisdictions": places,
  });
  await screen.findAllByText("24/118");
  fireEvent.click(button("Show more"));
  expect(
    await screen.findByText("The system is paused for a safety check. Try again later."),
  ).toBeTruthy();
  expect(screen.getAllByRole("button", { name: "Open" }).length).toBe(1);
  failing = false;
  fireEvent.click(button("Try again"));
  await waitFor(() => expect(screen.getAllByRole("button", { name: "Open" }).length).toBe(2));
  expect(
    screen.queryByText("The system is paused for a safety check. Try again later."),
  ).toBeNull();
});

test("the count under the list is the API total, and no count is shown when the API gives none", async () => {
  open({
    "GET /review-queue": ({ url }) => {
      const params = new URL(url).searchParams;
      return params.get("limit") === "1"
        ? json(200, { items: [], next_cursor: null, total: 80 })
        : json(200, { items: [item()], next_cursor: "next-page", total: 80 });
    },
    "GET /jurisdictions": places,
  });
  expect(await screen.findByText("Showing 1 of 80")).toBeTruthy();
  cleanup();
  open({
    "GET /review-queue": ({ url }) => {
      const params = new URL(url).searchParams;
      return params.get("limit") === "1"
        ? json(200, { items: [], next_cursor: null })
        : json(200, { items: [item()], next_cursor: "next-page" });
    },
    "GET /jurisdictions": places,
  });
  await screen.findAllByText("24/118");
  expect(button("Show more")).toBeTruthy();
  expect(screen.queryByText(/Showing \d+ of/)).toBeNull();
});

test("Back from a link keeps the Type, Area and waiting-time filters", async () => {
  open({
    ...queue({ SUGGESTED: [item()] }),
    [`GET /links/${LINK}`]: json(200, detail()),
    [`GET /links/${LINK}/explanation`]: json(200, explanation()),
  });
  await screen.findAllByText("24/118");
  await screen.findByRole("option", { name: "Rivergate" });
  fireEvent.change(screen.getByLabelText("Type"), { target: { value: "PHONE" } });
  fireEvent.change(screen.getByLabelText("Area"), { target: { value: DISTRICT } });
  fireEvent.click(screen.getByLabelText("Waiting more than 7 days"));
  await waitFor(() => expect(window.location.search).toContain("old=1"));
  fireEvent.click(await screen.findByRole("button", { name: "Open" }));
  await screen.findByText("Please check this link");
  fireEvent.click(button("Back to the list"));
  await screen.findAllByText("24/118");
  expect((screen.getByLabelText("Type") as HTMLSelectElement).value).toBe("PHONE");
  expect((screen.getByLabelText("Area") as HTMLSelectElement).value).toBe(DISTRICT);
  expect((screen.getByLabelText("Waiting more than 7 days") as HTMLInputElement).checked).toBe(
    true,
  );
  expect(window.location.search).toContain("type=PHONE");
});

test("a reason of 1000 characters is accepted and 1001 is refused", async () => {
  const { calls } = open(
    {
      ...queue({ SUGGESTED: [item()] }),
      [`GET /links/${LINK}`]: json(200, detail()),
      [`GET /links/${LINK}/explanation`]: json(200, explanation()),
      [`POST /links/${LINK}/reject`]: json(
        200,
        detail({ state: "REJECTED", allowed_actions: ["REOPEN"] }),
      ),
    },
    "en",
    `/review/${LINK}`,
  );
  await screen.findByText("Please check this link");
  fireEvent.click(button("Reject this link"));
  fireEvent.change(screen.getByLabelText(/Why are you rejecting it\?/), {
    target: { value: "x".repeat(1001) },
  });
  fireEvent.click(button("Yes, reject"));
  expect(await screen.findByText(t("state.somethingMissing", "en"))).toBeTruthy();
  expect(calls.some((c) => c.path.endsWith("/reject"))).toBe(false);
  fireEvent.change(screen.getByLabelText(/Why are you rejecting it\?/), {
    target: { value: "x".repeat(1000) },
  });
  fireEvent.click(button("Yes, reject"));
  await screen.findByText(
    "You rejected this link. A supervisor can reopen it from the Rejected list.",
  );
  expect(sentBody(calls, `/links/${LINK}/reject`).reason).toBe("x".repeat(1000));
});

test("a 429 on the link panel says the system is busy, not the sign-in lockout", async () => {
  open(
    {
      ...queue({ SUGGESTED: [item()] }),
      [`GET /links/${LINK}`]: json(429),
      [`GET /links/${LINK}/explanation`]: json(200, explanation()),
    },
    "en",
    `/review/${LINK}`,
  );
  expect(await screen.findByText(t("state.tooManyRequests", "en"))).toBeTruthy();
  expect(screen.queryByText(/15 minutes/)).toBeNull();
  expect(t("state.tooManyRequests", "hi")).not.toBe(t("state.tooManyRequests", "en"));
});

test("when Reject is the only allowed decision it is not the primary button", async () => {
  open(
    {
      ...queue({ SUGGESTED: [item()] }),
      [`GET /links/${LINK}`]: json(200, detail({ allowed_actions: ["REJECT"] })),
      [`GET /links/${LINK}/explanation`]: json(200, explanation()),
    },
    "en",
    `/review/${LINK}`,
  );
  await screen.findByText("Please check this link");
  expect(button("Reject this link").getAttribute("data-variant")).toBe("secondary");
});

/** Answers the link read and the list at once, and keeps the POST open until the test lets it go. */
function slowPostApi() {
  let finish: () => void = () => {};
  const fetchImpl = ((input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input));
    if (init.method === "POST")
      return new Promise<Response>((resolve) => {
        finish = () => resolve(json(200, detail({ state: "CONFIRMED", allowed_actions: [] })));
      });
    if (url.pathname === `/links/${LINK}`) return Promise.resolve(json(200, detail()));
    if (url.pathname === `/links/${LINK}/explanation`)
      return Promise.resolve(json(200, explanation()));
    return Promise.resolve(json(404));
  }) as unknown as typeof fetch;
  return {
    api: createApi({ baseUrl: "http://api.test", fetch: fetchImpl }),
    finish: () => finish(),
  };
}

test("the link panel loads with the shared Loading text and saves with its own line", async () => {
  const neverAnswers = (() => new Promise<Response>(() => {})) as unknown as typeof fetch;
  const waiting = createApi({ baseUrl: "http://api.test", fetch: neverAnswers });
  window.history.replaceState(null, "", `/review/${LINK}`);
  renderPage(<Harness api={waiting} />);
  expect(screen.getByText("Loading...")).toBeTruthy();
  expect(screen.queryByText("Loading your details...")).toBeNull();
  cleanup();

  const { api, finish } = slowPostApi();
  renderPage(<Harness api={api} />);
  await screen.findByText("Please check this link");
  fireEvent.click(button("Confirm they are the same"));
  expect(await screen.findByText("Saving your decision...")).toBeTruthy();
  expect(screen.queryByText("Loading your details...")).toBeNull();
  await act(async () => finish());
});
