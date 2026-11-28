import {
  Button,
  GraphCanvas,
  GraphLegend,
  Loading,
  Message,
  RestrictedCard,
  TextField,
  type GraphEdge,
  type GraphNode,
} from "@tracex/ui";
import { useMemo, useRef, useState, type FormEvent } from "react";

import type { AdminApi } from "../api";
import type { FailureResult } from "../api/resultKeys";
import type { components } from "../api/schema";
import { FailureView } from "../components/FailureView";
import { t, type Language } from "../i18n";
import type { Role } from "../nav";
import { LinkPanel } from "./LinkPanel";

type EntitySummary = components["schemas"]["EntitySummary"];
type GraphResponse = components["schemas"]["GraphResponse"];
type GraphEdgeData = components["schemas"]["GraphEdge"];
type EntityType = EntitySummary["type"];

/** The canvas draws five shapes; the API's ACCOUNT is the bank account shape. */
const SHAPE_OF: Record<EntityType, "person" | "phone" | "bank" | "vehicle" | "org"> = {
  PERSON: "person",
  PHONE: "phone",
  ACCOUNT: "bank",
  VEHICLE: "vehicle",
  ORG: "org",
};

/** The most the API may send, and the most the picture holds (DESIGN_RULES section 12). */
const CAP = 150;

/** GET /search/entities: `q` is 2 to 100 characters. */
const QUERY_MIN = 2;
const QUERY_MAX = 100;

type Search =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "failed"; result: FailureResult }
  | { state: "empty" }
  | { state: "results"; items: EntitySummary[]; more: boolean };

type Network =
  | { state: "none" }
  | { state: "loading" }
  | { state: "failed"; result: FailureResult; entityId: string }
  | { state: "ready"; data: GraphResponse };

/** A stub's own id never reaches the page: the picture names it by its place in the list. */
const stubNodeId = (index: number) => `stub-${index + 1}`;

/** A rejected or undone link is not part of the network. */
const isActive = (edge: GraphEdgeData) =>
  edge.state === "AUTO" || edge.state === "CONFIRMED" || edge.state === "SUGGESTED";

function toCanvas(data: GraphResponse): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const nodes: GraphNode[] = data.nodes.map(({ entity }) => ({
    id: entity.entity_id,
    type: SHAPE_OF[entity.type],
    label: entity.display_value,
  }));
  const edges: GraphEdge[] = data.edges.filter(isActive).map((e) => ({
    id: e.link_id,
    from: e.from_entity_id,
    to: e.to_entity_id,
    kind: "same_as" as const,
    strength: e.state === "SUGGESTED" ? ("possible" as const) : ("strong" as const),
    state:
      e.state === "AUTO"
        ? ("auto" as const)
        : e.state === "CONFIRMED"
          ? ("confirmed" as const)
          : ("suggested" as const),
  }));
  data.stubs.forEach((stub, index) => {
    nodes.push({ id: stubNodeId(index), restricted: true });
    edges.push({
      id: `stub-link-${index + 1}`,
      from: stub.near_entity_id,
      to: stubNodeId(index),
      kind: "restricted",
    });
  });
  return { nodes, edges };
}

export interface GraphPageProps {
  api: AdminApi;
  lang: Language;
  role: Role;
}

/**
 * A8 Network graph. An administrator gets no data here: the API answers 404 for that role (D47), so the
 * page does not ask at all.
 */
export function GraphPage({ api, lang, role }: GraphPageProps) {
  if (role === "ADMIN") {
    return <Message kind="info">{t("graphPage.notAvailable", lang)}</Message>;
  }
  return <GraphWork api={api} lang={lang} />;
}

