import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { createApi } from "../api";
import { messageKeyFor } from "../api/resultKeys";
import { en } from "../i18n/en";
import { hi } from "../i18n/hi";
import { t } from "../i18n";
import type { Role } from "../nav";
import { fakeApi, json, renderPage, type Routes } from "../testing";
import { AuditPage } from "./AuditPage";

afterEach(cleanup);

const MEENA = "c0000000-0000-4000-8000-000000000002";
const ASHA = "c0000000-0000-4000-8000-000000000003";
const D1 = "b0000000-0000-4000-8000-000000000001";

function user(id: string, name: string, role: string) {
  return {
    user_id: id,
    username: name.toLowerCase().split(" ")[0],
    display_name: name,
    role,
    district_id: role === "SENIOR" ? null : D1,
    coverage: null,
    active: true,
  };
}

function row(over: Record<string, unknown> = {}) {
  return {
    row_ref: "ref-opaque-1",
    occurred_at: "2026-03-12T14:05:00Z",
    event_type: "LINK_CONFIRMED",
    outcome: "SUCCESS",
    actor: { kind: "USER", user_id: ASHA, role: "JUNIOR", district_id: D1 },
    refs: [{ case_id: "C-101", district_id: D1 }],
    target_type: "LINK",
    target_id: "e0000000-0000-4000-8000-0000000000aa",
    ...over,
  };
}

const auditPage = (items: unknown[], next: string | null = null) =>
  json(200, { items, next_cursor: next, result_count: items.length });

function setup(role: Role, over: Routes = {}) {
  const fake = fakeApi({
    "GET /audit": auditPage([
      row(),
      row({
        row_ref: "ref-2",
        event_type: "ACCESS_DENIED",
        outcome: "DENIED",
        target_type: "CASE",
        refs: [],
      }),
      row({
        row_ref: "ref-3",
        event_type: "MATCHING_RUN_STARTED",
        actor: { kind: "SYSTEM" },
        refs: [],
        target_type: "RUN",
      }),
    ]),
    "GET /users": json(200, {
      items: [user(MEENA, "Meena Rao", "SENIOR"), user(ASHA, "Asha Devi", "JUNIOR")],
      next_cursor: null,
      total: 2,
    }),
    "POST /audit/verify": json(200, { result: "OK" }),
    ...over,
  });
  renderPage(<AuditPage api={fake.api} lang="en" role={role} />);
  return fake;
}

const calls = (fake: { calls: { method: string; path: string }[] }) =>
  fake.calls.map((c) => `${c.method} ${c.path}`).sort();

// ------------------------------------------------------------------ read-only

test("the log is read-only: the line is there, and no export, download, edit or delete control exists", async () => {
  setup("SENIOR");
  await screen.findByText("Asha Devi");
  expect(screen.getByRole("heading", { name: "Activity log" })).toBeTruthy();
  expect(screen.getByText("This log cannot be changed.")).toBeTruthy();
  expect(
    screen.queryAllByRole("button", {
      name: /export|download|delete|remove|edit|save|print|copy/i,
    }),
  ).toEqual([]);
  expect(document.querySelector("a[download], a[href]")).toBeNull();
  // Rows have no Open button and no row actions at all.
  expect(screen.queryByRole("button", { name: "Open" })).toBeNull();
});

test("the table shows time, person, what they did, case and item, in words", async () => {
  setup("SENIOR");
  await screen.findByText("Asha Devi");
  for (const header of ["Time", "Person", "What they did", "Case", "Item"]) {
    expect(screen.getByRole("columnheader", { name: header })).toBeTruthy();
  }
  const first = screen.getByText("Confirmed").closest("tr") as HTMLElement;
  expect(within(first).getByText("Asha Devi")).toBeTruthy();
  expect(within(first).getByText("C-101")).toBeTruthy();
  expect(within(first).getByText("Link")).toBeTruthy();
  const denied = screen.getByText(/Was refused access/).closest("tr") as HTMLElement;
  expect(within(denied).getByText(/Not allowed/)).toBeTruthy();
  const system = screen.getByText("Started a matching run").closest("tr") as HTMLElement;
  expect(within(system).getByText("The system")).toBeTruthy();
});

test("no sequence number, hash, row reference, or role code is shown", async () => {
  setup("SENIOR", {
    "GET /audit": auditPage([row({ seq: 41, first_bad_seq: 9, row_hash: "deadbeef" })]),
  });
  await screen.findByText("Asha Devi");
  const text = document.body.textContent ?? "";
  expect(text).not.toMatch(/\b(41|deadbeef|ref-opaque-1)\b/);
  expect(text).not.toMatch(/\b(JUNIOR|INVESTIGATOR|SUPERVISOR|SENIOR|ADMIN)\b/);
});

