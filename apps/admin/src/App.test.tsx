import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { App } from "./App";
import { createApi } from "./api";

const DISTRICT = "22222222-2222-4222-8222-222222222222";

function json(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function person(role: string, district: string | null = DISTRICT) {
  return {
    user_id: "00000000-0000-4000-8000-000000000009",
    username: "u",
    display_name: "Charu Singh",
    role,
    district_id: district,
    active: true,
  };
}

type MeAnswer = () => Response;

function setup(me: MeAnswer) {
  const fetchImpl = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/auth/login")) {
      return Promise.resolve(
        json(200, {
          access_token: "a",
          refresh_token: "r",
          token_type: "Bearer",
          expires_in: 900,
          refresh_expires_in: 28800,
          user: person("ADMIN"),
        }),
      );
    }
    if (url.endsWith("/auth/logout")) return Promise.resolve(json(204));
    if (url.endsWith("/auth/refresh"))
      return Promise.resolve(json(401, { code: "UNAUTHENTICATED" }));
    if (url.endsWith("/jurisdictions")) {
      return Promise.resolve(
        json(200, {
          items: [
            {
              state_id: "s",
              name: "Rivergate State",
              districts: [{ district_id: DISTRICT, name: "Rivergate" }],
            },
          ],
        }),
      );
    }
    if (url.endsWith("/me")) return Promise.resolve(me());
    return Promise.resolve(json(404));
  }) as unknown as typeof fetch;
  return createApi({ baseUrl: "http://api.test", fetch: fetchImpl });
}

async function signIn(api: ReturnType<typeof setup>, lang: "en" | "hi" = "en") {
  render(<App api={api} lang={lang} />);
  fireEvent.change(screen.getByLabelText(/user ID|यूज़र आईडी/), { target: { value: "charu" } });
  fireEvent.change(screen.getByLabelText(/^(Your password|आपका पासवर्ड)/), {
    target: { value: "pw" },
  });
  fireEvent.click(
    screen.getAllByRole("button", { name: /^(Sign in|साइन इन करें)$/ }).at(0) as HTMLElement,
  );
}

const navLabels = () =>
  within(screen.getByRole("navigation", { name: /Main sections/i }))
    .getAllByRole("button")
    .map((b) => b.textContent);

beforeEach(() => window.history.replaceState(null, "", "/"));
afterEach(cleanup);

test("signed out: the sign-in page with a title, a language switch and admin density", () => {
  render(<App api={setup(() => json(200, person("ADMIN")))} />);
  expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("TraceX Admin");
  expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("Sign in");
  expect(document.querySelector('[data-app="admin"]')).not.toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "हिन्दी" }));
  expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("ट्रेसएक्स एडमिन");
  expect(document.documentElement.lang).toBe("hi");
});

test("empty fields are named, not sent", async () => {
  const api = setup(() => json(200, person("ADMIN")));
  render(<App api={api} />);
  fireEvent.click(screen.getAllByRole("button", { name: "Sign in" }).at(0) as HTMLElement);
  expect(await screen.findByText("Please write your user ID and your password.")).toBeTruthy();
});

