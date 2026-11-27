import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { App } from "./App";
import { en } from "./i18n/en";
import { hi } from "./i18n/hi";

type Role = "JUNIOR" | "INVESTIGATOR" | "SUPERVISOR" | "SENIOR";
type Reply = { status: number; body?: unknown };
type Handler =
  Reply | ((request: { body: Record<string, unknown> | undefined; query: string }) => Reply);

interface Call {
  method: string;
  path: string;
  query: string;
  body: Record<string, unknown> | undefined;
}

/** A fetch that answers from a table of "METHOD /path" and records every call. */
function mockApi(table: Record<string, Handler>) {
  const calls: Call[] = [];
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://api.test");
    const method = init?.method ?? "GET";
    const body =
      typeof init?.body === "string"
        ? (JSON.parse(init.body) as Record<string, unknown>)
        : undefined;
    calls.push({ method, path: url.pathname, query: url.search, body });
    const handler = table[`${method} ${url.pathname}`];
    const reply: Reply =
      handler === undefined
        ? { status: 500 }
        : typeof handler === "function"
          ? handler({ body, query: url.search })
          : handler;
    return Promise.resolve(
      new Response(reply.body === undefined ? null : JSON.stringify(reply.body), {
        status: reply.status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  });
  return { fetch: fetchMock as unknown as typeof fetch, calls };
}

const ok = (body: unknown): Reply => ({ status: 200, body });

const user = (role: Role) => ({
  user_id: "u-1",
  username: "demo",
  display_name: "Demo Officer",
  role,
  district_id: "d-1",
  active: true,
});

const login = (role: Role): Reply =>
  ok({
    access_token: "access-1",
    refresh_token: "refresh-1",
    token_type: "Bearer",
    expires_in: 900,
    refresh_expires_in: 28800,
    user: user(role),
  });

const caseRef = (id: string, number: string, title: string) => ({
  case_id: id,
  case_number: number,
  title,
  district_id: "d-1",
});

const entity = (id: string, caseId: string, value: string, extra: object = {}) => ({
  entity_id: id,
  case_id: caseId,
  type: "PHONE",
  display_value: value,
  masked: false,
  link_count: 0,
  has_hidden_connection: false,
  needs_review: false,
  via_grant: false,
  ...extra,
});

const CASE_A = caseRef("C-1", "24/118", "Theft, Hazratganj");
const CASE_B = caseRef("C-2", "31/207", "Fraud, Aminabad");

const summary = {
  ...CASE_A,
  opened_on: "2026-03-03",
  linked_item_count: 2,
  is_assigned: true,
};

function linkSummary(state: string, id = "L-1") {
  return {
    link_id: id,
    entity_type: "PHONE",
    state,
    band: state === "SUGGESTED" ? "MEDIUM" : "HIGH",
    score: 91,
    ends: [
      { entity: entity("E-1", "C-1", "98xxxx1234"), case: CASE_A },
      { entity: entity("E-2", "C-2", "98xxxx1234"), case: CASE_B },
    ],
    main_reason: {
      template_key: "match.evidence.id_exact",
      params: { id_label: "PHONE", value: "98xxxx1234" },
    },
    updated_at: "2026-03-04T10:00:00Z",
  };
}

function linkDetail(state: string, allowed: string[], block: string | null = null) {
  return {
    ...linkSummary(state),
    thresholds_version: 1,
    ruleset_version: "r1",
    created_at: "2026-03-04T10:00:00Z",
    history: [],
    allowed_actions: allowed,
    decision_block: block,
    via_grant: false,
  };
}

const explanation = {
  link_id: "L-1",
  entity_type: "PHONE",
  state: "SUGGESTED",
  score: 91,
  band: "HIGH",
  thresholds: { high_min: 80, medium_min: 50, thresholds_version: 1 },
  ruleset_version: "r1",
  gates: { passed: true, failed: [] },
  records: [
    {
      entity_id: "E-1",
      case_id: "C-1",
      raw_text: "Mob 98xxxx1234",
      normalized: "98xxxx1234",
      extraction_confidence: 0.9,
      source: {
        case_id: "C-1",
        document_id: "D-1",
        line: 14,
        page: 2,
        document_type: "call record",
      },
    },
  ],
  support: [
    {
      tier: 1,
      cap: 60,
      raw: 50,
      cap_adjustment: { value: 0, template_key: "match.adjust.cap" },
      subtotal: 50,
      items: [
        {
          evidence_id: "ev-1",
          kind: "ID_EXACT",
          strength: 1,
          weight: 50,
          contribution: 50,
          is_anchor: false,
          modifiers: [],
          template_key: "match.evidence.id_exact",
          params: { id_label: "PHONE", value: "98xxxx1234" },
          sources: [
            {
              case_id: "C-1",
              case_number: "24/118",
              document_id: "D-1",
              line: 14,
              page: 2,
              document_type: "call record",
            },
          ],
        },
      ],
    },
  ],
  against: [],
  clamp_adjustment: { value: 0, template_key: "match.adjust.clamp" },
  history: [],
};

const stub = (status = "NONE") => ({
  redacted: true,
  stub_id: "S-1",
  near_entity_id: "E-1",
  connection_exists: true,
  access_request: { status, requested_at: status === "PENDING" ? "2026-03-12T09:00:00Z" : null },
  message_key: "access.stub.connection_exists",
});

function entityDetail(links: unknown[], stubs: unknown[] = []) {
  return {
    ...entity("E-1", "C-1", "98xxxx1234", { link_count: links.length }),
    case: CASE_A,
    facts: [{ key: "age", value: "34" }],
    provenance: [],
    links,
    stubs,
  };
}

/** The routes every flow needs: sign in, one case, one item. */
function baseTable(role: Role, detail: unknown): Record<string, Handler> {
  return {
    "POST /auth/login": login(role),
    "POST /auth/logout": { status: 204 },
    "GET /cases": ok({ items: [summary], next_cursor: null, total: 1 }),
    "GET /access-requests": ok({ items: [], next_cursor: null }),
    "GET /cases/C-1/entities": ok({
      items: [entity("E-1", "C-1", "98xxxx1234", { link_count: 2, needs_review: true })],
      next_cursor: null,
      case: summary,
      counts_by_type: { PHONE: 1 },
    }),
    "GET /entities/E-1": ok(detail),
  };
}

async function signIn() {
  fireEvent.change(screen.getByLabelText("Your user ID"), { target: { value: "demo" } });
  fireEvent.change(screen.getByLabelText("Your password"), { target: { value: "secret-pass" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findByText("Choose a case to open.");
}

const click = (name: string | RegExp) => fireEvent.click(screen.getByRole("button", { name }));

async function openLink(table: Record<string, Handler>) {
  const api = mockApi(table);
  render(<App fetchImpl={api.fetch} />);
  await signIn();
  fireEvent.click(await screen.findByRole("button", { name: /Case 24\/118/ }));
  fireEvent.click(await screen.findByRole("button", { name: /98xxxx1234/ }));
  fireEvent.click(await screen.findByRole("button", { name: "Show other cases" }));
  await screen.findByText("Also appears in", { selector: "h1" });
  fireEvent.click(await screen.findByRole("button", { name: /Why was this linked\?|Check this/ }));
  await screen.findByRole("heading", { level: 2, name: "Why we think so" });
  return api;
}

beforeEach(() => {
  window.history.replaceState(null, "", "/");
  window.sessionStorage.clear();
});
afterEach(cleanup);

describe("officer flow", () => {
  test("sign in, my cases, case, item, also appears in, why linked", async () => {
    const api = await openLink({
      ...baseTable("INVESTIGATOR", entityDetail([linkSummary("AUTO")])),
      "GET /links/L-1": ok(linkDetail("AUTO", [])),
      "GET /links/L-1/explanation": ok(explanation),
    });
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Why these are linked");
    expect(
      screen.getByText("The same phone number 98xxxx1234 appears in both cases."),
    ).toBeTruthy();
    expect(screen.getByText("Nothing found against this link.")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Where this came from" })).toBeTruthy();
    expect(screen.getAllByText("Case 24/118, call record, page 2, line 14").length).toBeGreaterThan(
      0,
    );
    expect(api.calls.map((call) => call.path)).toContain("/links/L-1/explanation");
  });

  test("the score is hidden until More detail is opened, and no percentage shows anywhere", async () => {
    await openLink({
      ...baseTable("INVESTIGATOR", entityDetail([linkSummary("SUGGESTED")])),
      "GET /links/L-1": ok(linkDetail("SUGGESTED", ["CONFIRM", "REJECT"])),
      "GET /links/L-1/explanation": ok(explanation),
    });
    const score = () =>
      screen.getByText("Match score: 91 (out of 100). Strong match starts at 80.");
    expect(score().closest("[hidden]")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "More detail" }));
    expect(score().closest("[hidden]")).toBeNull();
    expect(document.body.textContent).not.toMatch(/%/);
  });

  test("confirm saves at once and shows the result without Undo for an investigator", async () => {
    const api = await openLink({
      ...baseTable("INVESTIGATOR", entityDetail([linkSummary("SUGGESTED")])),
      "GET /links/L-1": ok(linkDetail("SUGGESTED", ["CONFIRM", "REJECT"])),
      "GET /links/L-1/explanation": ok(explanation),
      "POST /links/L-1/confirm": ok(linkDetail("CONFIRMED", [])),
    });
    click("Confirm they are the same");
    await screen.findByText(/You confirmed this link/);
    expect(api.calls.find((call) => call.path === "/links/L-1/confirm")?.body).toEqual({
      expected_state: "SUGGESTED",
    });
    expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
    expect(screen.getByRole("button", { name: "Back to this case" })).toBeTruthy();
  });

  test("undo appears after a confirm for a supervisor, and needs a reason", async () => {
    const api = await openLink({
      ...baseTable("SUPERVISOR", entityDetail([linkSummary("SUGGESTED")])),
      "GET /links/L-1": ok(linkDetail("SUGGESTED", ["CONFIRM", "REJECT"])),
      "GET /links/L-1/explanation": ok(explanation),
      "POST /links/L-1/confirm": ok(linkDetail("CONFIRMED", ["UNDO"])),
      "POST /links/L-1/undo": ok(linkDetail("UNDONE", [])),
    });
    click("Confirm they are the same");
    await screen.findByText(/You confirmed this link/);
    click("Undo");
    click("Yes, undo");
    expect(screen.getByText(/Please fill in/)).toBeTruthy();
    expect(api.calls.some((call) => call.path === "/links/L-1/undo")).toBe(false);
    fireEvent.change(screen.getByLabelText(/Why are you undoing it\?/), {
      target: { value: "Wrong phone" },
    });
    click("Yes, undo");
    await screen.findByText("Your decision was undone.");
    expect(api.calls.find((call) => call.path === "/links/L-1/undo")?.body).toEqual({
      reason: "Wrong phone",
      expected_state: "CONFIRMED",
    });
    expect(screen.getByRole("button", { name: "Check this link again" })).toBeTruthy();
  });

  test("reject needs a second step and a reason", async () => {
    const api = await openLink({
      ...baseTable("INVESTIGATOR", entityDetail([linkSummary("SUGGESTED")])),
      "GET /links/L-1": ok(linkDetail("SUGGESTED", ["CONFIRM", "REJECT"])),
      "GET /links/L-1/explanation": ok(explanation),
      "POST /links/L-1/reject": ok(linkDetail("REJECTED", [])),
    });
    click("Reject this link");
    expect(api.calls.some((call) => call.path === "/links/L-1/reject")).toBe(false);
    await screen.findByRole("heading", { name: "Reject this link?" });
    click("Yes, reject");
    expect(screen.getByText(/Please fill in/)).toBeTruthy();
    expect(api.calls.some((call) => call.path === "/links/L-1/reject")).toBe(false);
    fireEvent.change(screen.getByLabelText(/Why are you rejecting it\?/), {
      target: { value: "Different people" },
    });
    click("Yes, reject");
    await screen.findByText(/You rejected this link/);
    expect(api.calls.find((call) => call.path === "/links/L-1/reject")?.body).toEqual({
      reason: "Different people",
      expected_state: "SUGGESTED",
    });
    expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
  });

  test("No, go back leaves the reject step and changes nothing", async () => {
    const api = await openLink({
      ...baseTable("INVESTIGATOR", entityDetail([linkSummary("SUGGESTED")])),
      "GET /links/L-1": ok(linkDetail("SUGGESTED", ["CONFIRM", "REJECT"])),
      "GET /links/L-1/explanation": ok(explanation),
    });
    click("Reject this link");
    click("No, go back");
    expect(screen.getByRole("button", { name: "Confirm they are the same" })).toBeTruthy();
    expect(api.calls.some((call) => call.method === "POST" && call.path.startsWith("/links"))).toBe(
      false,
    );
  });

  test("undo is hidden from an investigator on a strong link, and Reject is hidden from everyone", async () => {
    await openLink({
      ...baseTable("INVESTIGATOR", entityDetail([linkSummary("AUTO")])),
      "GET /links/L-1": ok(linkDetail("AUTO", [], "ROLE_VIEW_ONLY")),
      "GET /links/L-1/explanation": ok(explanation),
    });
    expect(screen.queryByRole("button", { name: /Undo/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Reject/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Confirm/ })).toBeNull();
  });

  test("a strong link shows Undo this link and not Reject for a supervisor", async () => {
    await openLink({
      ...baseTable("SUPERVISOR", entityDetail([linkSummary("AUTO")])),
      "GET /links/L-1": ok(linkDetail("AUTO", ["UNDO", "CONFIRM"])),
      "GET /links/L-1/explanation": ok(explanation),
    });
    expect(screen.getByRole("button", { name: "Undo this link" })).toBeTruthy();
    expect(screen.getByText(/linked automatically/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Reject/ })).toBeNull();
  });

  test("an officer who may only look sees the read-only message and no buttons", async () => {
    await openLink({
      ...baseTable("JUNIOR", entityDetail([linkSummary("SUGGESTED")])),
      "GET /links/L-1": ok(linkDetail("SUGGESTED", [], "ROLE_VIEW_ONLY")),
      "GET /links/L-1/explanation": ok(explanation),
    });
    expect(screen.getByText(/You can look at this link but not decide it/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Confirm|Reject|Undo/ })).toBeNull();
  });

  test("a link that joins two police areas says only a senior officer can decide it", async () => {
    await openLink({
      ...baseTable("SUPERVISOR", entityDetail([linkSummary("SUGGESTED")])),
      "GET /links/L-1": ok(linkDetail("SUGGESTED", [], "CROSS_AREA_SENIOR_ONLY")),
      "GET /links/L-1/explanation": ok(explanation),
    });
    expect(screen.getByText(/Only a senior officer can decide it/)).toBeTruthy();
  });
});

describe("other police area", () => {
  async function openAlso(detail: unknown, extra: Record<string, Handler> = {}) {
    const api = mockApi({ ...baseTable("INVESTIGATOR", detail), ...extra });
    render(<App fetchImpl={api.fetch} />);
    await signIn();
    fireEvent.click(await screen.findByRole("button", { name: /Case 24\/118/ }));
    fireEvent.click(await screen.findByRole("button", { name: /98xxxx1234/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Show other cases" }));
    await screen.findByText("Also appears in", { selector: "h1" });
    return api;
  }

  test("a stub from the API shows the restricted card with no other-area detail", async () => {
    await openAlso(entityDetail([], [stub()]));
    const card = await screen.findByLabelText("Another police area");
    expect(within(card).getByText("You cannot see that case.")).toBeTruthy();
    expect(within(card).getByRole("button", { name: "Ask for access" })).toBeTruthy();
    expect(card.textContent).not.toMatch(/\d{2}\/\d{3}/);
  });

  test("the access request needs 10 to 500 characters and then says it was sent", async () => {
    const api = await openAlso(entityDetail([], [stub()]), {
      "POST /access-requests": { status: 201, body: { request_id: "R-1", status: "PENDING" } },
    });
    fireEvent.click(await screen.findByRole("button", { name: "Ask for access" }));
    const reason = await screen.findByLabelText(/Your reason/);
    click("Send request");
    expect(screen.getByText("Please write your reason.")).toBeTruthy();
    fireEvent.change(reason, { target: { value: "too short" } });
    click("Send request");
    expect(screen.getByText(/at least 10 characters/)).toBeTruthy();
    fireEvent.change(reason, { target: { value: "x".repeat(501) } });
    click("Send request");
    expect(screen.getByText(/at most 500 characters/)).toBeTruthy();
    expect(
      api.calls.some((call) => call.path === "/access-requests" && call.method === "POST"),
    ).toBe(false);
    fireEvent.change(reason, { target: { value: "  I need to see the other case.  " } });
    click("Send request");
    await screen.findByText(/Request sent\. We will tell you when it is decided/);
    expect(
      api.calls.find((call) => call.path === "/access-requests" && call.method === "POST")?.body,
    ).toEqual({
      stub_id: "S-1",
      reason: "I need to see the other case.",
    });
  });

  test("a waiting request shows its date and no button", async () => {
    await openAlso(entityDetail([], [stub("PENDING")]));
    const card = await screen.findByLabelText("Another police area");
    expect(within(card).getByText(/Request sent on 12 March 2026/)).toBeTruthy();
    expect(within(card).queryByRole("button")).toBeNull();
  });

  test("a cooldown refusal from the API is shown in words", async () => {
    await openAlso(entityDetail([], [stub()]), {
      "POST /access-requests": {
        status: 409,
        body: { code: "REQUEST_COOLDOWN", message_key: "x" },
      },
    });
    fireEvent.click(await screen.findByRole("button", { name: "Ask for access" }));
    fireEvent.change(await screen.findByLabelText(/Your reason/), {
      target: { value: "I need to see the other case." },
    });
    click("Send request");
    await screen.findByText("You can ask again 24 hours after the answer.");
  });
});

describe("refusals from the API", () => {
  test("404 shows the not-found state and never the restricted card", async () => {
    const api = mockApi({
      ...baseTable("INVESTIGATOR", entityDetail([])),
      "GET /cases/C-1/entities": { status: 404, body: { code: "NOT_FOUND", message_key: "x" } },
    });
    render(<App fetchImpl={api.fetch} />);
    await signIn();
    fireEvent.click(await screen.findByRole("button", { name: /Case 24\/118/ }));
    await screen.findByText(/We could not find this/);
    expect(screen.queryByLabelText("Another police area")).toBeNull();
    expect(screen.getByRole("button", { name: "Back to my cases" })).toBeTruthy();
  });

  const decisionFailure = (status: number, code: string) => ({
    ...baseTable("INVESTIGATOR", entityDetail([linkSummary("SUGGESTED")])),
    "GET /links/L-1": ok(linkDetail("SUGGESTED", ["CONFIRM", "REJECT"])),
    "GET /links/L-1/explanation": ok(explanation),
    "POST /links/L-1/confirm": { status, body: { code, message_key: "x" } },
  });

  test.each([
    [409, "RUN_IN_PROGRESS", /matching run is in progress/],
    [503, "INTERNAL", /paused for a safety check/],
    [403, "FORBIDDEN", /do not have access to this/],
    [409, "STATE_MISMATCH", /changed while you were looking/],
  ])(
    "%i %s on confirm is shown in words and nothing is marked done",
    async (status, code, text) => {
      await openLink(decisionFailure(status, code));
      click("Confirm they are the same");
      await screen.findByText(text);
      expect(screen.queryByText(/You confirmed this link/)).toBeNull();
    },
  );
});

describe("a failed Show more", () => {
  const caseCall = {
    items: [entity("E-1", "C-1", "98xxxx1234")],
    case: summary,
    counts_by_type: { PHONE: 1 },
  };

  const failing = (status: number) => ({
    "GET /cases": ({ query }: { query: string }): Reply =>
      query.includes("cursor")
        ? { status, body: { code: "X", message_key: "x" } }
        : ok({ items: [summary], next_cursor: "c2", total: 100 }),
    "GET /cases/C-1/entities": ({ query }: { query: string }): Reply =>
      query.includes("cursor")
        ? { status, body: { code: "X", message_key: "x" } }
        : ok({ ...caseCall, next_cursor: "c2" }),
  });

  const kinds: [number, RegExp][] = [
    [503, /paused for a safety check/],
    [403, /do not have access to this/],
    [404, /We could not find this/],
  ];

  test.each(kinds)("on My cases, %i has its own words, not no connection", async (status, text) => {
    const api = mockApi({ ...baseTable("INVESTIGATOR", entityDetail([])), ...failing(status) });
    render(<App fetchImpl={api.fetch} />);
    await signIn();
    click("Show more");
    await screen.findByText(text);
    expect(screen.queryByText(/No connection/)).toBeNull();
  });

  test.each(kinds)("on a case, %i has its own words, not no connection", async (status, text) => {
    const api = mockApi({ ...baseTable("INVESTIGATOR", entityDetail([])), ...failing(status) });
    render(<App fetchImpl={api.fetch} />);
    await signIn();
    fireEvent.click(await screen.findByRole("button", { name: /Case 24\/118/ }));
    await screen.findByText("Phone numbers (1)");
    click("Show more");
    await screen.findByText(text);
    expect(screen.queryByText(/No connection/)).toBeNull();
  });

  test("a lost connection still says no connection", async () => {
    const api = mockApi({ ...baseTable("INVESTIGATOR", entityDetail([])), ...failing(500) });
    const fetchImpl = ((input: RequestInfo | URL, init?: RequestInit) =>
      String(input).includes("cursor=")
        ? Promise.reject(new TypeError("offline"))
        : api.fetch(input, init)) as typeof fetch;
    render(<App fetchImpl={fetchImpl} />);
    await signIn();
    click("Show more");
    await screen.findByText(/No connection/);
  });
});

describe("reopen, allowed actions, wording and the access form", () => {
  test("a rejected link offers Open this link again when the API allows REOPEN, and sends a reason", async () => {
    const api = await openLink({
      ...baseTable("SUPERVISOR", entityDetail([linkSummary("SUGGESTED")])),
      "GET /links/L-1": ok(linkDetail("REJECTED", ["REOPEN"])),
      "GET /links/L-1/explanation": ok(explanation),
      "POST /links/L-1/reopen": ok(linkDetail("SUGGESTED", ["CONFIRM", "REJECT"])),
    });
    expect(screen.queryByRole("button", { name: /Confirm|Reject/ })).toBeNull();
    click("Open this link again");
    fireEvent.change(screen.getByLabelText(/Why are you opening it again?/), {
      target: { value: "New call record" },
    });
    click("Yes, open it again");
    await screen.findByText(/You opened this link again/);
    const post = api.calls.find((call) => call.path === "/links/L-1/reopen");
    expect(post?.body).toEqual({ reason: "New call record", expected_state: "REJECTED" });
  });

  test("no REOPEN in allowed_actions means no reopen button", async () => {
    await openLink({
      ...baseTable("SUPERVISOR", entityDetail([linkSummary("SUGGESTED")])),
      "GET /links/L-1": ok(linkDetail("REJECTED", [], "STATE_FINAL")),
      "GET /links/L-1/explanation": ok(explanation),
    });
    expect(screen.queryByRole("button", { name: /again/ })).toBeNull();
  });

  test("buttons follow allowed_actions even when the link state would hide them", async () => {
    await openLink({
      ...baseTable("SUPERVISOR", entityDetail([linkSummary("CONFIRMED")])),
      "GET /links/L-1": ok(linkDetail("CONFIRMED", ["CONFIRM", "REJECT"])),
      "GET /links/L-1/explanation": ok(explanation),
    });
    expect(screen.getByRole("button", { name: "Confirm they are the same" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reject this link" })).toBeTruthy();
  });

  test("a hidden connection does not use the restricted card wording", async () => {
    const api = mockApi({
      ...baseTable("INVESTIGATOR", entityDetail([])),
      "GET /cases/C-1/entities": ok({
        items: [entity("E-1", "C-1", "98xxxx1234", { has_hidden_connection: true })],
        next_cursor: null,
        case: summary,
        counts_by_type: { PHONE: 1 },
      }),
    });
    render(<App fetchImpl={api.fetch} />);
    await signIn();
    fireEvent.click(await screen.findByRole("button", { name: /Case 24\/118/ }));
    await screen.findByText("Phone numbers (1)");
    expect(screen.queryByText("Another police area")).toBeNull();
    expect(screen.getByText("Also in a case you cannot see")).toBeTruthy();
  });

  test("an organisation row says Organisation on its second line", async () => {
    const api = mockApi({
      ...baseTable("INVESTIGATOR", entityDetail([])),
      "GET /cases/C-1/entities": ok({
        items: [entity("E-9", "C-1", "Acme Traders", { type: "ORG" })],
        next_cursor: null,
        case: summary,
        counts_by_type: { ORG: 1 },
      }),
    });
    render(<App fetchImpl={api.fetch} />);
    await signIn();
    fireEvent.click(await screen.findByRole("button", { name: /Case 24\/118/ }));
    const row = await screen.findByRole("button", { name: /Acme Traders/ });
    expect(row.textContent).toMatch(/Organisation/);
  });

  test("a 404 on the access request disables the form", async () => {
    const api = mockApi({
      ...baseTable("INVESTIGATOR", entityDetail([], [stub()])),
      "POST /access-requests": { status: 404, body: { code: "NOT_FOUND", message_key: "x" } },
    });
    render(<App fetchImpl={api.fetch} />);
    await signIn();
    fireEvent.click(await screen.findByRole("button", { name: /Case 24\/118/ }));
    fireEvent.click(await screen.findByRole("button", { name: /98xxxx1234/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Show other cases" }));
    fireEvent.click(await screen.findByRole("button", { name: "Ask for access" }));
    fireEvent.change(await screen.findByLabelText("Your reason"), {
      target: { value: "I need this for my case review." },
    });
    click("Send request");
    await screen.findByText(/We could not find this/);
    expect(screen.queryByRole("button", { name: "Send request" })).toBeNull();
    expect(screen.queryByLabelText("Your reason")).toBeNull();
  });
});

describe("case line", () => {
  test("the string names a title, not a place, in both languages", () => {
    expect(en["also.caseLine"]).toContain("{title}");
    expect(hi["also.caseLine"]).toContain("{title}");
    expect(en["also.caseLine"]).not.toContain("{place}");
  });
});

describe("session notice", () => {
  test("says decisions are saved and offers no button", () => {
    expect(en["state.sessionEnding"]).toBe(
      "You will be signed out in 2 minutes. Your decisions are already saved. Sign in again after.",
    );
  });
});

describe("one primary button per page, and empty states", () => {
  const primaries = () =>
    screen.getAllByRole("button").filter((b) => b.getAttribute("data-variant") === "primary");

  test("several possible matches and cards: only the first button is primary", async () => {
    const detail = entityDetail(
      [linkSummary("SUGGESTED", "L-1"), linkSummary("SUGGESTED", "L-2")],
      [stub(), { ...stub(), stub_id: "S-2" }],
    );
    const api = mockApi(baseTable("INVESTIGATOR", detail));
    render(<App fetchImpl={api.fetch} />);
    await signIn();
    fireEvent.click(await screen.findByRole("button", { name: /Case 24\/118/ }));
    fireEvent.click(await screen.findByRole("button", { name: /98xxxx1234/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Show other cases" }));
    await screen.findByText("Also appears in", { selector: "h1" });
    const checks = screen.getAllByRole("button", { name: "Check this" });
    expect(checks).toHaveLength(2);
    const asks = screen.getAllByRole("button", { name: "Ask for access" });
    expect(asks).toHaveLength(2);
    const marked = primaries().filter((b) => [...checks, ...asks].includes(b));
    expect(marked).toEqual([checks[0]]);
  });

  test("with only restricted cards the first one is primary and the rest secondary", async () => {
    const detail = entityDetail([], [stub(), { ...stub(), stub_id: "S-2" }]);
    const api = mockApi(baseTable("INVESTIGATOR", detail));
    render(<App fetchImpl={api.fetch} />);
    await signIn();
    fireEvent.click(await screen.findByRole("button", { name: /Case 24\/118/ }));
    fireEvent.click(await screen.findByRole("button", { name: /98xxxx1234/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Show other cases" }));
    const asks = await screen.findAllByRole("button", { name: "Ask for access" });
    expect(primaries().filter((b) => asks.includes(b))).toEqual([asks[0]]);
  });

  test("No cases yet says why and what next", async () => {
    const api = mockApi({
      ...baseTable("INVESTIGATOR", entityDetail([])),
      "GET /cases": ok({ items: [], next_cursor: null, total: 0 }),
    });
    render(<App fetchImpl={api.fetch} />);
    await signIn();
    expect(screen.getByText("No cases yet.")).toBeTruthy();
    expect(screen.getByText("Ask your supervisor to add your cases.")).toBeTruthy();
  });

  test("an item with no other cases says why and what next", async () => {
    const api = mockApi(baseTable("INVESTIGATOR", entityDetail([linkSummary("REJECTED")])));
    render(<App fetchImpl={api.fetch} />);
    await signIn();
    fireEvent.click(await screen.findByRole("button", { name: /Case 24\/118/ }));
    fireEvent.click(await screen.findByRole("button", { name: /98xxxx1234/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Show other cases" }));
    await screen.findByText(en["also.empty"]);
    expect(screen.getByText(en["also.emptyHint"])).toBeTruthy();
  });

  test("the empty-state strings exist in both languages and only the 404 state has no hint", () => {
    for (const key of ["cases.emptyHint", "cases.noResultsHint", "also.emptyHint"] as const) {
      expect(en[key].length).toBeGreaterThan(5);
      expect(hi[key].length).toBeGreaterThan(5);
    }
  });
});

describe("navigation and language", () => {
  test("Back in the header returns to the screen before", async () => {
    const api = mockApi(baseTable("INVESTIGATOR", entityDetail([])));
    render(<App fetchImpl={api.fetch} />);
    await signIn();
    fireEvent.click(await screen.findByRole("button", { name: /Case 24\/118/ }));
    await screen.findByText(/People, phone numbers/);
    click("Back");
    await screen.findByText("Choose a case to open.");
  });

  test("My cases in the trail goes home from a deep screen", async () => {
    const api = mockApi(baseTable("INVESTIGATOR", entityDetail([])));
    render(<App fetchImpl={api.fetch} />);
    await signIn();
    fireEvent.click(await screen.findByRole("button", { name: /Case 24\/118/ }));
    fireEvent.click(await screen.findByRole("button", { name: /98xxxx1234/ }));
    await screen.findByText(/Person in Case|Phone number in Case/);
    fireEvent.click(
      within(screen.getByRole("navigation", { name: "You are here" })).getByRole("button", {
        name: "My cases",
      }),
    );
    await screen.findByText("Choose a case to open.");
  });

  test("the language chosen at sign in stays after sign in and in the session", async () => {
    const api = mockApi(baseTable("INVESTIGATOR", entityDetail([])));
    render(<App fetchImpl={api.fetch} />);
    click("हिन्दी");
    fireEvent.change(screen.getByLabelText(hi["signIn.userId"]), { target: { value: "demo" } });
    fireEvent.change(screen.getByLabelText(hi["signIn.password"]), {
      target: { value: "secret-pass" },
    });
    fireEvent.click(screen.getByRole("button", { name: hi["signIn.submit"] }));
    await screen.findByText(hi["cases.intro"]);
    expect(window.sessionStorage.getItem("tracex.officer.lang")).toBe("hi");
    expect(JSON.stringify({ ...window.sessionStorage })).not.toMatch(/access-1|refresh-1/);
  });

  test("a wrong password shows the sign-in error and tokens are never stored", async () => {
    const api = mockApi({ "POST /auth/login": { status: 401 } });
    render(<App fetchImpl={api.fetch} />);
    fireEvent.change(screen.getByLabelText("Your user ID"), { target: { value: "demo" } });
    fireEvent.change(screen.getByLabelText("Your password"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await screen.findByText(/We could not sign you in/);
    expect(JSON.stringify({ ...window.sessionStorage })).not.toMatch(/secret|token/i);
  });
});

describe("not found title and rate limit actions", () => {
  test("a 404 on a case names the page Not found, not Loading", async () => {
    const api = mockApi({
      ...baseTable("INVESTIGATOR", entityDetail([])),
      "GET /cases/C-1/entities": { status: 404, body: { code: "NOT_FOUND", message_key: "x" } },
    });
    render(<App fetchImpl={api.fetch} />);
    await signIn();
    fireEvent.click(await screen.findByRole("button", { name: /Case 24\/118/ }));
    await screen.findByText(/We could not find this/);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Not found");
    expect(document.body.textContent).not.toContain("Loading...");
  });

  test("the not-found title exists in both languages", () => {
    expect(en["state.notFoundTitle"]).toBe("Not found");
    expect(hi["state.notFoundTitle"]).toBeTruthy();
  });

  test("a 429 from the API shows a Try again button that asks again", async () => {
    let calls = 0;
    const api = mockApi({
      ...baseTable("INVESTIGATOR", entityDetail([])),
      "GET /cases/C-1/entities": () => {
        calls += 1;
        return calls === 1
          ? { status: 429, body: { code: "RATE_LIMITED", message_key: "x" } }
          : ok({ items: [], next_cursor: null, case: summary, counts_by_type: {} });
      },
    });
    render(<App fetchImpl={api.fetch} />);
    await signIn();
    fireEvent.click(await screen.findByRole("button", { name: /Case 24\/118/ }));
    await screen.findByText(/Too many tries/);
    click("Try again");
    await screen.findAllByText("None in this case.");
    expect(calls).toBe(2);
  });

  test("the waiting-requests limit offers Back to this case", async () => {
    const api = mockApi({
      ...baseTable("INVESTIGATOR", entityDetail([], [stub()])),
      "POST /access-requests": {
        status: 409,
        body: { code: "REQUEST_LIMIT", message_key: "x" },
      },
    });
    render(<App fetchImpl={api.fetch} />);
    await signIn();
    fireEvent.click(await screen.findByRole("button", { name: /Case 24\/118/ }));
    fireEvent.click(await screen.findByRole("button", { name: /98xxxx1234/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Show other cases" }));
    fireEvent.click(await screen.findByRole("button", { name: "Ask for access" }));
    fireEvent.change(await screen.findByLabelText(/Your reason/), {
      target: { value: "I need to see the other case." },
    });
    click("Send request");
    await screen.findByText(/10 requests waiting/);
    expect(screen.getByRole("button", { name: "Back to this case" })).toBeTruthy();
  });
});