function GraphWork({ api, lang }: { api: AdminApi; lang: Language }) {
  const [search, setSearch] = useState<Search>({ state: "idle" });
  const [network, setNetwork] = useState<Network>({ state: "none" });
  const [selected, setSelected] = useState<string | undefined>();
  const [query, setQuery] = useState("");
  const [queryError, setQueryError] = useState<string | undefined>();
  const [linkId, setLinkId] = useState<string | undefined>();
  /** Only the newest request may change the screen. */
  const latest = useRef(0);

  const showNetwork = async (entityId: string) => {
    const turn = ++latest.current;
    setSelected(undefined);
    setNetwork({ state: "loading" });
    const result = await api.client.getEntityGraph(entityId, { depth: 1, limit: CAP });
    if (turn !== latest.current) return;
    setNetwork(
      result.kind === "ok"
        ? { state: "ready", data: result.data }
        : { state: "failed", result, entityId },
    );
  };

  const runSearch = async (text: string) => {
    const words = text.trim();
    if (words.length < QUERY_MIN) {
      latest.current++;
      setNetwork({ state: "none" });
      setSearch({ state: "idle" });
      setQueryError(
        words.length === 0
          ? t("common.fillIn", lang, { field: t("graphPage.search", lang) })
          : t("graphPage.tooShort", lang),
      );
      return;
    }
    setQueryError(undefined);
    const turn = ++latest.current;
    setNetwork({ state: "none" });
    setSelected(undefined);
    setSearch({ state: "loading" });
    const result = await api.client.searchEntities({ q: words });
    if (turn !== latest.current) return;
    if (result.kind !== "ok") return setSearch({ state: "failed", result });
    const items = result.data.items;
    if (items.length === 0) return setSearch({ state: "empty" });
    setSearch({ state: "results", items, more: result.data.next_cursor !== null });
    const only = items.length === 1 ? items[0] : undefined;
    if (only) void showNetwork(only.entity_id);
  };

  const drawn = useMemo(
    () => (network.state === "ready" ? toCanvas(network.data) : undefined),
    [network],
  );

  // The same explanation panel as the review queue. It reads the link only now, when someone opens it (D69).
  if (linkId) {
    return (
      <LinkPanel
        api={api}
        lang={lang}
        linkId={linkId}
        onBack={() => setLinkId(undefined)}
        onOpen={setLinkId}
      />
    );
  }

  const nameOf = (id: string) =>
    network.state === "ready"
      ? (network.data.nodes.find((n) => n.entity.entity_id === id)?.entity.display_value ?? "")
      : "";

  const panel = () => {
    if (network.state !== "ready" || !selected) {
      return <p className="admin-body">{t("graphPage.nothingSelected", lang)}</p>;
    }
    const stub = network.data.stubs.find((_, i) => stubNodeId(i) === selected);
    if (stub) {
      // Only the restricted card, built from the viewer's own item. GET /stubs is not called (D69).
      const near = network.data.nodes.find((n) => n.entity.entity_id === stub.near_entity_id);
      if (!near) return null;
      return (
        <RestrictedCard
          itemType={SHAPE_OF[near.entity.type]}
          itemValue={near.entity.display_value}
          emphasis="secondary"
        />
      );
    }
    const entity = network.data.nodes.find((n) => n.entity.entity_id === selected)?.entity;
    if (!entity) return null;
    const mine = network.data.edges.filter(
      (e) => isActive(e) && (e.from_entity_id === selected || e.to_entity_id === selected),
    );
    return (
      <div className="admin-detail">
        <p className="admin-body">
          {t(`item.${SHAPE_OF[entity.type]}`, lang)}:{" "}
          <span className="admin-mono">{entity.display_value}</span>
        </p>
        <h3 className="admin-panel-title">{t("graphPage.links", lang)}</h3>
        {mine.length === 0 ? (
          <p className="admin-body">{t("graphPage.noLinks", lang)}</p>
        ) : (
          <ul className="admin-plain">
            {mine.map((e) => {
              const other = e.from_entity_id === selected ? e.to_entity_id : e.from_entity_id;
              const strength = e.state === "SUGGESTED" ? "strength.possible" : "strength.strong";
              return (
                <li key={e.link_id}>
                  <span className="admin-block">
                    {t("graphPage.linkRow", lang, {
                      name: nameOf(other),
                      strength: t(strength, lang),
                    })}
                  </span>
                  <Button variant="secondary" onClick={() => setLinkId(e.link_id)}>
                    {t("graphPage.seeWhy", lang)}
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    );
  };

  return (
    <div className="admin-page">
      <form
        className="admin-form"
        role="search"
        noValidate
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          void runSearch(query);
        }}
      >
        <TextField
          label={t("graphPage.search", lang)}
          value={query}
          maxLength={QUERY_MAX}
          onChange={setQuery}
          {...(queryError ? { error: queryError } : {})}
        />
        <div className="admin-actions">
          <Button type="submit" variant="primary" icon="search">
            {t("graphPage.show", lang)}
          </Button>
        </div>
      </form>
      {search.state === "loading" ? <Loading label={t("loading.default", lang)} /> : null}
      {search.state === "failed" ? <FailureView result={search.result} lang={lang} /> : null}
      {search.state === "empty" ? (
        <p className="admin-body">{t("common.nothingFound", lang)}</p>
      ) : null}
      {search.state === "results" && search.items.length > 1 ? (
        <section aria-label={t("graphPage.results", lang)}>
          <h2 className="admin-panel-title">{t("graphPage.results", lang)}</h2>
          {search.more ? (
            <Message kind="info">
              {t("graphPage.firstOnly", lang, { n: search.items.length })}
            </Message>
          ) : null}
          <ul className="admin-plain">
            {search.items.map((item) => (
              <li key={item.entity_id}>
                <span className="admin-block">
                  {t(`item.${SHAPE_OF[item.type]}`, lang)}:{" "}
                  <span className="admin-mono">{item.display_value}</span>
                </span>
                <Button variant="secondary" onClick={() => void showNetwork(item.entity_id)}>
                  {t("graphPage.showRow", lang)}
                </Button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {network.state === "loading" ? <Loading label={t("loading.default", lang)} /> : null}
      {network.state === "failed" ? (
        <FailureView
          result={network.result}
          lang={lang}
          {...(network.result.kind === "notFound"
            ? {}
            : { onRetry: () => void showNetwork(network.entityId) })}
        />
      ) : null}
      {network.state === "ready" && drawn ? (
        <div className="admin-graph">
          <GraphLegend />
          <GraphCanvas
            nodes={drawn.nodes}
            edges={drawn.edges}
            {...(selected ? { selectedId: selected } : {})}
            onSelect={setSelected}
            truncated={network.data.truncated}
          />
          <section className="admin-graph__panel" aria-label={t("graphPage.selected", lang)}>
            <h2 className="admin-panel-title">{t("graphPage.selected", lang)}</h2>
            {panel()}
          </section>
        </div>
      ) : null}
    </div>
  );
}