test("a wrong password shows the plain sign-in message", async () => {
  const fetchImpl = vi.fn(() =>
    Promise.resolve(json(401, { code: "UNAUTHENTICATED" })),
  ) as unknown as typeof fetch;
  render(<App api={createApi({ baseUrl: "http://api.test", fetch: fetchImpl })} />);
  fireEvent.change(screen.getByLabelText(/user ID/), { target: { value: "x" } });
  fireEvent.change(screen.getByLabelText(/^Your password/), { target: { value: "y" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Sign in" }).at(0) as HTMLElement);
  expect(await screen.findByText(/We could not sign you in/)).toBeTruthy();
});

test("ADMIN sees upload and matching but no review queue or graph; header shows name and area", async () => {
  await signIn(setup(() => json(200, person("ADMIN", null))));
  await screen.findByRole("navigation", { name: /Main sections/i });
  expect(navLabels()).toEqual([
    "Upload",
    "Matching",
    "Approvals",
    "Users and roles",
    "Audit log",
    "Thresholds",
  ]);
  expect(screen.getByText("Charu Singh")).toBeTruthy();
  expect(screen.getByText("All areas")).toBeTruthy();
  expect(window.location.pathname).toBe("/upload");
});

test("SENIOR sees approvals and the review queue, not upload", async () => {
  await signIn(setup(() => json(200, person("SENIOR", null))));
  await screen.findByRole("navigation", { name: /Main sections/i });
  const labels = navLabels();
  expect(labels).toContain("Approvals");
  expect(labels).toContain("Review queue");
  expect(labels).not.toContain("Upload");
});

test("SUPERVISOR shows the area name and no system pages", async () => {
  await signIn(setup(() => json(200, person("SUPERVISOR"))));
  await screen.findByRole("navigation", { name: /Main sections/i });
  expect(navLabels()).toEqual(["Review queue", "Approvals", "Audit log", "Network graph"]);
  // The Area filter on the review queue lists the same name, so look in the header.
  expect(await within(screen.getByRole("banner")).findByText("Rivergate")).toBeTruthy();
  expect(window.location.pathname).toBe("/review");
});

test("a role outside the panel gets one line and a way to sign out", async () => {
  await signIn(setup(() => json(200, person("JUNIOR"))));
  expect(await screen.findByText(/This panel is for supervisors/)).toBeTruthy();
  expect(screen.queryByRole("navigation", { name: /Main sections/i })).toBeNull();
  expect(screen.getByRole("button", { name: "Sign out" })).toBeTruthy();
});

test("a page the role may not open goes to its first page", async () => {
  window.history.replaceState(null, "", "/upload");
  await signIn(setup(() => json(200, person("SUPERVISOR"))));
  await screen.findByRole("navigation", { name: /Main sections/i });
  expect(window.location.pathname).toBe("/review");
});

test("a supervisor has no users page: the address goes to the first page", async () => {
  window.history.replaceState(null, "", "/users");
  const api = setup(() => json(200, person("SUPERVISOR")));
  await signIn(api);
  await screen.findByRole("navigation", { name: /Main sections/i });
  expect(window.location.pathname).toBe("/review");
  expect(screen.queryByRole("button", { name: "Users and roles" })).toBeNull();
  expect(screen.queryByText("Users and roles", { selector: "h2" })).toBeNull();
});

test("menu clicks use browser history: Back returns to the earlier page", async () => {
  window.history.replaceState(null, "", "/review");
  await signIn(setup(() => json(200, person("SUPERVISOR"))));
  await screen.findByRole("navigation", { name: /Main sections/i });
  fireEvent.click(screen.getByRole("button", { name: "Audit log" }));
  expect(window.location.pathname).toBe("/audit");
  expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Audit log");
  window.history.back();
  await waitFor(() => expect(window.location.pathname).toBe("/review"));
  await waitFor(() =>
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Review queue"),
  );
});

test("language switch redraws the menu in Hindi without leaving the page", async () => {
  await signIn(setup(() => json(200, person("SUPERVISOR"))));
  await screen.findByRole("navigation", { name: /Main sections|मुख्य/i });
  const before = window.location.pathname;
  fireEvent.click(screen.getByRole("button", { name: "हिन्दी" }));
  expect(window.location.pathname).toBe(before);
  expect(screen.getByRole("button", { name: "जाँच की कतार" })).toBeTruthy();
});

test.each([
  [503, "The system is paused for a safety check. Try again later."],
  [404, "We could not find this. Go back and try again."],
  [403, "You do not have access to do this."],
  [500, "Something went wrong on our side. Nothing was changed. Try again."],
])("when /me answers %s the shell shows the mapped message and a retry", async (status, text) => {
  await signIn(setup(() => json(status, { code: "X" })));
  expect(await screen.findByText(text)).toBeTruthy();
  expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
});

test("a session the server ends returns to sign-in with a message", async () => {
  await signIn(setup(() => json(401, { code: "UNAUTHENTICATED" })));
  expect(await screen.findByText("Your session has ended. Please sign in again.")).toBeTruthy();
  expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("Sign in");
});

test("sign out returns to the sign-in page", async () => {
  const api = setup(() => json(200, person("SUPERVISOR")));
  await signIn(api);
  await screen.findByRole("navigation", { name: /Main sections/i });
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  await waitFor(() =>
    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("Sign in"),
  );
  expect(api.session.accessToken()).toBeUndefined();
  expect(screen.queryByText("Your session has ended. Please sign in again.")).toBeNull();
});

test("a 429 on sign-in is the lockout text, not the plain busy text", async () => {
  const fetchImpl = vi.fn(() =>
    Promise.resolve(json(429, { code: "RATE_LIMITED" })),
  ) as unknown as typeof fetch;
  render(<App api={createApi({ baseUrl: "http://api.test", fetch: fetchImpl })} />);
  fireEvent.change(screen.getByLabelText(/user ID/), { target: { value: "x" } });
  fireEvent.change(screen.getByLabelText(/^Your password/), { target: { value: "y" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Sign in" }).at(0) as HTMLElement);
  expect(
    await screen.findByText("Too many tries. Please wait 15 minutes, then try again."),
  ).toBeTruthy();
});

test("ADMIN who opens /graph directly sees a plain not-available page and no graph or search call", async () => {
  window.history.replaceState(null, "", "/graph");
  const urls: string[] = [];
  const fetchImpl = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    urls.push(url);
    if (url.endsWith("/auth/login")) {
      return Promise.resolve(
        json(200, {
          access_token: "a",
          refresh_token: "r",
          token_type: "Bearer",
          expires_in: 900,
          refresh_expires_in: 28800,
          user: person("ADMIN", null),
        }),
      );
    }
    if (url.endsWith("/me")) return Promise.resolve(json(200, person("ADMIN", null)));
    return Promise.resolve(json(404));
  }) as unknown as typeof fetch;
  await signIn(createApi({ baseUrl: "http://api.test", fetch: fetchImpl }));
  expect(await screen.findByText("The network is for officers with case access.")).toBeTruthy();
  expect(window.location.pathname).toBe("/graph");
  expect(navLabels()).not.toContain("Network graph");
  expect(urls.filter((u) => /\/(search|entities|links|stubs)/.test(u))).toEqual([]);
});
