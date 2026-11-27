import { describe, expect, test, vi } from "vitest";

import { createClient } from "./client";
import { buildUrl } from "./http";
import { createSession } from "./session";

const BASE = "http://api.test";

const user = {
  user_id: "00000000-0000-4000-8000-000000000001",
  username: "charu",
  display_name: "Charu",
  role: "SUPERVISOR",
  active: true,
} as never;

function pair(n: number) {
  return {
    access_token: `access-${n}`,
    refresh_token: `refresh-${n}`,
    token_type: "Bearer",
    expires_in: 900,
    refresh_expires_in: 28800,
    user,
  };
}

function json(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

function fakeFetch(handler: Handler) {
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(String(input), init ?? {})),
  ) as unknown as typeof fetch & ReturnType<typeof vi.fn>;
}

async function signedIn(handler: Handler) {
  const fetchImpl = fakeFetch((url, init) =>
    url.endsWith("/auth/login") ? json(200, pair(1)) : handler(url, init),
  );
  const session = createSession({ baseUrl: BASE, fetch: fetchImpl });
  await session.signIn("charu", "pw");
  const client = createClient({ baseUrl: BASE, session, fetch: fetchImpl });
  return { fetchImpl, session, client };
}

function lastCall(fetchImpl: ReturnType<typeof fakeFetch>) {
  const calls = fetchImpl.mock.calls;
  const [url, init] = calls[calls.length - 1] as [string, RequestInit];
  return { url, init, headers: init.headers as Record<string, string> };
}

const ID = "11111111-1111-4111-8111-111111111111";

describe("error mapping", () => {
  const table: [string, number, unknown, unknown][] = [
    [
      "404 is a plain not-found (D65)",
      404,
      { code: "NOT_FOUND", message_key: "error.not_found" },
      { kind: "notFound" },
    ],
    ["403 is not allowed", 403, { code: "FORBIDDEN", message_key: "x" }, { kind: "notAllowed" }],
    [
      "409 run in progress",
      409,
      { code: "RUN_IN_PROGRESS", message_key: "x" },
      { kind: "tryAgainShortly" },
    ],
    [
      "409 other conflict keeps the code",
      409,
      { code: "CHANGE_HASH_STALE", message_key: "x" },
      { kind: "conflict", code: "CHANGE_HASH_STALE" },
    ],
    ["409 unreadable body", 409, undefined, { kind: "conflict", code: undefined }],
    [
      "422 with field errors",
      422,
      {
        code: "VALIDATION_FAILED",
        message_key: "x",
        field_errors: [{ field: "reason", code: "r" }],
      },
      { kind: "invalid", fieldErrors: [{ field: "reason", code: "r" }] },
    ],
    [
      "422 without field errors",
      422,
      { code: "VALIDATION_FAILED" },
      { kind: "invalid", fieldErrors: [] },
    ],
    ["503 is the safety pause", 503, { code: "NOT_READY" }, { kind: "safetyPause" }],
    ["503 with any body", 503, undefined, { kind: "safetyPause" }],
    ["429 too many attempts", 429, undefined, { kind: "tooManyAttempts" }],
    ["500 server problem", 500, { code: "INTERNAL" }, { kind: "serverError" }],
  ];

  test.each(table)("%s", async (_name, status, body, expected) => {
    const { client } = await signedIn(() => json(status, body));
    expect(await client.getMe()).toEqual(expected);
  });

  test("a network failure is a network error", async () => {
    const { client } = await signedIn(() => {
      throw new TypeError("offline");
    });
    expect(await client.getMe()).toEqual({ kind: "networkError" });
  });

  test("a 200 with a broken body is a server problem, not a crash", async () => {
    const { client } = await signedIn(() => new Response("not json", { status: 200 }));
    expect(await client.getMe()).toEqual({ kind: "serverError" });
  });
});

