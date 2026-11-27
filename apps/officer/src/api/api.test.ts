import { describe, expect, test, vi } from "vitest";

import { createClient } from "./client";
import { buildUrl } from "./http";
import { createSession } from "./session";

const BASE = "http://api.test";

const user = {
  id: "00000000-0000-4000-8000-000000000001",
  username: "bharat",
  display_name: "Bharat",
  role: "INVESTIGATOR",
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
  await session.signIn("bharat", "pw");
  const client = createClient({ baseUrl: BASE, session, fetch: fetchImpl });
  return { fetchImpl, session, client };
}

describe("error mapping", () => {
  const table: [string, number, unknown, unknown][] = [
    [
      "404 unknown, hidden or withdrawn id",
      404,
      { code: "NOT_FOUND", message_key: "error.not_found" },
      { kind: "notFound" },
    ],
    [
      "403 role does not allow",
      403,
      { code: "FORBIDDEN", message_key: "error.forbidden" },
      { kind: "notAllowed" },
    ],
    [
      "409 run in progress (D49)",
      409,
      { code: "RUN_IN_PROGRESS", message_key: "error.run_in_progress" },
      { kind: "tryAgainShortly" },
    ],
    [
      "409 other conflict",
      409,
      { code: "INVALID_TRANSITION", message_key: "error.invalid_transition" },
      { kind: "conflict", code: "INVALID_TRANSITION" },
    ],
    ["409 with unreadable body", 409, undefined, { kind: "conflict", code: undefined }],
    [
      "422 with field errors",
      422,
      {
        code: "VALIDATION_FAILED",
        message_key: "error.validation_failed",
        field_errors: [{ field: "reason", code: "too_short" }],
      },
      { kind: "invalid", fieldErrors: [{ field: "reason", code: "too_short" }] },
    ],
    [
      "429 throttled",
      429,
      { code: "TOO_MANY_REQUESTS", message_key: "error.too_many_requests" },
      { kind: "tooManyAttempts" },
    ],
    [
      "500 server problem",
      500,
      { code: "INTERNAL", message_key: "error.internal" },
      { kind: "serverError" },
    ],
    [
      "503 safety pause",
      503,
      { code: "NOT_READY", message_key: "error.not_ready" },
      { kind: "safetyPause" },
    ],
    ["503 with any other body", 503, { code: "SOMETHING_ELSE" }, { kind: "safetyPause" }],
    ["503 with no body", 503, undefined, { kind: "safetyPause" }],
  ];

  test.each(table)("%s", async (_name, status, body, expected) => {
    const { client } = await signedIn(() => json(status, body));
    expect(await client.getLink("l-1")).toEqual(expected);
  });

  test("200 returns the typed body", async () => {
    const { client } = await signedIn(() => json(200, { id: "l-1" }));
    expect(await client.getLink("l-1")).toEqual({ kind: "ok", data: { id: "l-1" } });
  });

  test("a network failure becomes networkError", async () => {
    const { client, fetchImpl } = await signedIn(() => json(200, {}));
    fetchImpl.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    expect(await client.listCases()).toEqual({ kind: "networkError" });
  });

  test("a 404 on entity, link, explanation and stub ids is notFound, never restricted", async () => {
    const { client } = await signedIn(() =>
      json(404, { code: "NOT_FOUND", message_key: "error.not_found" }),
    );
    const results = [
      await client.getEntity("e-1"),
      await client.getLink("l-1"),
      await client.getLinkExplanation("l-1"),
      await client.getStub("s-1"),
    ];
    for (const result of results) expect(result).toStrictEqual({ kind: "notFound" });
  });

  test("a stub from the API is ok data, not an error kind", async () => {
    const stub = { id: "s-1" };
    const { client } = await signedIn(() => json(200, stub));
    expect(await client.getStub("s-1")).toEqual({ kind: "ok", data: stub });
  });
});