test("a person the list cannot name shows the role in words, never the code", async () => {
  setup("SUPERVISOR", {
    "GET /audit": auditPage([
      row({ actor: { kind: "USER", user_id: "zzz", role: "INVESTIGATOR", district_id: D1 } }),
    ]),
  });
  expect(await screen.findByText("Investigating officer")).toBeTruthy();
  expect(document.body.textContent).not.toMatch(/\bINVESTIGATOR\b/);
});

test("an administrator sees no case content: no Case column, and a case id in a row is not drawn", async () => {
  setup("ADMIN");
  await screen.findByText("Started a matching run");
  expect(screen.queryByRole("columnheader", { name: "Case" })).toBeNull();
  expect(document.body.textContent).not.toContain("C-101");
});

test("empty", async () => {
  setup("SENIOR", { "GET /audit": auditPage([]) });
  expect(await screen.findByText("No activity to show.")).toBeTruthy();
  expect(screen.getByText("This log cannot be changed.")).toBeTruthy();
});

// ------------------------------------------------------------------ calls

test.each([
  ["SENIOR", ["GET /audit", "GET /users"]],
  ["ADMIN", ["GET /audit", "GET /users"]],
  ["SUPERVISOR", ["GET /audit"]],
] as const)(
  "%s: rendering the log makes exactly these calls and no per-row reads",
  async (role, expected) => {
    const fake = setup(role);
    await screen.findByText(/Started a matching run/);
    expect(calls(fake)).toEqual([...expected].sort());
    expect(fake.calls.some((c) => c.method === "POST")).toBe(false);
  },
);

test("Show more reads the next page with the cursor and adds the rows", async () => {
  const urls: string[] = [];
  setup("SENIOR", {
    "GET /audit": ({ url }) => {
      urls.push(url);
      const cursor = new URL(url).searchParams.get("cursor");
      return cursor
        ? auditPage([row({ row_ref: "r9", event_type: "DATA_UPLOADED", target_type: "BATCH" })])
        : auditPage([row()], "CURSOR-1");
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "Show more" }));
  expect(await screen.findByText("Uploaded")).toBeTruthy();
  expect(screen.getByText("Confirmed")).toBeTruthy();
  expect(new URL(urls[1] as string).searchParams.get("cursor")).toBe("CURSOR-1");
});

// ------------------------------------------------------------------ filters

const query = (url: string) => new URL(url).searchParams;

test("filters: date range, person and action in words; nothing is read until Show is pressed", async () => {
  const urls: string[] = [];
  const fake = setup("SENIOR", {
    "GET /audit": ({ url }) => {
      urls.push(url);
      return auditPage([row()]);
    },
  });
  await screen.findByText("Asha Devi");
  fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2026-03-01" } });
  fireEvent.change(screen.getByLabelText("To date"), { target: { value: "2026-03-31" } });
  fireEvent.change(screen.getByLabelText("Person"), { target: { value: ASHA } });
  fireEvent.change(screen.getByLabelText("What they did"), { target: { value: "LINK_CONFIRMED" } });
  expect(urls).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "Show" }));
  await waitFor(() => expect(urls).toHaveLength(2));
  const q = query(urls[1] as string);
  expect(q.get("actor_user_id")).toBe(ASHA);
  expect(q.get("event_type")).toBe("LINK_CONFIRMED");
  expect(new Date(q.get("occurred_from") as string).getTime()).toBe(
    new Date("2026-03-01T00:00:00").getTime(),
  );
  expect(new Date(q.get("occurred_to") as string).getTime()).toBe(
    new Date("2026-03-31T23:59:59.999").getTime(),
  );
  // The names come once; Show does not read users again.
  expect(fake.calls.filter((c) => c.path === "/users")).toHaveLength(1);
});

test("the action filter speaks in words and holds the six the design names", async () => {
  setup("SENIOR");
  await screen.findByText("Asha Devi");
  const select = screen.getByLabelText("What they did");
  const labels = within(select)
    .getAllByRole("option")
    .map((o) => o.textContent);
  for (const word of [
    "Looked at",
    "Confirmed",
    "Rejected",
    "Asked for access",
    "Approved access",
    "Uploaded",
  ]) {
    expect(labels).toContain(word);
  }
  expect(labels.join(" ")).not.toMatch(/[A-Z]{3,}_[A-Z]+/);
});

test("a supervisor has no person filter (the user list is for senior officers and administrators)", async () => {
  setup("SUPERVISOR");
  await screen.findByText(/Started a matching run/);
  expect(screen.queryByLabelText("Person")).toBeNull();
  expect(screen.getByLabelText("From date")).toBeTruthy();
});

test("a start date after the end date is not sent", async () => {
  const fake = setup("SENIOR");
  await screen.findByText("Asha Devi");
  fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2026-04-01" } });
  fireEvent.change(screen.getByLabelText("To date"), { target: { value: "2026-03-01" } });
  fireEvent.click(screen.getByRole("button", { name: "Show" }));
  expect(await screen.findByText(t("audit.error.dates", "en"))).toBeTruthy();
  expect(fake.calls.filter((c) => c.path === "/audit")).toHaveLength(1);
});

