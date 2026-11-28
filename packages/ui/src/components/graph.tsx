import { select } from "d3-selection";
import { zoom, zoomIdentity, type ZoomBehavior, type ZoomTransform } from "d3-zoom";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";

import { Button } from "./Button";
import { useUi } from "./context";
import { Message } from "./feedback";
import { Icon, type IconName } from "./Icon";
import { labelHalfWidth, placeEdgeWords, shortLabel, visibleLabels } from "./graph-labels";
import {
  GRAPH_NODE_TYPES,
  layoutGraph,
  type GraphEdge,
  type GraphNode,
  type GraphNodeType,
} from "./graph-layout";
import { Table } from "./lists";
import { StrengthBadge, type Strength } from "./strength";

/** DESIGN_RULES section 12: the picture never holds more than this many nodes. */
export const GRAPH_NODE_CAP = 150;

const DEFAULT_WIDTH = 900;
const WIDE_HEIGHT = 560;
/** A phone is narrow, so the picture is taller to keep labels apart. */
const NARROW_HEIGHT = 820;
const NARROW_PER_NODE = 150;

/** The picture grows with the node count, so shapes keep apart (zoom handles the rest). */
function pictureHeight(width: number, count: number): number {
  const extra = Math.max(0, count - 30);
  if (width < 600)
    return Math.max(NARROW_HEIGHT, Math.min(count, 30) * NARROW_PER_NODE + extra * 40);
  return WIDE_HEIGHT + extra * 8;
}

type ShapeName = GraphNodeType | "restricted";

/** One shape per type, so type is never carried by colour (section 12). */
const SHAPE_NAME: Record<ShapeName, string> = {
  person: "circle",
  phone: "rounded-square",
  bank: "diamond",
  vehicle: "triangle",
  org: "hexagon",
  restricted: "restricted",
};

const NODE_ICON: Record<GraphNodeType, IconName> = {
  person: "person",
  phone: "phone",
  bank: "bank",
  vehicle: "vehicle",
  org: "org",
};

type EdgeStyleName = "solid-heavy" | "dashed" | "dotted" | "dashed-restricted";

interface EdgeLook {
  name: EdgeStyleName;
  width: number;
  dash?: string;
}

/** Heavy solid = strong, dashed = possible (section 8 border styles); relations are thin and dotted. */
const EDGE_LOOK: Record<EdgeStyleName, EdgeLook> = {
  "solid-heavy": { name: "solid-heavy", width: 5 },
  dashed: { name: "dashed", width: 3, dash: "10 6" },
  dotted: { name: "dotted", width: 3, dash: "3 5" },
  "dashed-restricted": { name: "dashed-restricted", width: 3, dash: "10 6" },
};

function edgeLook(edge: GraphEdge): EdgeLook {
  if (edge.kind === "same_as") {
    return EDGE_LOOK[edge.strength === "strong" ? "solid-heavy" : "dashed"];
  }
  return EDGE_LOOK[edge.kind === "connected" ? "dotted" : "dashed-restricted"];
}

/** Shape outline centred on 0,0. Fits a 56px box. */
function Outline({ shape, selected }: { shape: ShapeName; selected?: boolean }) {
  const common = { className: "tx-graph__shape", strokeWidth: selected ? 5 : 2 };
  switch (shape) {
    case "person":
      return <circle r={24} {...common} />;
    case "phone":
      return <rect x={-22} y={-22} width={44} height={44} rx={10} {...common} />;
    case "bank":
      return <polygon points="0,-28 28,0 0,28 -28,0" {...common} />;
    case "vehicle":
      return <polygon points="0,-28 28,22 -28,22" {...common} />;
    case "org":
      return <polygon points="-14,-25 14,-25 28,0 14,25 -14,25 -28,0" {...common} />;
    case "restricted":
      return (
        <rect x={-30} y={-22} width={60} height={44} rx={4} strokeDasharray="6 4" {...common} />
      );
  }
}

function Glyph({ name, dy = 0 }: { name: IconName; dy?: number }) {
  const { app } = useUi();
  const size = app === "admin" ? 20 : 24;
  return (
    <g transform={`translate(${-size / 2} ${-size / 2 + dy})`}>
      <Icon name={name} />
    </g>
  );
}

function NodeBody({ shape, selected }: { shape: ShapeName; selected?: boolean }) {
  return (
    <>
      <Outline shape={shape} selected={selected} />
      <Glyph
        name={shape === "restricted" ? "restricted" : NODE_ICON[shape]}
        dy={shape === "vehicle" ? 5 : 0}
      />
    </>
  );
}

export type GraphView = "picture" | "list";

