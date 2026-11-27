import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
  fireEvent.click(screen.getByRole("button", { name: "Show network" }));
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
  const graphCall = new URL(
    (calls.find((c) => c.path === `/entities/${E1}/graph`) as { url: string }).url,
  );
  expect(graphCall.searchParams.get("depth")).toBe("1");
  expect(graphCall.searchParams.get("limit")).toBe("150");
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

test("Tab moves focus from node to node and Enter opens the focused node's panel", async () => {
  const user = userEvent.setup();
  open(routes());
  await showNetwork();
  const seen: string[] = [];
  for (let i = 0; i < 14 && seen.length < 4; i++) {
    await user.tab();
    const id = (document.activeElement as HTMLElement | null)?.getAttribute("data-node");
    if (id) seen.push(id);
  }
  expect(seen).toHaveLength(4);
  expect(new Set(seen).size).toBe(4);
  expect(seen).toContain(E3);
  const last = seen[3] as string;
  await user.keyboard("{Enter}");
  const panel = await screen.findByRole("region", { name: "Selected item" });
  expect(nodeEl(last).getAttribute("aria-pressed")).toBe("true");
  expect(panel.textContent).not.toContain("Choose an item");
});

test("the list lists every node label, both ends of every edge, and each stub as only 'Another police area'", async () => {
  open(routes());
  await showNetwork();
  fireEvent.click(screen.getByRole("button", { name: "Show as list" }));
  const items = screen.getByRole("table", { name: "Items in the network" });
  const itemRows = within(items).getAllByRole("row").slice(1);
  expect(itemRows).toHaveLength(4);
  const cells = (row: HTMLElement) =>
    within(row)
      .getAllByRole("cell")
      .map((c) => c.textContent);
  const itemCells = itemRows.map(cells);
  expect(itemCells).toContainEqual(["Phone number", "9000014471"]);
  expect(itemCells.filter((c) => c[1] === "9000014471")).toHaveLength(2);
  expect(itemCells).toContainEqual(["Person", "Meena Rao"]);
  expect(itemCells).toContainEqual(["Another police area", "Another police area"]);
  const stubRow = itemRows.find((r) => cells(r)[0] === "Another police area") as HTMLElement;
  expect(stubRow.textContent).toBe("Another police areaAnother police area");
  expect(items.innerHTML).not.toContain(STUB);

  const links = screen.getByRole("table", { name: "Links in the network" });
  const linkCells = within(links).getAllByRole("row").slice(1).map(cells);
  expect(linkCells).toHaveLength(3);
  expect(linkCells.map((c) => [c[0], c[1]])).toEqual(
    expect.arrayContaining([
      ["9000014471", "9000014471"],
      ["9000014471", "Meena Rao"],
      ["9000014471", "Another police area"],
    ]),
  );
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
  fireEvent.click(screen.getByRole("button", { name: "Show network" }));
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
  fireEvent.click(screen.getByRole("button", { name: "Show network" }));
  const buttons = await screen.findAllByRole("button", { name: "Show this network" });
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
  fireEvent.click(screen.getByRole("button", { name: "Show network" }));
  expect(await screen.findByText("We could not find this. Go back and try again.")).toBeTruthy();
  expect(screen.queryByText("Another police area")).toBeNull();
});

