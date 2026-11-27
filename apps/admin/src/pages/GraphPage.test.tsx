import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import type { Role } from "../nav";
import { fakeApi, json, renderPage, type Routes } from "../testing";
import { GraphPage } from "./GraphPage";

afterEach(cleanup);

const E1 = "e1111111-1111-4111-8111-111111111111";
const E2 = "e2222222-2222-4222-8222-222222222222";
const E3 = "e3333333-3333-4333-8333-333333333333";
const LINK = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const LINK2 = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const STUB = "5757575a-5757-4757-8757-575757575757";

function entity(id: string, type: string, value: string, caseId: string) {
  return {
    entity_id: id,
    case_id: caseId,
    type,
    display_value: value,
    masked: false,
    link_count: 1,
    has_hidden_connection: false,
    needs_review: false,
    via_grant: false,
  };
}

const node = (id: string, type: string, value: string, caseId: string, distance = 0) => ({
  entity: entity(id, type, value, caseId),
  degree: 1,
  distance,
});

function graph(over: Record<string, unknown> = {}) {
  return {
    center_entity_id: E1,
    nodes: [
      node(E1, "PHONE", "9000014471", "c1"),
      node(E2, "PHONE", "9000014471", "c2", 1),
      node(E3, "PERSON", "Meena Rao", "c3", 1),
    ],
    edges: [
      { link_id: LINK, state: "AUTO", band: "HIGH", from_entity_id: E1, to_entity_id: E2 },
      { link_id: LINK2, state: "SUGGESTED", band: "MEDIUM", from_entity_id: E1, to_entity_id: E3 },
    ],
    stubs: [
      {
        redacted: true,
        stub_id: STUB,
        near_entity_id: E1,
        connection_exists: true,
        access_request: { status: "NONE", requested_at: null },
        message_key: "access.stub.connection_exists",
      },
    ],
    truncated: false,
    ...over,
  };
}

const found = json(200, {
  items: [entity(E1, "PHONE", "9000014471", "c1")],
  next_cursor: null,
  total: 1,
});

function routes(over: Routes = {}): Routes {
  return {
    "GET /search/entities": found,
    [`GET /entities/${E1}/graph`]: json(200, graph()),
    ...over,
  };
}

function open(r: Routes, role: Role = "SENIOR", lang: "en" | "hi" = "en") {
  const made = fakeApi(r);
  renderPage(<GraphPage api={made.api} lang={lang} role={role} />, lang);
  return made;
}

