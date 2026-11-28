import type { GraphEdge, GraphNode, GraphPoint } from "./graph-layout";

/**
 * Label and edge-word placement for the graph picture (DESIGN_RULES section 12).
 * All pure: sizes are estimates from character count, so the result is the same in
 * a browser and in a test, and a reviewer can compare two screenshots.
 */

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** 14px admin text; Devanagari and capitals are wider than Latin lower case, so the estimate is generous. */
const CHAR_W = 9;
const LABEL_H = 20;
const WORD_H = 20;
const SHAPE_HALF = 30;
const PAD = 3;

/** A label longer than this is cut with an ellipsis; the full name stays in the title and the list. */
export const LABEL_MAX_CHARS = 20;

/** From this many nodes, labels that would sit on another label or shape are hidden. */
export const DENSE_NODE_COUNT = 30;

export function shortLabel(label: string): string {
  const chars = [...label];
  return chars.length <= LABEL_MAX_CHARS
    ? label
    : `${chars.slice(0, LABEL_MAX_CHARS - 1).join("")}…`;
}

export function labelHalfWidth(label: string): number {
  return ([...shortLabel(label)].length * CHAR_W) / 2;
}

/** The box a node label occupies, centred under the node (same offsets the drawing uses). */
export function labelRect(p: GraphPoint, label: string, restricted: boolean): Rect {
  const baseline = p.y + (restricted ? 42 : 46);
  const half = labelHalfWidth(label);
  return { x: p.x - half, y: baseline - LABEL_H + 5, w: half * 2, h: LABEL_H };
}

function shapeRect(p: GraphPoint): Rect {
  return { x: p.x - SHAPE_HALF, y: p.y - SHAPE_HALF, w: SHAPE_HALF * 2, h: SHAPE_HALF * 2 };
}

export function overlaps(a: Rect, b: Rect): boolean {
  return (
    a.x < b.x + b.w + PAD && b.x < a.x + a.w + PAD && a.y < b.y + b.h + PAD && b.y < a.y + a.h + PAD
  );
}

export function edgeWordSize(word: string): { w: number; h: number } {
  return { w: [...word].length * CHAR_W + 8, h: WORD_H };
}

function nodeText(node: GraphNode): string {
  return node.restricted === true ? "Another police area" : node.label;
}

/**
 * Ids whose label is drawn. Up to DENSE_NODE_COUNT nodes: all. Above it: the selected node,
 * its neighbours, then the best-connected nodes, each only if its box is clear of the labels
 * already shown and of every other node's shape. Reason: at 150 nodes the picture cannot hold
 * 150 readable names; the list view is the readable route and the note says so.
 */
export function visibleLabels(
  nodes: readonly GraphNode[],
  edges: readonly GraphEdge[],
  positions: ReadonlyMap<string, GraphPoint>,
  selectedId: string | undefined,
): Set<string> {
  if (nodes.length <= DENSE_NODE_COUNT) return new Set(nodes.map((n) => n.id));

  const degree = new Map<string, number>();
  const near = new Set<string>();
  for (const e of edges) {
    degree.set(e.from, (degree.get(e.from) ?? 0) + 1);
    degree.set(e.to, (degree.get(e.to) ?? 0) + 1);
    if (e.from === selectedId) near.add(e.to);
    if (e.to === selectedId) near.add(e.from);
  }
  const rank = (n: GraphNode) => (n.id === selectedId ? 2 : near.has(n.id) ? 1 : 0);
  const ordered = [...nodes].sort(
    (a, b) =>
      rank(b) - rank(a) ||
      (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0) ||
      (a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
  );

  const shapes = nodes.flatMap((n) => {
    const p = positions.get(n.id);
    return p ? [{ id: n.id, rect: shapeRect(p) }] : [];
  });
  const shown = new Set<string>();
  const taken: Rect[] = [];
  for (const node of ordered) {
    const p = positions.get(node.id);
    if (!p) continue;
    const rect = labelRect(p, nodeText(node), node.restricted === true);
    const must = node.id === selectedId;
    const clear =
      taken.every((t) => !overlaps(rect, t)) &&
      shapes.every((s) => s.id === node.id || !overlaps(rect, s.rect));
    if (must || clear) {
      shown.add(node.id);
      taken.push(rect);
    }
  }
  return shown;
}

/** Spots along the line, middle first. */
const STEPS = [0.5, 0.42, 0.58, 0.34, 0.66, 0.26, 0.74, 0.18, 0.82, 0.12, 0.88];

/** Offsets from the line, in px: on it first, then beside it. */
const SIDES = [0, 18, -18];

/**
 * Centre point of the word ("Strong", "Possible") for each edge that has one, chosen
 * clear of node shapes, shown labels and words already placed. An edge with no clear
 * spot gets no word: its line style, its spoken name and the list still say the strength.
 */
export function placeEdgeWords(
  edges: readonly GraphEdge[],
  nodes: readonly GraphNode[],
  positions: ReadonlyMap<string, GraphPoint>,
  labelled: ReadonlySet<string>,
  wordOf: (edge: GraphEdge) => string,
): Map<string, GraphPoint> {
  const obstacles: Rect[] = [];
  for (const n of nodes) {
    const p = positions.get(n.id);
    if (!p) continue;
    obstacles.push(shapeRect(p));
    if (labelled.has(n.id)) obstacles.push(labelRect(p, nodeText(n), n.restricted === true));
  }
  const out = new Map<string, GraphPoint>();
  const sorted = [...edges].sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  for (const edge of sorted) {
    const word = wordOf(edge);
    const a = positions.get(edge.from);
    const b = positions.get(edge.to);
    if (!word || !a || !b) continue;
    const size = edgeWordSize(word);
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len = Math.hypot(dx, dy) || 1;
    // Unit normal: the word may sit just beside the line when the line itself is crowded.
    const nx = -dy / len;
    const ny = dx / len;
    let done = false;
    for (const side of SIDES) {
      for (const t of STEPS) {
        const x = a.x + dx * t + nx * side;
        const y = a.y + dy * t + ny * side;
        const box = { x: x - size.w / 2, y: y - size.h / 2, w: size.w, h: size.h };
        if (obstacles.every((o) => !overlaps(box, o))) {
          out.set(edge.id, { x, y });
          obstacles.push(box);
          done = true;
          break;
        }
      }
      if (done) break;
    }
  }
  return out;
}