export interface GraphCanvasProps {
  /** Plain model: the app maps API responses to this, so no API type reaches the canvas. */
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedId?: string;
  /** Called with the node id on click, Enter or Space. */
  onSelect: (id: string) => void;
  /** True when the API cut the result at its limit; shows the cap message. */
  truncated?: boolean;
  /** Set both to control the picture/list toggle; leave out to let the canvas keep it. */
  view?: GraphView;
  onViewChange?: (view: GraphView) => void;
}

/** Admin only. Renders nothing in the officer app (section 14). */
export function GraphCanvas(props: GraphCanvasProps) {
  const { app } = useUi();
  if (app !== "admin") return null;
  return <GraphCanvasInner {...props} />;
}

function GraphCanvasInner({
  nodes: allNodes,
  edges: allEdges,
  selectedId,
  onSelect,
  truncated,
  view: controlledView,
  onViewChange,
}: GraphCanvasProps) {
  const { t, lang } = useUi();
  const [ownView, setOwnView] = useState<GraphView>("picture");
  const view = controlledView ?? ownView;
  const setView = (next: GraphView) => {
    if (controlledView === undefined) setOwnView(next);
    onViewChange?.(next);
  };

  const capped = allNodes.length > GRAPH_NODE_CAP;
  const nodes = useMemo(() => allNodes.slice(0, GRAPH_NODE_CAP), [allNodes]);
  const edges = useMemo(() => {
    const ids = new Set(nodes.map((n) => n.id));
    return allEdges.filter((e) => ids.has(e.from) && ids.has(e.to));
  }, [allEdges, nodes]);

  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const w = Math.round(entry?.contentRect.width ?? 0);
      if (w >= 240) setWidth(w);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [view]);

  const height = pictureHeight(width, nodes.length);
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const labelText = (node: GraphNode): string =>
    node.restricted === true ? t("restricted.title") : node.label;
  const positions = useMemo(
    () =>
      layoutGraph(nodes, edges, width, height, (id) => {
        const node = byId.get(id);
        return node
          ? labelHalfWidth(node.restricted === true ? t("restricted.title") : node.label)
          : 0;
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- t only changes with the language
    [nodes, edges, width, height, byId, lang],
  );
  const shownLabels = useMemo(
    () => visibleLabels(nodes, edges, positions, selectedId),
    [nodes, edges, positions, selectedId],
  );
  const [focusedId, setFocusedId] = useState<string | undefined>();
  const edgeWordOf = (edge: GraphEdge): string =>
    edge.kind !== "same_as"
      ? ""
      : t(edge.strength === "strong" ? "graph.edge.strongShort" : "graph.edge.possibleShort");
  const edgeWords = useMemo(
    () => placeEdgeWords(edges, nodes, positions, shownLabels, edgeWordOf),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- edgeWordOf depends only on the language
    [edges, nodes, positions, shownLabels, lang],
  );
  const hiddenLabelCount = nodes.length - shownLabels.size;

  const svgRef = useRef<SVGSVGElement>(null);
  const viewRef = useRef<SVGGElement>(null);
  const zoomRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const transformRef = useRef<ZoomTransform>(zoomIdentity);

  useEffect(() => {
    const svg = svgRef.current;
    if (view !== "picture" || !svg) return;
    const behavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 4])
      .extent([
        [0, 0],
        [width, height],
      ])
      // Page scroll keeps working: the wheel zooms only with Ctrl, touch needs two fingers.
      .filter((event: Event) => {
        const e = event as MouseEvent & { touches?: TouchList };
        if (e.type === "wheel") return e.ctrlKey;
        if (e.type.startsWith("touch")) return (e.touches?.length ?? 0) >= 2;
        return !e.button;
      })
      .on("zoom", (event: { transform: ZoomTransform }) => {
        transformRef.current = event.transform;
        viewRef.current?.setAttribute("transform", event.transform.toString());
      });
    zoomRef.current = behavior;
    select(svg).call(behavior);
    if (transformRef.current !== zoomIdentity)
      select(svg).call(behavior.transform, transformRef.current);
    return () => {
      select(svg).on(".zoom", null);
    };
  }, [view, width, height]);

  const zoomBy = (factor: number) => {
    const svg = svgRef.current;
    if (svg && zoomRef.current) select(svg).call(zoomRef.current.scaleBy, factor);
  };
  const zoomReset = () => {
    const svg = svgRef.current;
    if (svg && zoomRef.current) select(svg).call(zoomRef.current.transform, zoomIdentity);
  };
  /** Keyboard focus never lands out of sight: move the view, not the nodes. */
  const bringIntoView = (x: number, y: number) => {
    const svg = svgRef.current;
    const tr = transformRef.current;
    if (!svg || !zoomRef.current) return;
    const sx = tr.applyX(x);
    const sy = tr.applyY(y);
    if (sx < 40 || sx > width - 40 || sy < 40 || sy > height - 40) {
      select(svg).call(zoomRef.current.translateTo, x, y);
    }
  };

  const nameOf = (node: GraphNode | undefined): string =>
    !node || node.restricted === true ? t("restricted.title") : node.label;
  const typeWordOf = (node: GraphNode | undefined): string =>
    !node || node.restricted === true ? t("restricted.title") : t(`item.${node.type}`);
  const strengthWords = (s: Strength) =>
    t(s === "strong" ? "strength.strong" : "strength.possible");

  const edgeAria = (edge: GraphEdge) => {
    const a = nameOf(byId.get(edge.from));
    const b = nameOf(byId.get(edge.to));
    if (edge.kind === "same_as") {
      return t("graph.edge.sameAsLabel", {
        strength: strengthWords(edge.strength),
        state: t(`graph.state.${edge.state}`),
        a,
        b,
      });
    }
    if (edge.kind === "connected") return t("graph.edge.connectedLabel", { a, b });
    const entity = byId.get(edge.from)?.restricted === true ? edge.to : edge.from;
    return t("graph.edge.restrictedLabel", { a: nameOf(byId.get(entity)) });
  };

  const onKey = (event: KeyboardEvent, id: string) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(id);
    }
  };

  const toggle =
    view === "picture" ? (
      <Button variant="secondary" icon="list" onClick={() => setView("list")}>
        {t("graph.showList")}
      </Button>
    ) : (
      <Button variant="secondary" icon="picture" onClick={() => setView("picture")}>
        {t("graph.showPicture")}
      </Button>
    );

  return (
    <section className="tx-graph">
      <div className="tx-graph__bar">
        {toggle}
        {view === "picture" && nodes.length > 0 ? (
          <div className="tx-graph__zoom">
            <Button variant="secondary" icon="zoomOut" onClick={() => zoomBy(1 / 1.4)}>
              {t("graph.zoomOut")}
            </Button>
            <Button variant="secondary" icon="zoomIn" onClick={() => zoomBy(1.4)}>
              {t("graph.zoomIn")}
            </Button>
            <Button variant="secondary" onClick={zoomReset}>
              {t("graph.zoomReset")}
            </Button>
          </div>
        ) : null}
      </div>

      {truncated || capped ? <Message kind="info">{t("graph.truncated")}</Message> : null}

      {view === "picture" && hiddenLabelCount > 0 ? (
        <Message kind="info">{t("graph.labelsHidden", { count: hiddenLabelCount })}</Message>
      ) : null}

      {nodes.length === 0 ? (
        <p className="tx-body">{t("graph.empty")}</p>
      ) : view === "list" ? (
        <div className="tx-graph__lists">
          <Table
            caption={t("graph.nodesCaption")}
            rows={nodes}
            rowKey={(n) => n.id}
            onOpenRow={(n) => onSelect(n.id)}
            columns={[
              { id: "type", header: t("graph.col.type"), cell: (n) => typeWordOf(n) },
              {
                id: "name",
                header: t("graph.col.name"),
                cell: (n) =>
                  n.restricted === true ? nameOf(n) : <span className="tx-mono">{n.label}</span>,
              },
            ]}
          />
          <Table
            caption={t("graph.linksCaption")}
            rows={edges}
            rowKey={(e) => e.id}
            columns={[
              { id: "from", header: t("graph.col.from"), cell: (e) => nameOf(byId.get(e.from)) },
              { id: "to", header: t("graph.col.to"), cell: (e) => nameOf(byId.get(e.to)) },
              {
                id: "link",
                header: t("graph.col.link"),
                cell: (e) =>
                  e.kind === "same_as" ? (
                    <StrengthBadge strength={e.strength} />
                  ) : e.kind === "connected" ? (
                    t("graph.connected")
                  ) : (
                    t("restricted.title")
                  ),
              },
              {
                id: "state",
                header: t("graph.col.state"),
                cell: (e) => (e.kind === "same_as" ? t(`graph.state.${e.state}`) : ""),
              },
            ]}
          />
        </div>
      ) : (
        <div className="tx-graph__frame" ref={wrapRef}>
          <svg
            ref={svgRef}
            className="tx-graph__svg"
            role="group"
            aria-label={t("graph.canvasLabel", { nodes: nodes.length, links: edges.length })}
            viewBox={`0 0 ${width} ${height}`}
            width="100%"
            height={height}
          >
            <g ref={viewRef}>
              {edges.map((edge) => {
                const a = positions.get(edge.from);
                const b = positions.get(edge.to);
                if (!a || !b) return null;
                const look = edgeLook(edge);
                const word = edgeWords.get(edge.id);
                return (
                  <g
                    key={edge.id}
                    className="tx-graph__edge"
                    data-edge={edge.id}
                    data-style={look.name}
                    role="img"
                    aria-label={edgeAria(edge)}
                  >
                    <line
                      x1={a.x}
                      y1={a.y}
                      x2={b.x}
                      y2={b.y}
                      strokeWidth={look.width}
                      strokeDasharray={look.dash}
                    />
                    {word ? (
                      <text
                        className="tx-graph__edge-label"
                        x={word.x}
                        y={word.y}
                        textAnchor="middle"
                        dy="0.35em"
                      >
                        {edgeWordOf(edge)}
                      </text>
                    ) : null}
                  </g>
                );
              })}
              {nodes.map((node) => {
                const p = positions.get(node.id);
                if (!p) return null;
                const restricted = node.restricted === true;
                const shape: ShapeName = restricted
                  ? "restricted"
                  : (node as { type: GraphNodeType }).type;
                const label = nameOf(node);
                const selected = selectedId === node.id;
                const name = restricted
                  ? label
                  : t("graph.nodeName", { type: typeWordOf(node), label });
                return (
                  <g
                    key={node.id}
                    className="tx-graph__node"
                    data-node={node.id}
                    data-shape={SHAPE_NAME[shape]}
                    data-selected={selected ? "true" : undefined}
                    transform={`translate(${p.x} ${p.y})`}
                    role="button"
                    tabIndex={0}
                    aria-pressed={selected}
                    aria-label={name}
                    onClick={() => onSelect(node.id)}
                    onKeyDown={(e) => onKey(e, node.id)}
                    onFocus={() => {
                      setFocusedId(node.id);
                      bringIntoView(p.x, p.y);
                    }}
                    onBlur={() => setFocusedId(undefined)}
                  >
                    {shownLabels.has(node.id) && shortLabel(label) === label ? null : (
                      <title>{label}</title>
                    )}
                    <NodeBody shape={shape} selected={selected} />
                    {shownLabels.has(node.id) || focusedId === node.id ? (
                      <text
                        className="tx-graph__label"
                        y={restricted ? 42 : 46}
                        textAnchor="middle"
                        data-selected={selected ? "true" : undefined}
                      >
                        {shortLabel(labelText(node))}
                      </text>
                    ) : null}
                  </g>
                );
              })}
            </g>
          </svg>
        </div>
      )}
    </section>
  );
}

