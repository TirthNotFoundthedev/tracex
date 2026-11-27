import { render } from "@testing-library/react";
import { UiProvider } from "@tracex/ui";
import type { ReactElement } from "react";
import { vi } from "vitest";

import { createApi, type AdminApi } from "./api";

export const DISTRICT = "22222222-2222-4222-8222-222222222222";

export function json(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export type Answer = Response | ((request: { url: string; init: RequestInit }) => Response);
/** Keys look like "GET /thresholds". Anything not listed answers 404. */
export type Routes = Record<string, Answer>;

/** An API over a fake `fetch`. Pages can call at once; the test needs no sign-in. */
export function fakeApi(routes: Routes) {
  const calls: { method: string; path: string; init: RequestInit }[] = [];
  const fetchImpl = vi.fn((input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input));
    const method = init.method ?? "GET";
    calls.push({ method, path: url.pathname, init });
    const answer = routes[`${method} ${url.pathname}`];
    if (!answer) return Promise.resolve(json(404));
    return Promise.resolve(
      typeof answer === "function" ? answer({ url: url.toString(), init }) : answer.clone(),
    );
  }) as unknown as typeof fetch;
  const api: AdminApi = createApi({ baseUrl: "http://api.test", fetch: fetchImpl });
  return { api, calls, fetchImpl };
}

export function renderPage(ui: ReactElement, lang: "en" | "hi" = "en") {
  return render(
    <UiProvider app="admin" lang={lang}>
      {ui}
    </UiProvider>,
  );
}
