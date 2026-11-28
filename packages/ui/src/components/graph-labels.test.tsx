import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import {
  GraphCanvas,
  RestrictedCard,
  UiProvider,
  en,
  hi,
  type GraphEdge,
  type GraphNode,
} from "../index";
import { layoutGraph } from "./graph-layout";
import {
  DENSE_NODE_COUNT,
  edgeWordSize,
  labelHalfWidth,
  labelRect,
  overlaps,
  placeEdgeWords,
  shortLabel,
  visibleLabels,
  type Rect,
} from "./graph-labels";

afterEach(cleanup);

const ORIGIN = { x: 0, y: 0 };

function textOf(node: GraphNode): string {
  return node.restricted === true ? "" : node.label;
}

describe("label clip at the left edge (TIR-94 point 1)", () => {
  test("a long label is shortened with an ellipsis, never longer than the cap", () => {
    const short = shortLabel("Shri Mohammad Irfan Abdul Rahman Qureshi");
    expect(short.endsWith("…")).toBe(true);
    expect([...short].length).toBeLessThanOrEqual(20);
    expect(shortLabel("9000051234")).toBe("9000051234");
  });

  test("the layout keeps every label box inside the drawing width", () => {
    const labels = [
      "Shri Mohammad Irfan Abdul Rahman Qureshi",
      "9000051234",
      "UP32 AB 1234 XYZ",
      "इरफ़ान मोहम्मद अब्दुल रहमान क़ुरैशी",
    ];
    const nodes = labels.map((label, i) => ({ id: `n${i}`, label }));
    const edges = [
      { id: "e0", from: "n0", to: "n1" },
      { id: "e1", from: "n0", to: "n2" },
      { id: "e2", from: "n0", to: "n3" },
    ];
    const width = 375;
    const pos = layoutGraph(nodes, edges, width, 820, (id) =>
      labelHalfWidth(nodes.find((n) => n.id === id)?.label ?? ""),
    );
    for (const n of nodes) {
      const r = labelRect(pos.get(n.id) ?? ORIGIN, n.label, false);
      expect(r.x).toBeGreaterThanOrEqual(0);
      expect(r.x + r.w).toBeLessThanOrEqual(width);
    }
  });

  test("the canvas draws the shortened label and keeps the full name in the title", () => {
    const nodes: GraphNode[] = [
      { id: "p1", type: "person", label: "Shri Mohammad Irfan Abdul Rahman Qureshi" },
    ];
    const { container } = render(
      <UiProvider lang="en" app="admin">
        <GraphCanvas nodes={nodes} edges={[]} onSelect={() => {}} />
      </UiProvider>,
    );
    expect(container.querySelector(".tx-graph__label")?.textContent).toContain("…");
    expect(container.querySelector("[data-node] title")?.textContent).toBe(
      "Shri Mohammad Irfan Abdul Rahman Qureshi",
    );
  });
});

describe("edge words stay off the labels (point 2)", () => {
  const nodes: GraphNode[] = [
    { id: "a", type: "person", label: "Mohd. Irfan" },
    { id: "b", type: "person", label: "Irfan bhai" },
    { id: "c", type: "phone", label: "9000051234" },
  ];

  function wordBox(word: { x: number; y: number }, text: string): Rect {
    const size = edgeWordSize(text);
    return { x: word.x - size.w / 2, y: word.y - size.h / 2, w: size.w, h: size.h };
  }

  test("a word is placed clear of every node label", () => {
    const pos = new Map([
      ["a", { x: 100, y: 100 }],
      ["b", { x: 100, y: 300 }],
      ["c", { x: 100, y: 154 }],
    ]);
    const edge: GraphEdge = {
      id: "e",
      from: "a",
      to: "b",
      kind: "same_as",
      strength: "possible",
      state: "suggested",
    };
    const placed = placeEdgeWords([edge], nodes, pos, new Set(["a", "b", "c"]), () => "Possible");
    const word = placed.get("e");
    // c's label sits exactly on the midpoint (100, 200 is 46 below c): the old drawing put the word there
    expect(word).toBeDefined();
    if (!word) return;
    const box = wordBox(word, "Possible");
    for (const n of nodes) {
      expect(overlaps(box, labelRect(pos.get(n.id) ?? ORIGIN, textOf(n), false))).toBe(false);
    }
  });

  test("the word is left out when no clear spot exists", () => {
    // two nodes close together: the whole line is covered by their labels and shapes
    const pos = new Map([
      ["a", { x: 100, y: 100 }],
      ["b", { x: 100, y: 130 }],
    ]);
    const edge: GraphEdge = {
      id: "e",
      from: "a",
      to: "b",
      kind: "same_as",
      strength: "strong",
      state: "auto",
    };
    const placed = placeEdgeWords([edge], nodes, pos, new Set(["a", "b"]), () => "Strong");
    expect(placed.has("e")).toBe(false);
  });
});