/** Admin only. Words + icon for every shape and line the canvas can draw. */
export function GraphLegend() {
  const { app, t } = useUi();
  if (app !== "admin") return null;

  const edgeRows: {
    key: "strong" | "possible" | "connected" | "restricted";
    look: EdgeLook;
    icon?: IconName;
  }[] = [
    { key: "strong", look: EDGE_LOOK["solid-heavy"], icon: "strong" },
    { key: "possible", look: EDGE_LOOK.dashed, icon: "possible" },
    { key: "connected", look: EDGE_LOOK.dotted },
    { key: "restricted", look: EDGE_LOOK["dashed-restricted"], icon: "restricted" },
  ];

  return (
    <section className="tx-legend" aria-label={t("graph.legend.title")}>
      <h2 className="tx-legend__title">{t("graph.legend.title")}</h2>
      <h3 className="tx-legend__head">{t("graph.legend.nodes")}</h3>
      <ul className="tx-legend__list">
        {[...GRAPH_NODE_TYPES, "restricted" as const].map((shape) => (
          <li key={shape} className="tx-legend__item" data-legend-node={shape}>
            <svg
              className="tx-legend__swatch"
              width={64}
              height={60}
              viewBox="-32 -30 64 60"
              aria-hidden="true"
              focusable="false"
            >
              <g className="tx-graph__node" data-shape={SHAPE_NAME[shape]}>
                <NodeBody shape={shape} />
              </g>
            </svg>
            <span>{t(`graph.legend.node.${shape}`)}</span>
          </li>
        ))}
      </ul>
      <h3 className="tx-legend__head">{t("graph.legend.edges")}</h3>
      <ul className="tx-legend__list">
        {edgeRows.map(({ key, look, icon }) => (
          <li key={key} className="tx-legend__item" data-legend-edge={key}>
            <svg
              className="tx-legend__swatch"
              width={64}
              height={24}
              viewBox="0 0 64 24"
              aria-hidden="true"
              focusable="false"
            >
              <g className="tx-graph__edge" data-style={look.name}>
                <line
                  x1={4}
                  y1={12}
                  x2={60}
                  y2={12}
                  strokeWidth={look.width}
                  strokeDasharray={look.dash}
                />
              </g>
            </svg>
            {icon ? <Icon name={icon} /> : null}
            <span>{t(`graph.legend.edge.${key}`)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
