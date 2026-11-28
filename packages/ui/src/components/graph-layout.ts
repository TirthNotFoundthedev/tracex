import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";

import type { Strength } from "./strength";

export const GRAPH_NODE_TYPES = ["person", "phone", "bank", "vehicle", "org"] as const;
export type GraphNodeType = (typeof GRAPH_NODE_TYPES)[number];

export type GraphLinkState = "auto" | "suggested" | "confirmed";

/** An entity the viewer may see. */
export interface GraphEntityNode {
  id: string;
  type: GraphNodeType;
  label: string;
  restricted?: false;
}

/**
 * A hidden link's far end. It carries no type, label or any case data
 * (DESIGN_RULES section 10); the canvas draws only the words "Another police area".
 */
export interface GraphStubNode {
  id: string;
  restricted: true;
}

export type GraphNode = GraphEntityNode | GraphStubNode;

/** Same entity seen in two places. Only strong and possible exist (section 8). */
export interface GraphSameAsEdge {
  id: string;
  from: string;
  to: string;
  kind: "same_as";
  strength: Strength;
  state: GraphLinkState;
}

/** A person and their phone, account or vehicle: a relation, not a match, so no strength. */
export interface GraphConnectedEdge {
  id: string;
  from: string;
  to: string;
  kind: "connected";
}

/** A link whose far end is in another police area. No strength, no state. */
export interface GraphRestrictedEdge {
  id: string;
  from: string;
  to: string;
  kind: "restricted";
}

export type GraphEdge = GraphSameAsEdge | GraphConnectedEdge | GraphRestrictedEdge;

export interface GraphPoint {
  x: number;
  y: number;
}

/** Fixed number of simulation steps: the picture is a pure function of the input. */
export const LAYOUT_TICKS = 300;
export const LAYOUT_MARGIN = 56;

/** Small seeded generator (mulberry32) so the layout never depends on Math.random. */
function seeded(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

interface SimNode extends SimulationNodeDatum {
  id: string;
}

/**
 * Runs the force simulation to completion before anything is drawn, so nothing
 * moves on screen (DESIGN_RULES section 12: no physics bounce). Input order does not matter.
 */
export function layoutGraph(
  nodes: readonly { id: string }[],
  edges: readonly { id: string; from: string; to: string }[],
  width: number,
  height: number,
  /** Half the width of a node's label, so the label box never crosses the left or right edge. */
  halfLabelWidth: (id: string) => number = () => 0,
): Map<string, GraphPoint> {
  const simNodes: SimNode[] = nodes.map((n) => ({ id: n.id })).sort((a, b) => cmp(a.id, b.id));
  const known = new Set(simNodes.map((n) => n.id));
  const links: SimulationLinkDatum<SimNode>[] = edges
    .filter((e) => known.has(e.from) && known.has(e.to))
    .map((e) => ({ id: e.id, source: e.from, target: e.to }))
    .sort((a, b) => cmp(a.id, b.id))
    .map(({ source, target }) => ({ source, target }));

  // On a phone the picture grows downward instead of sideways, so labels stay apart.
  const narrow = width < 600;
  const sim = forceSimulation(simNodes)
    .randomSource(seeded(20260101))
    .force(
      "link",
      forceLink<SimNode, SimulationLinkDatum<SimNode>>(links)
        .id((n) => n.id)
        .distance(170)
        .strength(0.7),
    )
    .force("charge", forceManyBody().strength(-1400))
    .force("collide", forceCollide(72))
    .force("center", forceCenter(width / 2, height / 2))
    .force("x", forceX(width / 2).strength(narrow ? 0.12 : 0.04))
    .force("y", forceY(height / 2).strength(narrow ? 0.01 : 0.06))
    .stop();
  sim.tick(LAYOUT_TICKS);

  const out = new Map<string, GraphPoint>();
  for (const n of simNodes) {
    const mx = Math.min(Math.max(LAYOUT_MARGIN, halfLabelWidth(n.id) + 4), width / 2);
    out.set(n.id, {
      x: clamp(n.x ?? width / 2, mx, width - mx),
      y: clamp(n.y ?? height / 2, LAYOUT_MARGIN, height - LAYOUT_MARGIN),
    });
  }
  return out;
}

function cmp(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(Math.max(v, lo), hi);
}
