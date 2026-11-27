import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import {
  GraphCanvas,
  GraphLegend,
  UiProvider,
  en,
  hi,
  type AppVariant,
  type GraphEdge,
  type GraphNode,
  type Language,
} from "../index";
import { GRAPH_NODE_TYPES, layoutGraph } from "./graph-layout";

afterEach(cleanup);

function must<T>(value: T | null | undefined): T {
  if (value === null || value === undefined) throw new Error("expected a value");
  return value;
}

const nodes: GraphNode[] = [
  { id: "p1", type: "person", label: "Mohd. Irfan" },
  { id: "p2", type: "person", label: "Irfan bhai" },
  { id: "ph1", type: "phone", label: "9000051234" },
  { id: "b1", type: "bank", label: "SBIN 4471" },
  { id: "v1", type: "vehicle", label: "UP32 AB 1234" },
  { id: "o1", type: "org", label: "Irfan Traders" },
  { id: "s1", restricted: true },
];

const edges: GraphEdge[] = [
  { id: "e1", from: "p1", to: "p2", kind: "same_as", strength: "strong", state: "auto" },
  { id: "e2", from: "p1", to: "o1", kind: "same_as", strength: "possible", state: "suggested" },
  { id: "e3", from: "p1", to: "ph1", kind: "connected" },
  { id: "e4", from: "p2", to: "b1", kind: "connected" },
  { id: "e5", from: "p2", to: "v1", kind: "connected" },
  { id: "e6", from: "ph1", to: "s1", kind: "restricted" },
];

function ui(node: React.ReactNode, lang: Language = "en", app: AppVariant = "admin") {
  return render(
    <UiProvider lang={lang} app={app}>
      {node}
    </UiProvider>,
  );
}

describe("GraphCanvas rendering", () => {
  test("draws one focusable, named node per entity and one named edge per link", () => {
    ui(<GraphCanvas nodes={nodes} edges={edges} onSelect={() => {}} />);
    expect(document.querySelectorAll("[data-node]")).toHaveLength(7);
    expect(screen.getByRole("button", { name: "Person: Mohd. Irfan" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Phone number: 9000051234" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Organisation: Irfan Traders" })).toBeTruthy();
    expect(document.querySelectorAll("[data-edge]")).toHaveLength(6);
  });

  test("node label is visible text, not hover-only", () => {
    ui(<GraphCanvas nodes={nodes} edges={edges} onSelect={() => {}} />);
    const label = document.querySelector('[data-node="p1"] text');
    expect(label?.textContent).toBe("Mohd. Irfan");
  });

  test("each node type has its own shape", () => {
    ui(<GraphCanvas nodes={nodes} edges={edges} onSelect={() => {}} />);
    const shapes = new Set(
      ["p1", "ph1", "b1", "v1", "o1", "s1"].map((id) =>
        document.querySelector(`[data-node="${id}"]`)?.getAttribute("data-shape"),
      ),
    );
    expect(shapes.size).toBe(6);
  });

  test("an empty graph draws no nodes and says so", () => {
    ui(<GraphCanvas nodes={[]} edges={[]} onSelect={() => {}} />);
    expect(document.querySelectorAll("[data-node]")).toHaveLength(0);
    expect(screen.getByText(en["graph.empty"])).toBeTruthy();
  });

  test("shows the cap message when truncated and never draws more than 150 nodes", () => {
    const many: GraphNode[] = Array.from({ length: 160 }, (_, i) => ({
      id: `n${i}`,
      type: "phone",
      label: `90000${String(i).padStart(5, "0")}`,
    }));
    ui(<GraphCanvas nodes={many} edges={[]} truncated onSelect={() => {}} />);
    expect(screen.getByText(en["graph.truncated"])).toBeTruthy();
    expect(document.querySelectorAll("[data-node]")).toHaveLength(150);
  });
});

