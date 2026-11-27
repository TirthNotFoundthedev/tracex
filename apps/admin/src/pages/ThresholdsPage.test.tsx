import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { fakeApi, json, renderPage, type Routes } from "../testing";
import { ThresholdsPage } from "./ThresholdsPage";

afterEach(cleanup);

const current = json(200, {
  high_min: 80,
  medium_min: 45,
  thresholds_version: 3,
  effective_at: "2026-03-01T00:00:00Z",
});
const none = json(200, { items: [], next_cursor: null });

function change(over: Record<string, unknown> = {}) {
  return {
    change_id: "44444444-4444-4444-8444-444444444444",
    kind: "THRESHOLDS",
    state: "PENDING",
    old_value: { high_min: 80, medium_min: 45 },
    new_value: { high_min: 85, medium_min: 50 },
    proposer: { user_id: "u", display_name: "Hari" },
    change_hash: "b".repeat(64),
    proposed_at: "2026-03-12T14:05:00Z",
    ...over,
  };
}

function page(over: Routes = {}) {
  return fakeApi({ "GET /thresholds": current, "GET /pending-changes": none, ...over });
}

const strong = () => screen.getByLabelText("Strong match starts at") as HTMLInputElement;
const possible = () => screen.getByLabelText("Possible match starts at") as HTMLInputElement;
const save = () => screen.getByRole("button", { name: "Save settings" });

async function admin(over: Routes = {}) {
  const fake = page(over);
  renderPage(<ThresholdsPage api={fake.api} lang="en" role="ADMIN" />);
  await waitFor(() => expect(strong().value).toBe("80"));
  return fake;
}

test("shows the current numbers on the 0 to 100 scale with the allowed ranges and three zones", async () => {
  await admin();
  expect(possible().value).toBe("45");
  expect(screen.getByText("Allowed: from 70 to 100.")).toBeTruthy();
  expect(screen.getByText("Allowed: from 30 up to 70.")).toBeTruthy();
  expect(screen.getByText("No link made")).toBeTruthy();
  expect(screen.getByText("Please check")).toBeTruthy();
  expect(screen.getByText("Linked automatically")).toBeTruthy();
});

test("there is no test run or preview of what would change", async () => {
  await admin();
  expect(screen.queryByRole("button", { name: /preview|test|dry/i })).toBeNull();
});

test("an administrator saving sends a proposal and sees Sent for approval with the old numbers kept", async () => {
  const { calls } = await admin({
    "POST /pending-changes": json(201, change()),
  });
  fireEvent.change(strong(), { target: { value: "85" } });
  fireEvent.change(possible(), { target: { value: "50" } });
  fireEvent.click(save());
  expect(
    await screen.findByText(
      "Sent for approval. Nothing changes until a senior officer approves it.",
    ),
  ).toBeTruthy();
  const post = calls.find((c) => c.method === "POST");
  expect(post?.path).toBe("/pending-changes");
  expect(JSON.parse(String(post?.init.body))).toEqual({
    kind: "THRESHOLDS",
    new_value: { high_min: 85, medium_min: 50 },
  });
  expect(screen.getByText("Change waiting for approval")).toBeTruthy();
  expect(screen.getByText("The current numbers stay in use until then.")).toBeTruthy();
  expect(screen.getByText("85")).toBeTruthy();
});

test("a proposal already waiting is shown when the page opens", async () => {
  const fake = page({
    "GET /pending-changes": json(200, { items: [change()], next_cursor: null }),
  });
  renderPage(<ThresholdsPage api={fake.api} lang="en" role="ADMIN" />);
  expect(await screen.findByText("Change waiting for approval")).toBeTruthy();
  expect(screen.getByText("The current numbers stay in use until then.")).toBeTruthy();
});

test.each([
  ["69", "50", "Please enter a number from 70 to 100."],
  ["101", "50", "Please enter a number from 70 to 100."],
  ["", "50", "Please enter a number from 70 to 100."],
  ["80", "29", "Please enter a number from 30 to 70."],
  ["80", "71", "Please enter a number from 30 to 70."],
  ["90", "81", "Please enter a number from 30 to 80."],
])("strong %s and possible %s is refused in the browser: %s", async (high, medium, message) => {
  const { calls } = await admin();
  fireEvent.change(strong(), { target: { value: high } });
  fireEvent.change(possible(), { target: { value: medium } });
  fireEvent.click(save());
  expect(await screen.findByText(message)).toBeTruthy();
  expect(calls.some((c) => c.method === "POST")).toBe(false);
});

test("a 422 puts the message beside the field the API names", async () => {
  await admin({
    "POST /pending-changes": json(422, {
      code: "VALIDATION_ERROR",
      field_errors: [{ field: "medium_min", code: "out_of_range" }],
    }),
  });
  fireEvent.click(save());
  expect(await screen.findByText("Please enter a number from 30 to 70.")).toBeTruthy();
  expect(possible().getAttribute("aria-invalid")).toBe("true");
});

test.each([
  [403, undefined, "You do not have access to do this."],
  [404, undefined, "We could not find this. Go back and try again."],
  [409, { code: "RUN_IN_PROGRESS" }, "A matching run is in progress. Try again in a few minutes."],
  [409, { code: "CONFLICT" }, "Someone changed this while you were looking. Please open it again."],
  [429, undefined, "Too many tries. Please wait 15 minutes, then try again."],
  [503, undefined, "The system is paused for a safety check. Try again later."],
])(
  "a %s answer to Save shows the shared message and keeps the typed numbers",
  async (status, body, text) => {
    await admin({ "POST /pending-changes": json(status, body) });
    fireEvent.change(strong(), { target: { value: "85" } });
    fireEvent.click(save());
    expect(await screen.findByText(text)).toBeTruthy();
    expect(strong().value).toBe("85");
    expect(screen.queryByText(/Sent for approval/)).toBeNull();
  },
);

test("a senior officer sees the numbers but no fields to edit and no Save", async () => {
  const fake = page();
  renderPage(<ThresholdsPage api={fake.api} lang="en" role="SENIOR" />);
  expect(await screen.findByText("Only an administrator can propose new numbers.")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Save settings" })).toBeNull();
  expect(screen.queryByLabelText("Strong match starts at")).toBeNull();
  expect(screen.getByText("80")).toBeTruthy();
});

test("a failed load shows the shared failure and Try again loads again", async () => {
  let n = 0;
  const fake = page({ "GET /thresholds": () => (n++ === 0 ? json(503) : current.clone()) });
  renderPage(<ThresholdsPage api={fake.api} lang="en" role="ADMIN" />);
  expect(
    await screen.findByText("The system is paused for a safety check. Try again later."),
  ).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  await waitFor(() => expect(strong().value).toBe("80"));
});

test("the page reads in Hindi", async () => {
  const fake = page();
  renderPage(<ThresholdsPage api={fake.api} lang="hi" role="ADMIN" />);
  expect(await screen.findByRole("button", { name: "सेटिंग सहेजें" })).toBeTruthy();
});