test("a 503 shows the safety pause message", async () => {
  open(routes({ [`GET /entities/${E1}/graph`]: json(503, { code: "SAFETY_PAUSE" }) }));
  fireEvent.change(screen.getByLabelText("Find a person, phone number, account or vehicle"), {
    target: { value: "9000014471" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Show network" }));
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

const E4 = "e4444444-4444-4444-8444-444444444444";
const E5 = "e5555555-5555-4555-8555-555555555555";
const LINK_C = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const LINK_R = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
const LINK_U = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";

function stateGraph() {
  return graph({
    nodes: [
      node(E1, "PHONE", "9000014471", "c1"),
      node(E2, "PHONE", "9000014472", "c2", 1),
      node(E3, "PERSON", "Meena Rao", "c3", 1),
      node(E4, "PERSON", "Rejected Person", "c4", 1),
      node(E5, "PERSON", "Undone Person", "c5", 1),
    ],
    edges: [
      { link_id: LINK, state: "AUTO", band: "HIGH", from_entity_id: E1, to_entity_id: E2 },
      { link_id: LINK_C, state: "CONFIRMED", band: "HIGH", from_entity_id: E1, to_entity_id: E3 },
      { link_id: LINK_R, state: "REJECTED", band: "LOW", from_entity_id: E1, to_entity_id: E4 },
      { link_id: LINK_U, state: "UNDONE", band: "LOW", from_entity_id: E1, to_entity_id: E5 },
    ],
    stubs: [],
  });
}

test("a CONFIRMED link is drawn strong and listed; REJECTED and UNDONE links are in no picture, list or panel", async () => {
  open(routes({ [`GET /entities/${E1}/graph`]: json(200, stateGraph()) }));
  await showNetwork();
  const edgeIds = [...document.querySelectorAll("[data-edge]")].map((e) =>
    e.getAttribute("data-edge"),
  );
  expect(edgeIds.sort()).toEqual([LINK, LINK_C].sort());
  const confirmed = document.querySelector(`[data-edge="${LINK_C}"]`) as Element;
  expect(confirmed.getAttribute("data-style")).toBe("solid-heavy");

  fireEvent.click(nodeEl(E1));
  const panel = await screen.findByRole("region", { name: "Selected item" });
  expect(within(panel).getAllByRole("button", { name: /See why/ })).toHaveLength(2);
  expect(panel.textContent).not.toContain("Rejected Person");
  expect(panel.textContent).not.toContain("Undone Person");

  fireEvent.click(screen.getByRole("button", { name: "Show as list" }));
  const links = screen.getByRole("table", { name: "Links in the network" });
  expect(within(links).getAllByRole("row")).toHaveLength(3);
  expect(links.textContent).toContain("Meena Rao");
  expect(links.textContent).toContain("Confirmed by an officer");
  expect(links.textContent).not.toContain("Rejected Person");
  expect(links.textContent).not.toContain("Undone Person");
});

test("masked phone and account values show exactly as the API sends them", async () => {
  open(
    routes({
      [`GET /entities/${E1}/graph`]: json(
        200,
        graph({
          nodes: [
            {
              entity: { ...entity(E1, "PHONE", "98xxxx1234", "c1"), masked: true },
              degree: 1,
              distance: 0,
            },
            {
              entity: { ...entity(E2, "ACCOUNT", "xxxx5678", "c2"), masked: true },
              degree: 1,
              distance: 1,
            },
          ],
          edges: [],
          stubs: [],
        }),
      ),
    }),
  );
  await showNetwork();
  expect(nodeEl(E1).textContent).toBe("98xxxx1234");
  expect(nodeEl(E2).textContent).toBe("xxxx5678");
  fireEvent.click(nodeEl(E1));
  const panel = await screen.findByRole("region", { name: "Selected item" });
  expect(within(panel).getByText("98xxxx1234")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Show as list" }));
  expect(screen.getByText("xxxx5678")).toBeTruthy();
});

test("a blank search shows 'Please fill in' beside the field and makes no call", async () => {
  const { calls } = open(routes());
  fireEvent.click(screen.getByRole("button", { name: "Show network" }));
  expect(
    await screen.findByText("Please fill in: Find a person, phone number, account or vehicle."),
  ).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Find a person, phone number, account or vehicle"), {
    target: { value: "   " },
  });
  fireEvent.click(screen.getByRole("button", { name: "Show network" }));
  expect(
    await screen.findByText("Please fill in: Find a person, phone number, account or vehicle."),
  ).toBeTruthy();
  expect(calls).toEqual([]);
});

test("a search shorter than the API minimum is refused in words, with no call", async () => {
  const { calls } = open(routes());
  fireEvent.change(screen.getByLabelText("Find a person, phone number, account or vehicle"), {
    target: { value: " a " },
  });
  fireEvent.click(screen.getByRole("button", { name: "Show network" }));
  expect(await screen.findByText("Please write at least 2 characters.")).toBeTruthy();
  expect(screen.queryByText(/We could not|Please check what you wrote/)).toBeNull();
  expect(calls).toEqual([]);
});

test("more matches than one page says so in words", async () => {
  open(
    routes({
      "GET /search/entities": json(200, {
        items: [entity(E1, "PHONE", "9000014471", "c1"), entity(E3, "PERSON", "Meena Rao", "c3")],
        next_cursor: "next-page",
        total: 120,
      }),
    }),
  );
  fireEvent.change(screen.getByLabelText("Find a person, phone number, account or vehicle"), {
    target: { value: "900" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Show network" }));
  expect(
    await screen.findByText("Showing the first 2. Narrow the search to see others."),
  ).toBeTruthy();
});

test("every stub, an organisation stub too, shows the lock, in the picture and in its panel", async () => {
  open(
    routes({
      [`GET /entities/${E1}/graph`]: json(
        200,
        graph({
          nodes: [node(E1, "ORG", "Rivergate Traders", "c1")],
          edges: [],
        }),
      ),
    }),
  );
  await showNetwork();
  expect(nodeEl("stub-1").querySelector("svg.lucide-lock")).not.toBeNull();
  fireEvent.click(nodeEl("stub-1"));
  const card = await screen.findByRole("region", { name: "Another police area" });
  expect(card.querySelector("svg.lucide-lock")).not.toBeNull();
  expect(card.textContent).not.toContain("Rivergate Traders");
});

test("150 nodes in a star are all drawn, with the cap message", async () => {
  const nodes = [node(E1, "PHONE", "9000014471", "c1")];
  const edges = [];
  for (let i = 1; i < 150; i++) {
    const id = `f${String(i).padStart(7, "0")}-1111-4111-8111-111111111111`;
    nodes.push(node(id, "PERSON", `Person ${i}`, `c${i}`, 1));
    edges.push({
      link_id: `a${String(i).padStart(7, "0")}-1111-4111-8111-111111111111`,
      state: "AUTO",
      band: "HIGH",
      from_entity_id: E1,
      to_entity_id: id,
    });
  }
  open(
    routes({
      [`GET /entities/${E1}/graph`]: json(200, graph({ nodes, edges, stubs: [], truncated: true })),
    }),
  );
  await showNetwork();
  expect(document.querySelectorAll("[data-node]")).toHaveLength(150);
  expect(
    screen.getByText("Showing the 150 closest. Narrow the search to see others."),
  ).toBeTruthy();
}, 30000);

test("Hindi shows the Show network button", async () => {
  open(routes(), "SENIOR", "hi");
  expect(screen.getByRole("button", { name: "नेटवर्क दिखाएँ" })).toBeTruthy();
});