describe("link strength without colour", () => {
  test("strong is a solid heavy line with words; possible is dashed with words", () => {
    ui(<GraphCanvas nodes={nodes} edges={edges} onSelect={() => {}} />);
    const strong = must(document.querySelector('[data-edge="e1"]'));
    const possible = must(document.querySelector('[data-edge="e2"]'));
    expect(strong.getAttribute("data-style")).toBe("solid-heavy");
    expect(possible.getAttribute("data-style")).toBe("dashed");
    expect(strong.querySelector("line")?.getAttribute("stroke-dasharray")).toBeNull();
    expect(possible.querySelector("line")?.getAttribute("stroke-dasharray")).toBeTruthy();
    expect(Number(strong.querySelector("line")?.getAttribute("stroke-width"))).toBeGreaterThan(
      Number(possible.querySelector("line")?.getAttribute("stroke-width")),
    );
    expect(within(strong as HTMLElement).getByText(en["graph.edge.strongShort"])).toBeTruthy();
    expect(within(possible as HTMLElement).getByText(en["graph.edge.possibleShort"])).toBeTruthy();
    expect(strong.getAttribute("aria-label")).toContain(en["strength.strong"]);
    expect(possible.getAttribute("aria-label")).toContain(en["strength.possible"]);
  });

  test("a plain connection and a restricted one carry no strength", () => {
    ui(<GraphCanvas nodes={nodes} edges={edges} onSelect={() => {}} />);
    for (const id of ["e3", "e6"]) {
      const edge = must(document.querySelector(`[data-edge="${id}"]`));
      expect(edge.textContent).not.toContain(en["graph.edge.strongShort"]);
      expect(edge.textContent).not.toContain(en["graph.edge.possibleShort"]);
    }
    expect(document.querySelector('[data-edge="e3"]')?.getAttribute("data-style")).toBe("dotted");
    expect(document.querySelector('[data-edge="e6"]')?.getAttribute("data-style")).toBe(
      "dashed-restricted",
    );
  });
});

describe("keyboard and selection", () => {
  test("Enter and Space on a node call onSelect with its id; click does too", () => {
    const onSelect = vi.fn();
    ui(<GraphCanvas nodes={nodes} edges={edges} onSelect={onSelect} />);
    const node = screen.getByRole("button", { name: "Bank account: SBIN 4471" });
    expect(node.getAttribute("tabindex")).toBe("0");
    fireEvent.keyDown(node, { key: "Enter" });
    fireEvent.keyDown(node, { key: " " });
    fireEvent.click(node);
    expect(onSelect.mock.calls).toEqual([["b1"], ["b1"], ["b1"]]);
  });

  test("every node is in the tab order", () => {
    ui(<GraphCanvas nodes={nodes} edges={edges} onSelect={() => {}} />);
    const tabbable = document.querySelectorAll('[data-node][tabindex="0"]');
    expect(tabbable).toHaveLength(nodes.length);
  });

  test("selected node is marked for assistive technology and by shape weight", () => {
    ui(<GraphCanvas nodes={nodes} edges={edges} selectedId="p1" onSelect={() => {}} />);
    const selected = screen.getByRole("button", { name: "Person: Mohd. Irfan" });
    expect(selected.getAttribute("aria-pressed")).toBe("true");
    expect(selected.getAttribute("data-selected")).toBe("true");
    const other = screen.getByRole("button", { name: "Person: Irfan bhai" });
    expect(other.getAttribute("aria-pressed")).toBe("false");
  });

  test("a focus ring rule exists for nodes in the stylesheet", async () => {
    const css = (await import("./ui.css?raw")).default;
    expect(css).toMatch(/\.tx-graph__node:focus-visible/);
  });
});

describe("restricted node holds no case data", () => {
  test("shows only the words Another police area, even if the caller passes extra fields", () => {
    const leaky = [
      { id: "s9", restricted: true, label: "SECRET NAME", type: "person", caseNumber: "99/1" },
    ] as unknown as GraphNode[];
    const { container } = ui(<GraphCanvas nodes={leaky} edges={[]} onSelect={() => {}} />);
    const node = screen.getByRole("button", { name: en["restricted.title"] });
    expect(node.textContent).toBe(en["restricted.title"]);
    expect(container.innerHTML).not.toContain("SECRET");
    expect(container.innerHTML).not.toContain("99/1");
    expect(node.getAttribute("data-shape")).toBe("restricted");
  });

  test("the list view shows a restricted node with the same words only", () => {
    ui(<GraphCanvas nodes={nodes} edges={edges} view="list" onSelect={() => {}} />);
    const [nodeTable] = screen.getAllByRole("table");
    const rows = within(must(nodeTable)).getAllByRole("row");
    const stubRow = must(rows[rows.length - 1]);
    expect(stubRow.textContent).toContain(en["restricted.title"]);
  });
});

