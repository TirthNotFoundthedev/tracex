import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { fakeApi, json, renderPage, type Routes } from "../testing";
import { MatchingPage } from "./MatchingPage";

afterEach(cleanup);

const RUN = "33333333-3333-4333-8333-333333333333";

function run(over: Record<string, unknown> = {}) {
  return {
    run_id: RUN,
    status: "SUCCEEDED",
    started_at: "2026-03-12T14:00:00Z",
    finished_at: "2026-03-12T14:05:00Z",
    triggered_by: "00000000-0000-4000-8000-000000000009",
    ruleset_version: "1",
    thresholds_version: 1,
    oversized_block_count: 0,
    input_batch_count: 2,
    auto_created: 6,
    suggested_created: 14,
    ...over,
  };
}

const totals = json(200, { waiting: 14, rejected: 1, undone: 0, auto: 6, confirmed: 3 });

function page(over: Routes = {}) {
  return fakeApi({
    "GET /matching/runs": json(200, { items: [run()], next_cursor: null }),
    "GET /stats/links": totals,
    ...over,
  });
}

test("shows the last run with the strong and possible counts and the system totals", async () => {
  const { api } = page();
  renderPage(<MatchingPage api={api} lang="en" />);
  expect(await screen.findByText(/^Last run: .*2026.*Found 6 strong, 14 possible\.$/)).toBeTruthy();
  expect(screen.getByText("Links now: 6 strong, 14 possible, 3 confirmed.")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Start matching" })).toBeTruthy();
});

test("never shows a low-band or per-pair count", async () => {
  const { api } = page();
  const { container } = renderPage(<MatchingPage api={api} lang="en" />);
  await screen.findByText(/Last run/);
  expect(container.textContent).not.toMatch(/low|pair|oversized|block/i);
});

test("with no run yet it says so", async () => {
  const { api } = page({ "GET /matching/runs": json(200, { items: [], next_cursor: null }) });
  renderPage(<MatchingPage api={api} lang="en" />);
  expect(await screen.findByText("No matching has been run yet.")).toBeTruthy();
});

test("starting a run shows that it is running and that it cannot be stopped, with no stop button", async () => {
  const { api, calls } = page({
    "POST /matching/runs": json(202, run({ status: "RUNNING", finished_at: null })),
    [`GET /matching/runs/${RUN}`]: json(200, run({ status: "RUNNING", finished_at: null })),
  });
  renderPage(<MatchingPage api={api} lang="en" pollMs={5} />);
  fireEvent.click(await screen.findByRole("button", { name: "Start matching" }));
  expect(await screen.findByText("A run cannot be stopped. Please wait.")).toBeTruthy();
  expect(screen.getByText("Matching is running...")).toBeTruthy();
  expect(screen.queryByRole("button", { name: /stop|cancel/i })).toBeNull();
  expect(
    (screen.queryByRole("button", { name: "Start matching" }) as HTMLButtonElement | null)
      ?.disabled ?? true,
  ).toBe(true);
  expect(calls.filter((c) => c.method === "POST" && c.path === "/matching/runs")).toHaveLength(1);
});

test("when the run finishes it says how many possible matches need review", async () => {
  let polls = 0;
  const { api } = page({
    "POST /matching/runs": json(202, run({ status: "RUNNING", finished_at: null })),
    [`GET /matching/runs/${RUN}`]: () =>
      polls++ < 1
        ? json(200, run({ status: "RUNNING", finished_at: null }))
        : json(200, run({ suggested_created: 9 })),
  });
  renderPage(<MatchingPage api={api} lang="en" pollMs={5} />);
  fireEvent.click(await screen.findByRole("button", { name: "Start matching" }));
  expect(
    await screen.findByText(
      "Matching finished. 9 possible matches are waiting for officers to check.",
    ),
  ).toBeTruthy();
  expect(screen.queryByText("A run cannot be stopped. Please wait.")).toBeNull();
  expect(screen.getByRole("button", { name: "Start matching" })).toBeTruthy();
});

test("a run that failed says nothing was changed and offers a new start", async () => {
  const { api } = page({
    "POST /matching/runs": json(202, run({ status: "RUNNING", finished_at: null })),
    [`GET /matching/runs/${RUN}`]: json(200, run({ status: "FAILED", error_code: "ENGINE_ERROR" })),
  });
  renderPage(<MatchingPage api={api} lang="en" pollMs={5} />);
  fireEvent.click(await screen.findByRole("button", { name: "Start matching" }));
  expect(
    await screen.findByText("The run did not finish. Nothing was changed. Try again."),
  ).toBeTruthy();
  expect(screen.getByRole("button", { name: "Start matching" })).toBeTruthy();
});

test("a run already going when the page opens shows the running state", async () => {
  const { api } = page({
    "GET /matching/runs": json(200, {
      items: [run({ status: "RUNNING", finished_at: null })],
      next_cursor: null,
    }),
    [`GET /matching/runs/${RUN}`]: json(200, run({ status: "RUNNING", finished_at: null })),
  });
  renderPage(<MatchingPage api={api} lang="en" pollMs={5} />);
  expect(await screen.findByText("A run cannot be stopped. Please wait.")).toBeTruthy();
});

test.each([
  [409, { code: "RUN_IN_PROGRESS" }, "A matching run is in progress. Try again in a few minutes."],
  [403, undefined, "You do not have access to do this."],
  [404, undefined, "We could not find this. Go back and try again."],
  [429, undefined, "The system is busy. Please wait a moment, then try again."],
  [503, undefined, "The system is paused for a safety check. Try again later."],
  [
    422,
    { code: "VALIDATION_ERROR", field_errors: [] },
    "Something is missing. Check the fields marked below.",
  ],
])("a %s answer to Start shows the shared message", async (status, body, text) => {
  const { api } = page({ "POST /matching/runs": json(status, body) });
  renderPage(<MatchingPage api={api} lang="en" pollMs={5} />);
  fireEvent.click(await screen.findByRole("button", { name: "Start matching" }));
  expect(await screen.findByText(text)).toBeTruthy();
  await waitFor(() => expect(screen.getByRole("button", { name: "Start matching" })).toBeTruthy());
});

test("a failed first load shows the shared failure and Try again loads again", async () => {
  let n = 0;
  const { api } = page({
    "GET /matching/runs": () =>
      n++ === 0 ? json(503) : json(200, { items: [run()], next_cursor: null }),
  });
  renderPage(<MatchingPage api={api} lang="en" />);
  expect(
    await screen.findByText("The system is paused for a safety check. Try again later."),
  ).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText(/Found 6 strong, 14 possible/)).toBeTruthy();
});