async function showNetwork() {
  fireEvent.change(screen.getByLabelText("Find a person, phone number, account or vehicle"), {
    target: { value: "9000014471" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await screen.findByRole("group", { name: /nodes|items|links/i });
}

const nodeEl = (id: string) => document.querySelector(`[data-node="${id}"]`) as SVGGElement;
const apiCalls = (calls: { path: string }[]) =>
  calls.filter(
    (c) =>
      c.path.startsWith("/search") || c.path.startsWith("/entities") || c.path.startsWith("/links"),
  );

test("an administrator gets a plain not-available state and no graph or search call", async () => {
  const { calls } = open(routes(), "ADMIN");
  expect(screen.getByText("The network is for officers with case access.")).toBeTruthy();
  expect(screen.queryByLabelText("Find a person, phone number, account or vehicle")).toBeNull();
  await new Promise((r) => setTimeout(r, 20));
  expect(calls).toEqual([]);
});

test("searching then showing the network draws nodes, a legend and calls only search and graph", async () => {
  const { calls } = open(routes());
  await showNetwork();
  expect(nodeEl(E1)).not.toBeNull();
  expect(nodeEl(E2)).not.toBeNull();
  expect(nodeEl(E3)).not.toBeNull();
  expect(screen.getByRole("region", { name: "How to read the picture" })).toBeTruthy();
  const paths = apiCalls(calls).map((c) => c.path);
  expect(paths).toEqual(["/search/entities", `/entities/${E1}/graph`]);
  const graphCall = calls.find((c) => c.path === `/entities/${E1}/graph`);
  expect(graphCall).toBeTruthy();
});

test("a hidden case is a lock card with only 'Another police area': no label, id or far-side edge, and no stub read", async () => {
  const { calls } = open(routes());
  await showNetwork();
  const stub = nodeEl("stub-1");
  expect(stub).not.toBeNull();
  expect(stub.getAttribute("data-shape")).toBe("restricted");
  expect(stub.getAttribute("aria-label")).toBe("Another police area");
  expect(stub.textContent).toBe("Another police area");
  expect(document.body.innerHTML).not.toContain(STUB);
  const dashed = document.querySelectorAll('[data-edge][data-style="dashed-restricted"]');
  expect(dashed).toHaveLength(1);
  expect(calls.some((c) => c.path.startsWith("/stubs"))).toBe(false);
});

test("opening a stub shows the restricted card only", async () => {
  const { calls } = open(routes());
  await showNetwork();
  fireEvent.click(nodeEl("stub-1"));
  const card = await screen.findByRole("region", { name: "Another police area", hidden: false });
  expect(within(card).getByText("Also appears in a case in another police area.")).toBeTruthy();
  expect(screen.queryByRole("button", { name: /See why/ })).toBeNull();
  expect(calls.some((c) => c.path.startsWith("/stubs") || c.path.startsWith("/links"))).toBe(false);
});

test("Tab order reaches every node and Enter opens the selected node's panel", async () => {
  open(routes());
  await showNetwork();
  const nodes = document.querySelectorAll("[data-node]");
  expect(nodes).toHaveLength(4);
  for (const n of nodes) {
    expect(n.getAttribute("tabindex")).toBe("0");
    expect(n.getAttribute("role")).toBe("button");
  }
  (nodeEl(E3) as unknown as HTMLElement).focus();
  expect(document.activeElement).toBe(nodeEl(E3));
  fireEvent.keyDown(nodeEl(E3), { key: "Enter" });
  const panel = await screen.findByRole("region", { name: "Selected item" });
  expect(within(panel).getByText("Meena Rao")).toBeTruthy();
});

test("the list toggle shows every node, edge and stub as text", async () => {
  open(routes());
  await showNetwork();
  fireEvent.click(screen.getByRole("button", { name: "Show as list" }));
  const items = screen.getByRole("table", { name: "Items in the network" });
  // header row + 3 entities + 1 stub
  expect(within(items).getAllByRole("row")).toHaveLength(5);
  expect(within(items).getByText("Meena Rao")).toBeTruthy();
  expect(within(items).getAllByText("Another police area").length).toBeGreaterThan(0);
  const links = screen.getByRole("table", { name: "Links in the network" });
  // header + 2 links + 1 restricted link
  expect(within(links).getAllByRole("row")).toHaveLength(4);
  expect(screen.getByRole("button", { name: "Show as picture" })).toBeTruthy();
});

test("truncated shows the exact cap message", async () => {
  open(routes({ [`GET /entities/${E1}/graph`]: json(200, graph({ truncated: true })) }));
  await showNetwork();
  expect(
    screen.getByText("Showing the 150 closest. Narrow the search to see others."),
  ).toBeTruthy();
});

test("no truncation message when the answer is complete", async () => {
  open(routes());
  await showNetwork();
  expect(screen.queryByText(/Showing the 150 closest/)).toBeNull();
});

test("search with no match says so and calls no graph", async () => {
  const { calls } = open(
    routes({ "GET /search/entities": json(200, { items: [], next_cursor: null, total: 0 }) }),
  );
  fireEvent.change(screen.getByLabelText("Find a person, phone number, account or vehicle"), {
    target: { value: "zzzz" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  expect(
    await screen.findByText("Nothing found. Check the spelling or try fewer words."),
  ).toBeTruthy();
  expect(calls.some((c) => c.path.endsWith("/graph"))).toBe(false);
});

test("several matches are listed and the network opens on choice", async () => {
  const { calls } = open(
    routes({
      "GET /search/entities": json(200, {
        items: [entity(E1, "PHONE", "9000014471", "c1"), entity(E3, "PERSON", "Meena Rao", "c3")],
        next_cursor: null,
        total: 2,
      }),
    }),
  );
  fireEvent.change(screen.getByLabelText("Find a person, phone number, account or vehicle"), {
    target: { value: "900" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  const buttons = await screen.findAllByRole("button", { name: /Show network/ });
  expect(buttons).toHaveLength(2);
  expect(calls.some((c) => c.path.endsWith("/graph"))).toBe(false);
  fireEvent.click(buttons[0] as HTMLElement);
  await waitFor(() => expect(nodeEl(E1)).not.toBeNull());
});

test("a 404 from the graph is a plain not-found, never the restricted card", async () => {
  open(routes({ [`GET /entities/${E1}/graph`]: json(404, { code: "NOT_FOUND" }) }));
  fireEvent.change(screen.getByLabelText("Find a person, phone number, account or vehicle"), {
    target: { value: "9000014471" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  expect(await screen.findByText("We could not find this. Go back and try again.")).toBeTruthy();
  expect(screen.queryByText("Another police area")).toBeNull();
});

test("a 503 shows the safety pause message", async () => {
  open(routes({ [`GET /entities/${E1}/graph`]: json(503, { code: "SAFETY_PAUSE" }) }));
  fireEvent.change(screen.getByLabelText("Find a person, phone number, account or vehicle"), {
    target: { value: "9000014471" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  expect(await screen.findByText(/paused/i)).toBeTruthy();
});

test("opening a link from the panel loads its explanation then; no per-edge read on load", async () => {
  const { calls } = open(
    routes({
      [`GET /links/${LINK}`]: json(404),
      [`GET /links/${LINK}/explanation`]: json(404),
    }),
  );
  await showNetwork();
  expect(calls.filter((c) => c.path.startsWith("/links"))).toEqual([]);
  fireEvent.click(nodeEl(E1));
  const panel = await screen.findByRole("region", { name: "Selected item" });
  expect(calls.filter((c) => c.path.startsWith("/links"))).toEqual([]);
  fireEvent.click(within(panel).getAllByRole("button", { name: /See why/ })[0] as HTMLElement);
  await waitFor(() =>
    expect(calls.some((c) => c.path === `/links/${LINK}` || c.path === `/links/${LINK2}`)).toBe(
      true,
    ),
  );
  expect(calls.some((c) => c.path.endsWith("/explanation"))).toBe(true);
});

test("Hindi renders the page strings", async () => {
  open(routes(), "SENIOR", "hi");
  expect(screen.getByLabelText("व्यक्ति, फ़ोन नंबर, खाता या वाहन खोजें")).toBeTruthy();
});