describe("requests", () => {
  test("sends the bearer token, JSON body and encoded path", async () => {
    const { client, fetchImpl } = await signedIn(() => json(200, {}));
    await client.rejectLink("a/b", { reason: "Different people" });
    const [url, init] = fetchImpl.mock.calls.at(-1) as [string, RequestInit];
    expect(url).toBe(`${BASE}/links/a%2Fb/reject`);
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer access-1");
    expect(init.body).toBe(JSON.stringify({ reason: "Different people" }));
  });

  test("buildUrl drops undefined query values and trailing slashes", () => {
    expect(buildUrl("http://x/", "/cases", { case_number: "24", limit: undefined })).toBe(
      "http://x/cases?case_number=24",
    );
  });
});

describe("refresh rotation", () => {
  test("concurrent 401s cause one refresh and every call is retried with the new token", async () => {
    let refreshes = 0;
    const { client, fetchImpl } = await signedIn((url, init) => {
      if (url.endsWith("/auth/refresh")) {
        refreshes += 1;
        expect(JSON.parse(String(init.body))).toEqual({ refresh_token: "refresh-1" });
        return json(200, pair(2));
      }
      const auth = (init.headers as Record<string, string>).Authorization;
      return auth === "Bearer access-2"
        ? json(200, { ok: true })
        : json(401, { code: "UNAUTHENTICATED", message_key: "error.unauthenticated" });
    });
    const results = await Promise.all([client.listCases(), client.getMe(), client.listLinks()]);
    expect(refreshes).toBe(1);
    expect(results.every((r) => r.kind === "ok")).toBe(true);
    expect(fetchImpl.mock.calls.filter(([u]) => String(u).endsWith("/auth/refresh"))).toHaveLength(
      1,
    );
  });

  test("the next refresh uses the rotated refresh token", async () => {
    const seen: string[] = [];
    let valid = 2;
    const { client } = await signedIn((url, init) => {
      if (url.endsWith("/auth/refresh")) {
        seen.push(JSON.parse(String(init.body)).refresh_token);
        return json(200, pair(valid));
      }
      const auth = (init.headers as Record<string, string>).Authorization;
      return auth === `Bearer access-${valid}` ? json(200, {}) : json(401);
    });
    expect((await client.getMe()).kind).toBe("ok");
    valid = 3;
    expect((await client.getMe()).kind).toBe("ok");
    expect(seen).toEqual(["refresh-1", "refresh-2"]);
  });

  test("a refused refresh signs out and reports sessionExpired", async () => {
    const { client, session } = await signedIn((url) =>
      url.endsWith("/auth/refresh") ? json(401) : json(401),
    );
    expect(await client.listCases()).toEqual({ kind: "sessionExpired" });
    expect(session.state()).toBeUndefined();
    expect(session.accessToken()).toBeUndefined();
  });

  test("a second 401 after a good refresh is sessionExpired, not a loop", async () => {
    const { client, fetchImpl } = await signedIn((url) =>
      url.endsWith("/auth/refresh") ? json(200, pair(2)) : json(401),
    );
    expect(await client.getMe()).toEqual({ kind: "sessionExpired" });
    expect(fetchImpl.mock.calls.filter(([u]) => String(u).endsWith("/auth/refresh"))).toHaveLength(
      1,
    );
  });

  test.each([
    [503, { kind: "safetyPause" }],
    [429, { kind: "tooManyAttempts" }],
  ])("a refresh answered %i keeps the session and reports %j", async (status, expected) => {
    const { client, session } = await signedIn((url) =>
      url.endsWith("/auth/refresh") ? json(status) : json(401),
    );
    expect(await client.listCases()).toEqual(expected);
    expect(session.state()).toBeDefined();
    expect(session.accessToken()).toBe("access-1");
  });

  test("a network error during refresh keeps the session", async () => {
    const { client, session, fetchImpl } = await signedIn(() => json(401));
    fetchImpl.mockImplementation(((input: RequestInfo | URL) =>
      String(input).endsWith("/auth/refresh")
        ? Promise.reject(new TypeError("offline"))
        : Promise.resolve(json(401))) as typeof fetch);
    expect(await client.getMe()).toEqual({ kind: "networkError" });
    expect(session.state()).toBeDefined();
  });

  test("a call made while signed out is sessionExpired without a refresh", async () => {
    const fetchImpl = fakeFetch(() => json(401));
    const session = createSession({ baseUrl: BASE, fetch: fetchImpl });
    const client = createClient({ baseUrl: BASE, session, fetch: fetchImpl });
    expect(await client.getMe()).toEqual({ kind: "sessionExpired" });
    expect(fetchImpl.mock.calls.some(([u]) => String(u).endsWith("/auth/refresh"))).toBe(false);
  });
});