test("a 409 on Start shows the shared message and then the running state", async () => {
  let started = false;
  const { api } = page({
    "GET /matching/runs": () =>
      json(200, {
        items: [started ? run({ status: "RUNNING", finished_at: null }) : run()],
        next_cursor: null,
      }),
    "POST /matching/runs": () => {
      started = true;
      return json(409, { code: "RUN_IN_PROGRESS" });
    },
    [`GET /matching/runs/${RUN}`]: json(200, run({ status: "RUNNING", finished_at: null })),
  });
  renderPage(<MatchingPage api={api} lang="en" pollMs={5} />);
  fireEvent.click(await screen.findByRole("button", { name: "Start matching" }));
  expect(
    await screen.findByText("A matching run is in progress. Try again in a few minutes."),
  ).toBeTruthy();
  expect(await screen.findByText("A run cannot be stopped. Please wait.")).toBeTruthy();
});

test("a run that lasts long shows the slow line", async () => {
  const { api } = page({
    "GET /matching/runs": json(200, {
      items: [run({ status: "RUNNING", finished_at: null })],
      next_cursor: null,
    }),
    [`GET /matching/runs/${RUN}`]: json(200, run({ status: "RUNNING", finished_at: null })),
  });
  renderPage(<MatchingPage api={api} lang="en" pollMs={5} slowAfterMs={30} />);
  expect(await screen.findByText("A run cannot be stopped. Please wait.")).toBeTruthy();
  expect(screen.queryByText("This is taking long. Please wait or try again.")).toBeNull();
  expect(await screen.findByText("This is taking long. Please wait or try again.")).toBeTruthy();
});

test("the page reads in Hindi, including the running line", async () => {
  const { api } = page({
    "GET /matching/runs": json(200, {
      items: [run({ status: "RUNNING", finished_at: null })],
      next_cursor: null,
    }),
    [`GET /matching/runs/${RUN}`]: json(200, run({ status: "RUNNING", finished_at: null })),
  });
  renderPage(<MatchingPage api={api} lang="hi" pollMs={5} />);
  expect(await screen.findByText("मिलान चल रहा है...")).toBeTruthy();
  expect(screen.getByText("चलते मिलान को रोका नहीं जा सकता। कृपया प्रतीक्षा करें।")).toBeTruthy();
});