// ------------------------------------------------------------------ verify (D45)

test("a senior officer can check the log; OK says it is intact and shows no number", async () => {
  const fake = setup("SENIOR");
  await screen.findByText("Asha Devi");
  fireEvent.click(screen.getByRole("button", { name: "Check the log is intact" }));
  expect(await screen.findByText("The log is intact.")).toBeTruthy();
  expect(fake.calls.filter((c) => c.method === "POST").map((c) => c.path)).toEqual([
    "/audit/verify",
  ]);
});

test("BROKEN gives a senior officer the first bad entry number, the only number in the screen", async () => {
  setup("SENIOR", {
    "POST /audit/verify": json(200, { result: "BROKEN", first_bad_seq: 17 }),
  });
  await screen.findByText("Asha Devi");
  fireEvent.click(screen.getByRole("button", { name: "Check the log is intact" }));
  expect(await screen.findByText("The log has a problem. Tell the system owner now.")).toBeTruthy();
  expect(screen.getByText("First problem at entry 17.")).toBeTruthy();
});

test("a supervisor and an administrator have no check button", async () => {
  setup("SUPERVISOR");
  await screen.findByText(/Started a matching run/);
  expect(screen.queryByRole("button", { name: "Check the log is intact" })).toBeNull();
  cleanup();
  setup("ADMIN");
  await screen.findByText(/Started a matching run/);
  expect(screen.queryByRole("button", { name: "Check the log is intact" })).toBeNull();
});

test("a failed check goes through the shared failure message", async () => {
  setup("SENIOR", { "POST /audit/verify": json(503) });
  await screen.findByText("Asha Devi");
  fireEvent.click(screen.getByRole("button", { name: "Check the log is intact" }));
  expect(await screen.findByText(t("error.safetyPause", "en"))).toBeTruthy();
});

// ------------------------------------------------------------------ failures

test.each([
  [401, "sessionExpired"],
  [403, "notAllowed"],
  [404, "notFound"],
  [409, "conflict"],
  [422, "invalid"],
  [429, "tooManyAttempts"],
  [503, "safetyPause"],
  [500, "serverError"],
] as const)("a %s when the log loads shows the shared message", async (status, kind) => {
  setup("SENIOR", { "GET /audit": json(status, { code: "X" }) });
  expect(await screen.findByText(t(messageKeyFor({ kind } as never), "en"))).toBeTruthy();
});

test("a network failure shows the no-connection message with Try again", async () => {
  const failing = (() => Promise.reject(new TypeError("offline"))) as unknown as typeof fetch;
  const api = createApi({ baseUrl: "http://api.test", fetch: failing });
  renderPage(<AuditPage api={api} lang="en" role="SENIOR" />);
  expect(await screen.findAllByText(t("state.noConnection", "en"))).not.toHaveLength(0);
  expect(screen.getAllByRole("button", { name: "Try again" }).length).toBeGreaterThan(0);
});

test("if the names do not load, the log still shows and the failure is told", async () => {
  setup("SENIOR", { "GET /users": json(503) });
  expect(await screen.findByText(t("error.safetyPause", "en"))).toBeTruthy();
  expect(await screen.findByText("Confirmed")).toBeTruthy();
  expect(screen.queryByLabelText("Person")).toBeNull();
});

test("a 422 on a filter shows the shared message and keeps the filters", async () => {
  // Only a read that carries a date fails.
  setup("SENIOR", {
    "GET /audit": ({ url }) =>
      query(url).get("occurred_from")
        ? json(422, { code: "VALIDATION_FAILED" })
        : auditPage([row()]),
  });
  await screen.findByText("Asha Devi");
  fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2026-03-01" } });
  fireEvent.click(screen.getByRole("button", { name: "Show" }));
  expect(await screen.findByText(t("state.somethingMissing", "en"))).toBeTruthy();
  expect((screen.getByLabelText("From date") as HTMLInputElement).value).toBe("2026-03-01");
});

// ------------------------------------------------------------------ Hindi

test("Hindi: every event word the screen can show has a Hindi text", () => {
  const eventKeys = Object.keys(en).filter((key) => key.startsWith("audit.event."));
  expect(eventKeys.length).toBeGreaterThan(40);
  for (const key of eventKeys)
    expect((hi as Record<string, string>)[key]?.length).toBeGreaterThan(0);
});

test("Hindi: the page draws in Hindi", async () => {
  const fake = fakeApi({
    "GET /audit": auditPage([row()]),
    "GET /users": json(200, { items: [], next_cursor: null, total: 0 }),
  });
  renderPage(<AuditPage api={fake.api} lang="hi" role="SENIOR" />, "hi");
  expect(await screen.findByText(t("audit.cannotChange", "hi"))).toBeTruthy();
  expect(await screen.findByText(t("audit.action.confirmed", "hi"))).toBeTruthy();
});