describe("session", () => {
  test("sign in keeps the user and the end of the 8 hour lifetime", async () => {
    const fetchImpl = fakeFetch(() => json(200, pair(1)));
    const session = createSession({ baseUrl: BASE, fetch: fetchImpl, now: () => 1_000 });
    expect(await session.signIn("bharat", "pw")).toEqual({ kind: "ok", data: user });
    expect(session.state()).toEqual({ user, endsAt: 1_000 + 28_800_000 });
  });

  test.each([
    [401, { kind: "badCredentials" }],
    [429, { kind: "tooManyAttempts" }],
    [422, { kind: "invalid", fieldErrors: [] }],
  ])("sign in answered %i gives %j and no session", async (status, expected) => {
    const session = createSession({ baseUrl: BASE, fetch: fakeFetch(() => json(status)) });
    expect(await session.signIn("bharat", "wrong")).toEqual(expected);
    expect(session.state()).toBeUndefined();
  });

  test("sign out clears state at once and tells the server", async () => {
    const { session, fetchImpl } = await signedIn(() => json(204));
    const seen = vi.fn();
    session.subscribe(seen);
    await session.signOut();
    expect(session.accessToken()).toBeUndefined();
    expect(session.state()).toBeUndefined();
    expect(seen).toHaveBeenLastCalledWith(undefined);
    const [url, init] = fetchImpl.mock.calls.at(-1) as [string, RequestInit];
    expect(url).toBe(`${BASE}/auth/logout`);
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer access-1");
  });

  test("sign out still clears state when the server cannot be reached", async () => {
    const { session, fetchImpl } = await signedIn(() => json(204));
    fetchImpl.mockRejectedValueOnce(new TypeError("offline"));
    await session.signOut();
    expect(session.state()).toBeUndefined();
  });

  test("tokens are never written to browser storage or cookies", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    await signedIn(() => json(200, {}));
    expect(setItem).not.toHaveBeenCalled();
    expect(document.cookie).toBe("");
    setItem.mockRestore();
  });
});

describe("access request reason", () => {
  const send = (reason: string) => {
    return signedIn(() => json(201, { id: "r-1" })).then(async ({ client, fetchImpl }) => ({
      result: await client.createAccessRequest({ stub_id: "s-1", reason } as never),
      fetchImpl,
    }));
  };
  const posted = (fetchImpl: ReturnType<typeof fakeFetch>) =>
    fetchImpl.mock.calls.filter(([url]) => String(url).endsWith("/access-requests"));

  test.each([
    [9, "too_short"],
    [501, "too_long"],
    [0, "too_short"],
  ])("%i characters is refused before any request", async (length, code) => {
    const { result, fetchImpl } = await send("a".repeat(length));
    expect(result).toEqual({ kind: "invalid", fieldErrors: [{ field: "reason", code }] });
    expect(posted(fetchImpl)).toHaveLength(0);
  });

  test.each([10, 500])("%i characters is sent", async (length) => {
    const { result, fetchImpl } = await send("a".repeat(length));
    expect(result.kind).toBe("ok");
    expect(posted(fetchImpl)).toHaveLength(1);
  });

  test("spaces are trimmed before counting and sending", async () => {
    expect((await send("   123456789   ")).result.kind).toBe("invalid");
    const { fetchImpl } = await send("  " + "b".repeat(10) + "  ");
    const body = JSON.parse(String((posted(fetchImpl)[0]?.[1] as RequestInit).body));
    expect(body.reason).toBe("b".repeat(10));
  });
});