describe("tokens and refresh", () => {
  test("sends the bearer token and no cookie", async () => {
    const { client, fetchImpl } = await signedIn(() => json(200, { ok: 1 }));
    await client.getMe();
    const { headers, init } = lastCall(fetchImpl);
    expect(headers.Authorization).toBe("Bearer access-1");
    expect(init.credentials).toBeUndefined();
  });

  test("one refresh on 401, then the call is retried with the new token", async () => {
    let first = true;
    const { client, fetchImpl, session } = await signedIn((url, init) => {
      if (url.endsWith("/auth/refresh")) return json(200, pair(2));
      if (first) {
        first = false;
        return json(401, { code: "UNAUTHENTICATED" });
      }
      expect((init.headers as Record<string, string>).Authorization).toBe("Bearer access-2");
      return json(200, { ok: 1 });
    });
    expect(await client.getMe()).toEqual({ kind: "ok", data: { ok: 1 } });
    expect(fetchImpl.mock.calls.filter(([u]) => String(u).endsWith("/auth/refresh"))).toHaveLength(
      1,
    );
    expect(session.accessToken()).toBe("access-2");
  });

  test("a second 401 after a good refresh signs out", async () => {
    const { client, session } = await signedIn((url) =>
      url.endsWith("/auth/refresh") ? json(200, pair(2)) : json(401, { code: "UNAUTHENTICATED" }),
    );
    expect(await client.getMe()).toEqual({ kind: "sessionExpired" });
    expect(session.state()).toBeUndefined();
  });

  test("a refused refresh signs out", async () => {
    const { client, session } = await signedIn((url) =>
      url.endsWith("/auth/refresh") ? json(401) : json(401),
    );
    expect(await client.getMe()).toEqual({ kind: "sessionExpired" });
    expect(session.accessToken()).toBeUndefined();
  });

  test("tokens are never written to browser storage", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    await signedIn(() => json(200, {}));
    expect(setItem).not.toHaveBeenCalled();
    expect(document.cookie).toBe("");
    setItem.mockRestore();
  });
});

describe("session", () => {
  test("wrong password is its own result", async () => {
    const fetchImpl = fakeFetch(() => json(401, { code: "UNAUTHENTICATED" }));
    const session = createSession({ baseUrl: BASE, fetch: fetchImpl });
    expect(await session.signIn("x", "y")).toEqual({ kind: "badCredentials" });
  });

  test("sign out clears the session and tells the server", async () => {
    const { session, fetchImpl } = await signedIn(() => json(204));
    await session.signOut();
    expect(session.accessToken()).toBeUndefined();
    expect(lastCall(fetchImpl).url).toBe(`${BASE}/auth/logout`);
  });
});

describe("buildUrl", () => {
  test("drops undefined values and trims the base slash", () => {
    expect(buildUrl("http://a/", "/x", { a: 1, b: undefined, c: "z" })).toBe("http://a/x?a=1&c=z");
  });
});

interface Route {
  name: string;
  call: (c: Awaited<ReturnType<typeof signedIn>>["client"]) => Promise<unknown>;
  method: "GET" | "POST";
  path: string;
  query?: Record<string, string>;
  body?: unknown;
}

const hash = "a".repeat(64);