describe("text alternative", () => {
  test("list view lists every node and every link, in words", () => {
    const onSelect = vi.fn();
    ui(<GraphCanvas nodes={nodes} edges={edges} view="list" onSelect={onSelect} />);
    const [nodeTable, linkTable] = screen.getAllByRole("table");
    expect(within(must(nodeTable)).getAllByRole("row")).toHaveLength(1 + nodes.length);
    expect(within(must(linkTable)).getAllByRole("row")).toHaveLength(1 + edges.length);
    expect(within(must(linkTable)).getAllByText(en["strength.strong"]).length).toBeGreaterThan(0);
    expect(within(must(linkTable)).getAllByText(en["strength.possible"]).length).toBeGreaterThan(0);
    expect(within(must(linkTable)).getAllByText(en["graph.state.auto"])).toHaveLength(1);
    fireEvent.click(
      must(within(must(nodeTable)).getAllByRole("button", { name: en["nav.openRow"] })[0]),
    );
    expect(onSelect).toHaveBeenCalledWith("p1");
  });

  test("the toggle switches between picture and list when uncontrolled", () => {
    ui(<GraphCanvas nodes={nodes} edges={edges} onSelect={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: en["graph.showList"] }));
    expect(screen.getAllByRole("table")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: en["graph.showPicture"] }));
    expect(screen.queryAllByRole("table")).toHaveLength(0);
  });

  test("the toggle reports the change when controlled", () => {
    const onViewChange = vi.fn();
    ui(
      <GraphCanvas
        nodes={nodes}
        edges={edges}
        view="picture"
        onViewChange={onViewChange}
        onSelect={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: en["graph.showList"] }));
    expect(onViewChange).toHaveBeenCalledWith("list");
  });
});

describe("layout is deterministic and stable", () => {
  test("same input gives the same positions, in any input order", () => {
    const a = layoutGraph(nodes, edges, 900, 560);
    const b = layoutGraph([...nodes].reverse(), [...edges].reverse(), 900, 560);
    expect([...a.entries()].sort()).toEqual([...b.entries()].sort());
  });

  test("every node gets a finite position inside the area", () => {
    const pos = layoutGraph(nodes, edges, 900, 560);
    expect(pos.size).toBe(nodes.length);
    for (const { x, y } of pos.values()) {
      expect(Number.isFinite(x) && Number.isFinite(y)).toBe(true);
      expect(x).toBeGreaterThan(0);
      expect(x).toBeLessThan(900);
      expect(y).toBeGreaterThan(0);
      expect(y).toBeLessThan(560);
    }
  });

  test("redrawing with a new selection does not move nodes", () => {
    const { rerender } = ui(<GraphCanvas nodes={nodes} edges={edges} onSelect={() => {}} />);
    const before = document.querySelector('[data-node="p2"]')?.getAttribute("transform");
    expect(before).toBeTruthy();
    rerender(
      <UiProvider lang="en" app="admin">
        <GraphCanvas nodes={nodes} edges={edges} selectedId="p2" onSelect={() => {}} />
      </UiProvider>,
    );
    expect(document.querySelector('[data-node="p2"]')?.getAttribute("transform")).toBe(before);
  });
});

describe("GraphLegend", () => {
  test("explains every node type and every edge style in words, in English and Hindi", () => {
    for (const lang of ["en", "hi"] as const) {
      const catalog = lang === "en" ? en : hi;
      ui(<GraphLegend />, lang);
      for (const type of GRAPH_NODE_TYPES) {
        expect(screen.getAllByText(catalog[`graph.legend.node.${type}`]).length).toBeGreaterThan(0);
      }
      for (const key of [
        "graph.legend.node.restricted",
        "graph.legend.edge.strong",
        "graph.legend.edge.possible",
        "graph.legend.edge.connected",
        "graph.legend.edge.restricted",
      ] as const) {
        expect(screen.getAllByText(catalog[key]).length).toBeGreaterThan(0);
      }
      cleanup();
    }
  });

  test("has one entry per node type plus restricted, and four edge entries", () => {
    ui(<GraphLegend />);
    expect(document.querySelectorAll("[data-legend-node]")).toHaveLength(
      GRAPH_NODE_TYPES.length + 1,
    );
    expect(document.querySelectorAll("[data-legend-edge]")).toHaveLength(4);
  });

  test("legend shows no weak or low link style", () => {
    ui(<GraphLegend />);
    expect(document.body.textContent?.toLowerCase()).not.toContain("weak");
  });
});

describe("graph strings", () => {
  test("every graph string exists in Hindi", () => {
    const keys = Object.keys(en).filter((k) => k.startsWith("graph."));
    expect(keys.length).toBeGreaterThan(10);
    for (const key of keys) {
      expect((hi as Record<string, string>)[key]?.trim()).toBeTruthy();
    }
  });
});

describe("officer app", () => {
  test("GraphCanvas and GraphLegend render nothing", () => {
    const { container } = ui(
      <>
        <GraphCanvas nodes={nodes} edges={edges} onSelect={() => {}} />
        <GraphLegend />
      </>,
      "en",
      "officer",
    );
    expect(container.querySelector(".tx-root")?.innerHTML).toBe("");
  });
});