describe("density (point 3)", () => {
  const many = (n: number): GraphNode[] =>
    Array.from({ length: n }, (_, i) => ({
      id: `n${i}`,
      type: "phone" as const,
      label: `90000${String(i).padStart(5, "0")}`,
    }));
  const hub = (n: number): GraphEdge[] =>
    Array.from({ length: n - 1 }, (_, i) => ({
      id: `e${i}`,
      from: "n0",
      to: `n${i + 1}`,
      kind: "connected" as const,
    }));

  test("below the dense count every label is shown", () => {
    const nodes = many(DENSE_NODE_COUNT);
    const edges = hub(nodes.length);
    const pos = layoutGraph(nodes, edges, 900, 560);
    expect(visibleLabels(nodes, edges, pos, undefined).size).toBe(nodes.length);
  });

  test("at 150 nodes shown labels never overlap and the selected one is always shown", () => {
    const nodes = many(150);
    const edges = hub(150);
    const pos = layoutGraph(nodes, edges, 900, 560);
    const shown = visibleLabels(nodes, edges, pos, "n77");
    expect(shown.size).toBeLessThan(150);
    expect(shown.has("n77")).toBe(true);
    const rects = [...shown].map((id) => {
      const node = nodes.find((n) => n.id === id);
      return labelRect(pos.get(id) ?? ORIGIN, node ? textOf(node) : "", false);
    });
    for (let i = 0; i < rects.length; i++) {
      for (let j = i + 1; j < rects.length; j++) {
        expect(overlaps(rects[i] as Rect, rects[j] as Rect)).toBe(false);
      }
    }
  });

  test("the canvas hides lesser labels at 150, says why, and keeps every node named", () => {
    const { container } = render(
      <UiProvider lang="en" app="admin">
        <GraphCanvas nodes={many(150)} edges={hub(150)} onSelect={() => {}} />
      </UiProvider>,
    );
    expect(container.querySelectorAll("[data-node]")).toHaveLength(150);
    expect(container.querySelectorAll(".tx-graph__label").length).toBeLessThan(150);
    expect(container.textContent).toContain(en["graph.labelsHidden"].split("{count}")[0]);
    for (const node of container.querySelectorAll("[data-node]")) {
      expect(node.getAttribute("aria-label")).toBeTruthy();
    }
  });

  test("no hidden-labels note when everything fits", () => {
    const { container } = render(
      <UiProvider lang="en" app="admin">
        <GraphCanvas nodes={many(5)} edges={hub(5)} onSelect={() => {}} />
      </UiProvider>,
    );
    expect(container.textContent).not.toContain(en["graph.labelsHidden"].split("{count}")[0]);
  });

  test("Hindi has the new string", () => {
    expect(hi["graph.labelsHidden"]?.trim()).toBeTruthy();
  });
});

describe("organisation on the restricted card (point 4)", () => {
  test("shows an organisation item line with word and value, in English and Hindi", () => {
    for (const [lang, dict] of [
      ["en", en],
      ["hi", hi],
    ] as const) {
      const { container } = render(
        <UiProvider lang={lang} app="admin">
          <RestrictedCard itemType="org" itemValue="Irfan Traders" />
        </UiProvider>,
      );
      const line = container.querySelector(".tx-restricted__item");
      expect(line?.textContent).toContain(dict["item.org"]);
      expect(line?.textContent).toContain("Irfan Traders");
      cleanup();
    }
  });
});