const routes: Route[] = [
  { name: "getMe", call: (c) => c.getMe(), method: "GET", path: "/me" },
  {
    name: "uploadFiles",
    call: (c) =>
      c.uploadFiles({
        case_number: "24/118",
        district_id: ID,
        files: [new File(["a"], "a.pdf")],
      }),
    method: "POST",
    path: "/uploads",
  },
  {
    name: "listUploads",
    call: (c) => c.listUploads({ limit: 20 }),
    method: "GET",
    path: "/uploads",
    query: { limit: "20" },
  },
  { name: "getUpload", call: (c) => c.getUpload(ID), method: "GET", path: `/uploads/${ID}` },
  {
    name: "startMatchingRun",
    call: (c) => c.startMatchingRun(),
    method: "POST",
    path: "/matching/runs",
  },
  {
    name: "listMatchingRuns",
    call: (c) => c.listMatchingRuns(),
    method: "GET",
    path: "/matching/runs",
  },
  {
    name: "getMatchingRun",
    call: (c) => c.getMatchingRun(ID),
    method: "GET",
    path: `/matching/runs/${ID}`,
  },
  {
    name: "listReviewQueue",
    call: (c) => c.listReviewQueue({ state: "REJECTED", waiting_days_min: 7 }),
    method: "GET",
    path: "/review-queue",
    query: { state: "REJECTED", waiting_days_min: "7" },
  },
  { name: "getLink", call: (c) => c.getLink(ID), method: "GET", path: `/links/${ID}` },
  {
    name: "getLinkExplanation",
    call: (c) => c.getLinkExplanation(ID),
    method: "GET",
    path: `/links/${ID}/explanation`,
  },
  {
    name: "confirmLink",
    call: (c) => c.confirmLink(ID),
    method: "POST",
    path: `/links/${ID}/confirm`,
    body: {},
  },
  {
    name: "rejectLink",
    call: (c) => c.rejectLink(ID, { reason: "  Different people.  " }),
    method: "POST",
    path: `/links/${ID}/reject`,
    body: { reason: "Different people." },
  },
  {
    name: "undoLink",
    call: (c) => c.undoLink(ID, { reason: "Wrong match" }),
    method: "POST",
    path: `/links/${ID}/undo`,
    body: { reason: "Wrong match" },
  },
  {
    name: "reopenLink",
    call: (c) => c.reopenLink(ID, { reason: "New evidence" }),
    method: "POST",
    path: `/links/${ID}/reopen`,
    body: { reason: "New evidence" },
  },
  {
    name: "listAccessRequests",
    call: (c) => c.listAccessRequests({ scope: "to_decide" }),
    method: "GET",
    path: "/access-requests",
    query: { scope: "to_decide" },
  },
  {
    name: "getAccessRequest",
    call: (c) => c.getAccessRequest(ID),
    method: "GET",
    path: `/access-requests/${ID}`,
  },
  {
    name: "approveAccessRequest",
    call: (c) => c.approveAccessRequest(ID, { duration_days: 30 }),
    method: "POST",
    path: `/access-requests/${ID}/approve`,
    body: { duration_days: 30 },
  },
  {
    name: "denyAccessRequest",
    call: (c) => c.denyAccessRequest(ID, { note: "  Not needed  " }),
    method: "POST",
    path: `/access-requests/${ID}/deny`,
    body: { note: "Not needed" },
  },
  {
    name: "listGrants",
    call: (c) => c.listGrants({ scope: "authority" }),
    method: "GET",
    path: "/grants",
    query: { scope: "authority" },
  },
  {
    name: "revokeGrant",
    call: (c) => c.revokeGrant(ID),
    method: "POST",
    path: `/grants/${ID}/revoke`,
  },
  {
    name: "listUsers",
    call: (c) => c.listUsers({ active: true }),
    method: "GET",
    path: "/users",
    query: { active: "true" },
  },
  { name: "getUser", call: (c) => c.getUser(ID), method: "GET", path: `/users/${ID}` },
  { name: "listRoles", call: (c) => c.listRoles(), method: "GET", path: "/roles" },
  {
    name: "listJurisdictions",
    call: (c) => c.listJurisdictions(),
    method: "GET",
    path: "/jurisdictions",
  },
  { name: "getThresholds", call: (c) => c.getThresholds(), method: "GET", path: "/thresholds" },
  {
    name: "proposeChange",
    call: (c) =>
      c.proposeChange({ kind: "THRESHOLDS", new_value: { high_min: 85, medium_min: 50 } } as never),
    method: "POST",
    path: "/pending-changes",
    body: { kind: "THRESHOLDS", new_value: { high_min: 85, medium_min: 50 } },
  },
  {
    name: "listPendingChanges",
    call: (c) => c.listPendingChanges({ state: "PENDING" }),
    method: "GET",
    path: "/pending-changes",
    query: { state: "PENDING" },
  },
  {
    name: "getPendingChange",
    call: (c) => c.getPendingChange(ID),
    method: "GET",
    path: `/pending-changes/${ID}`,
  },
  {
    name: "approveChange",
    call: (c) => c.approveChange(ID, { change_hash: hash }),
    method: "POST",
    path: `/pending-changes/${ID}/approve`,
    body: { change_hash: hash },
  },
  {
    name: "denyChange",
    call: (c) => c.denyChange(ID),
    method: "POST",
    path: `/pending-changes/${ID}/deny`,
  },
  {
    name: "listAudit",
    call: (c) => c.listAudit({ occurred_from: "2026-03-01T00:00:00Z", order: "desc" }),
    method: "GET",
    path: "/audit",
    query: { occurred_from: "2026-03-01T00:00:00Z", order: "desc" },
  },
  {
    name: "verifyAuditChain",
    call: (c) => c.verifyAuditChain(),
    method: "POST",
    path: "/audit/verify",
  },
  { name: "getLinkTotals", call: (c) => c.getLinkTotals(), method: "GET", path: "/stats/links" },
  {
    name: "searchEntities",
    call: (c) => c.searchEntities({ q: "Ravi" } as never),
    method: "GET",
    path: "/search/entities",
    query: { q: "Ravi" },
  },
  {
    name: "getEntityGraph",
    call: (c) => c.getEntityGraph(ID, { depth: 2 }),
    method: "GET",
    path: `/entities/${ID}/graph`,
    query: { depth: "2" },
  },
  {
    name: "getEntityCluster",
    call: (c) => c.getEntityCluster(ID),
    method: "GET",
    path: `/entities/${ID}/cluster`,
  },
  {
    name: "getEntityPaths",
    call: (c) => c.getEntityPaths(ID, { max_hops: 3 }),
    method: "GET",
    path: `/entities/${ID}/paths`,
    query: { max_hops: "3" },
  },
];

describe("typed functions", () => {
  test.each(routes)("$name uses the right method, path, query and body", async (route) => {
    const { client, fetchImpl } = await signedIn(() => json(200, { done: true }));
    const result = await route.call(client);
    expect(result).toEqual({ kind: "ok", data: { done: true } });
    const { url, init, headers } = lastCall(fetchImpl);
    const parsed = new URL(url);
    expect(init.method).toBe(route.method);
    expect(parsed.origin + parsed.pathname).toBe(`${BASE}${route.path}`);
    expect(Object.fromEntries(parsed.searchParams)).toEqual(route.query ?? {});
    if (route.name === "uploadFiles") {
      expect(init.body).toBeInstanceOf(FormData);
      expect(headers["Content-Type"]).toBeUndefined();
      const form = init.body as FormData;
      expect(form.get("case_number")).toBe("24/118");
      expect(form.get("district_id")).toBe(ID);
      expect(form.getAll("files")).toHaveLength(1);
    } else if (route.body === undefined) {
      expect(init.body).toBeUndefined();
    } else {
      expect(JSON.parse(init.body as string)).toEqual(route.body);
      expect(headers["Content-Type"]).toBe("application/json");
    }
  });

  test("ids are escaped in the path", async () => {
    const { client, fetchImpl } = await signedIn(() => json(200, {}));
    await client.getLink("a/b");
    expect(lastCall(fetchImpl).url).toBe(`${BASE}/links/a%2Fb`);
  });

  test("uploadFiles accepts 202", async () => {
    const { client } = await signedIn(() => json(202, { batches: [] }));
    expect(
      await client.uploadFiles({
        case_number: "1",
        district_id: ID,
        files: [new File(["a"], "a.txt")],
      }),
    ).toEqual({ kind: "ok", data: { batches: [] } });
  });

  test("a 204 gives ok with no data", async () => {
    const { client } = await signedIn(() => json(204));
    expect(await client.revokeGrant(ID)).toEqual({ kind: "ok", data: undefined });
  });
});

describe("reasons", () => {
  test.each(["rejectLink", "undoLink", "reopenLink"] as const)(
    "%s with a blank reason does not call the API",
    async (name) => {
      const { client, fetchImpl } = await signedIn(() => json(200, {}));
      const before = fetchImpl.mock.calls.length;
      const result = await client[name](ID, { reason: "   " });
      expect(result).toEqual({
        kind: "invalid",
        fieldErrors: [{ field: "reason", code: "required" }],
      });
      expect(fetchImpl.mock.calls.length).toBe(before);
    },
  );

  test.each(["rejectLink", "undoLink", "reopenLink"] as const)(
    "%s with a reason shorter than 3 or longer than 1000 characters does not call the API",
    async (name) => {
      const { client, fetchImpl } = await signedIn(() => json(200, {}));
      const before = fetchImpl.mock.calls.length;
      expect(await client[name](ID, { reason: " ab " })).toEqual({
        kind: "invalid",
        fieldErrors: [{ field: "reason", code: "too_short" }],
      });
      expect(await client[name](ID, { reason: "x".repeat(1001) })).toEqual({
        kind: "invalid",
        fieldErrors: [{ field: "reason", code: "too_long" }],
      });
      expect(fetchImpl.mock.calls.length).toBe(before);
    },
  );

  test.each(["rejectLink", "undoLink", "reopenLink"] as const)(
    "%s sends a reason of exactly 3 and exactly 1000 characters",
    async (name) => {
      const { client, fetchImpl } = await signedIn(() => json(200, {}));
      const before = fetchImpl.mock.calls.length;
      await client[name](ID, { reason: "abc" });
      await client[name](ID, { reason: "x".repeat(1000) });
      expect(fetchImpl.mock.calls.length).toBe(before + 2);
    },
  );

  test("denyChange and denyAccessRequest send no note when it is blank", async () => {
    const { client, fetchImpl } = await signedIn(() => json(200, {}));
    await client.denyAccessRequest(ID, { note: "  " });
    expect(JSON.parse(lastCall(fetchImpl).init.body as string)).toEqual({});
  });

  test("a too long refusal note is a field error and does not call the API", async () => {
    const { client, fetchImpl } = await signedIn(() => json(200, {}));
    const before = fetchImpl.mock.calls.length;
    const result = await client.denyAccessRequest(ID, { note: "x".repeat(201) });
    expect(result).toEqual({ kind: "invalid", fieldErrors: [{ field: "note", code: "too_long" }] });
    expect(fetchImpl.mock.calls.length).toBe(before);
  });
});

describe("run in progress on decisions and runs", () => {
  test.each([
    ["confirmLink", (c: Awaited<ReturnType<typeof signedIn>>["client"]) => c.confirmLink(ID)],
    [
      "reopenLink",
      (c: Awaited<ReturnType<typeof signedIn>>["client"]) =>
        c.reopenLink(ID, { reason: "Because" }),
    ],
    [
      "startMatchingRun",
      (c: Awaited<ReturnType<typeof signedIn>>["client"]) => c.startMatchingRun(),
    ],
  ])("%s 409 RUN_IN_PROGRESS", async (_name, call) => {
    const { client } = await signedIn(() => json(409, { code: "RUN_IN_PROGRESS" }));
    expect(await call(client)).toEqual({ kind: "tryAgainShortly" });
  });
});
