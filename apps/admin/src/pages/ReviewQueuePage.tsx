import {
  Button,
  Checkbox,
  EmptyState,
  Loading,
  Pager,
  Select,
  StrengthBadge,
  Table,
} from "@tracex/ui";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AdminApi } from "../api";
import type { FailureResult } from "../api/resultKeys";
import type { components } from "../api/schema";
import { FailureView } from "../components/FailureView";
import { renderTemplate, groupPhone } from "../explain";
import { dateOnly } from "../format";
import { t, type AnyMessageKey, type Language } from "../i18n";
import { LinkPanel } from "./LinkPanel";

type Item = components["schemas"]["ReviewQueueItem"];
type EntityType = components["schemas"]["EntityType"];
type State = "SUGGESTED" | "REJECTED" | "UNDONE";
type SortId = "strength" | "item" | "waiting";

const PAGE = 50;
const BASE = "/review";
const SHOW: Record<string, State> = { rejected: "REJECTED", undone: "UNDONE" };
const SHOW_PARAM: Record<State, string | undefined> = {
  SUGGESTED: undefined,
  REJECTED: "rejected",
  UNDONE: "undone",
};
const TYPES: [EntityType, AnyMessageKey][] = [
  ["PERSON", "item.person"],
  ["PHONE", "item.phone"],
  ["ACCOUNT", "item.bank"],
  ["VEHICLE", "item.vehicle"],
  ["ORG", "item.org"],
];
const SORT_API: Record<SortId, "score" | "entity_type" | "waiting_since"> = {
  strength: "score",
  item: "entity_type",
  waiting: "waiting_since",
};

interface ReviewQueuePageProps {
  api: AdminApi;
  lang: Language;
  /** The browser address: the list is `/review`, one link is `/review/{id}`. */
  path: string;
  search: string;
  navigate: (to: string) => void;
}

type Counts = Record<State, number>;
type Load =
  | { state: "loading" }
  | { state: "failed"; result: FailureResult }
  | {
      state: "ready";
      items: Item[];
      next: string | null;
      counts: Counts;
    };

/**
 * A3 Review queue. The status switch, the Type and Area filters and the waiting-time filter all live in the
 * page address, so Back returns to them. ADMIN has no queue (D47): the menu hides it and the API answers 404,
 * which shows as the plain not-found state like any link the viewer cannot see (D65).
 */
export function ReviewQueuePage({ api, lang, path, search, navigate }: ReviewQueuePageProps) {
  const params = useMemo(() => new URLSearchParams(search), [search]);
  const linkId = path.startsWith(`${BASE}/`)
    ? decodeURIComponent(path.slice(BASE.length + 1))
    : undefined;
  const state: State = SHOW[params.get("show") ?? ""] ?? "SUGGESTED";
  const entityType = TYPES.find(([type]) => type === params.get("type"))?.[0];
  const area = params.get("area") ?? undefined;
  const old = params.get("old") === "1" && state === "SUGGESTED";

  const [sort, setSort] = useState<{ id: SortId; dir: "up" | "down" }>({
    id: "waiting",
    dir: "up",
  });
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [places, setPlaces] = useState<{ value: string; label: string }[]>([]);
  const [more, setMore] = useState(false);

  // Rejected and undone links list newest first.
  const direction = state === "SUGGESTED" ? sort.dir : "down";
  const queryFor = useCallback(
    (cursor?: string) => ({
      state,
      limit: PAGE,
      ...(entityType ? { entity_type: entityType } : {}),
      ...(area ? { district_id: area } : {}),
      ...(old ? { waiting_days_min: 7 } : {}),
      sort: SORT_API[state === "SUGGESTED" ? sort.id : "waiting"],
      order: direction === "up" ? ("asc" as const) : ("desc" as const),
      ...(cursor ? { cursor } : {}),
    }),
    [state, entityType, area, old, sort.id, direction],
  );

  const refresh = useCallback(async () => {
    setLoad({ state: "loading" });
    const [list, waiting, rejected, undone] = await Promise.all([
      api.client.listReviewQueue(queryFor()),
      api.client.listReviewQueue({ state: "SUGGESTED", limit: 1 }),
      api.client.listReviewQueue({ state: "REJECTED", limit: 1 }),
      api.client.listReviewQueue({ state: "UNDONE", limit: 1 }),
    ]);
    for (const result of [list, waiting, rejected, undone]) {
      if (result.kind !== "ok") return setLoad({ state: "failed", result });
    }
    const totalOf = (page: typeof waiting) =>
      page.kind === "ok" ? (page.data.total ?? page.data.items.length) : 0;
    const items = list.kind === "ok" ? list.data.items : [];
    setLoad({
      state: "ready",
      items,
      next: list.kind === "ok" ? list.data.next_cursor : null,
      counts: { SUGGESTED: totalOf(waiting), REJECTED: totalOf(rejected), UNDONE: totalOf(undone) },
    });
  }, [api, queryFor]);

  useEffect(() => {
    if (!linkId) void refresh();
  }, [refresh, linkId]);

  useEffect(() => {
    void api.client.listJurisdictions().then((result) => {
      if (result.kind !== "ok") return;
      setPlaces(
        result.data.items.flatMap((s) =>
          s.districts.map((d) => ({ value: d.district_id, label: d.name })),
        ),
      );
    });
  }, [api]);

  const go = (next: { show?: State; type?: string; area?: string; old?: boolean }) => {
    const q = new URLSearchParams();
    const show = SHOW_PARAM[next.show ?? state];
    if (show) q.set("show", show);
    const type = "type" in next ? next.type : entityType;
    if (type) q.set("type", type);
    const place = "area" in next ? next.area : area;
    if (place) q.set("area", place);
    const wait = "old" in next ? next.old : old;
    if (wait && (next.show ?? state) === "SUGGESTED") q.set("old", "1");
    const text = q.toString();
    navigate(text ? `${BASE}?${text}` : BASE);
  };

  const here = search; // keeps the filters when a link is opened and closed again
  const back = () => navigate(`${BASE}${here}`);
  const openLink = (id: string) => navigate(`${BASE}/${encodeURIComponent(id)}${here}`);

  if (linkId) {
    const ids = load.state === "ready" ? load.items.map((item) => item.link_id) : [];
    const index = ids.indexOf(linkId);
    return (
      <LinkPanel
        key={linkId}
        api={api}
        lang={lang}
        linkId={linkId}
        {...(index >= 0
          ? { position: { n: index + 1, total: ids.length, nextId: ids[index + 1] } }
          : {})}
        onBack={back}
        onOpen={openLink}
      />
    );
  }

  const counts = load.state === "ready" ? load.counts : undefined;
  const choice = (which: State, key: AnyMessageKey) => (
    <Button
      key={which}
      variant="secondary"
      {...(state === which ? { icon: "confirm" as const } : {})}
      aria-pressed={state === which}
      onClick={() => go({ show: which })}
    >
      {t(key, lang, { n: counts?.[which] ?? 0 })}
    </Button>
  );

  const filtered = Boolean(entityType || area || old);
  const loadMore = async (cursor: string) => {
    setMore(true);
    const page = await api.client.listReviewQueue(queryFor(cursor));
    if (page.kind !== "ok") {
      setMore(false);
      return setLoad({ state: "failed", result: page });
    }
    setMore(false);
    setLoad((now) =>
      now.state === "ready"
        ? {
            ...now,
            items: [...now.items, ...page.data.items],
            next: page.data.next_cursor,
          }
        : now,
    );
  };

  const itemText = (item: Item) => {
    const end = item.ends[0]?.entity;
    const key = TYPES.find(([type]) => type === item.entity_type)?.[1];
    const value = end
      ? item.entity_type === "PHONE"
        ? groupPhone(end.display_value)
        : end.display_value
      : "";
    return `${key ? t(key, lang) : ""} ${value}`.trim();
  };

  const decided = state !== "SUGGESTED";
  const columnsFor = () => {
    const caseColumns = [
      {
        id: "caseA",
        header: t("queue.col.caseA", lang),
        cell: (r: Item) => r.ends[0]?.case.case_number,
      },
      {
        id: "caseB",
        header: t("queue.col.caseB", lang),
        cell: (r: Item) => r.ends[1]?.case.case_number,
      },
    ];
    const item = {
      id: "item",
      header: t("queue.col.item", lang),
      sortable: !decided,
      cell: itemText,
    };
    if (!decided) {
      return [
        {
          id: "strength",
          header: t("queue.col.strength", lang),
          sortable: true,
          cell: (r: Item) => (
            <StrengthBadge
              strength={r.state === "AUTO" ? "strong" : "possible"}
              adminScore={r.score}
            />
          ),
        },
        item,
        ...caseColumns,
        {
          id: "reason",
          header: t("queue.col.mainReason", lang),
          cell: (r: Item) =>
            renderTemplate(r.main_reason.template_key, r.main_reason.params, lang) ?? "",
        },
        {
          id: "waiting",
          header: t("queue.col.waitingSince", lang),
          numeric: true,
          sortable: true,
          cell: (r: Item) => dateOnly(r.waiting_since, lang),
        },
      ];
    }
    // The queue does not say who decided or why; that is in the opened link. `updated_at` is the last change
    // of any kind, so the column says so and is never called a decision date.
    return [
      item,
      ...caseColumns,
      {
        id: "changed",
        header: t("queue.col.lastChange", lang),
        numeric: true,
        cell: (r: Item) => dateOnly(r.updated_at, lang),
      },
    ];
  };

  return (
    <div className="admin-page">
      <h2 className="admin-panel-title">{t("queue.title", lang)}</h2>
      <div className="admin-switch" role="group" aria-label={t("queue.show", lang)}>
        <span className="admin-switch__label">{t("queue.show", lang)}</span>
        {choice("SUGGESTED", "queue.filter.waiting")}
        {choice("REJECTED", "queue.filter.rejected")}
        {choice("UNDONE", "queue.filter.undone")}
      </div>
      <div className="admin-filters">
        <Select
          label={t("queue.filter.type", lang)}
          value={entityType ?? ""}
          options={[
            { value: "", label: t("queue.type.all", lang) },
            ...TYPES.map(([value, key]) => ({ value, label: t(key, lang) })),
          ]}
          onChange={(value) => go({ type: value })}
        />
        <Select
          label={t("queue.filter.area", lang)}
          value={area ?? ""}
          options={[{ value: "", label: t("shell.noArea", lang) }, ...places]}
          onChange={(value) => go({ area: value })}
        />
        {state === "SUGGESTED" ? (
          <Checkbox
            label={t("queue.filter.waitingLong", lang)}
            checked={old}
            onChange={(checked) => go({ old: checked })}
          />
        ) : null}
      </div>
      {load.state === "loading" ? <Loading /> : null}
      {load.state === "failed" ? (
        <FailureView result={load.result} lang={lang} onRetry={() => void refresh()} />
      ) : null}
      {load.state === "ready" ? (
        <>
          {decided ? (
            <p className="admin-body">
              {t(state === "REJECTED" ? "queue.rejected.intro" : "queue.undone.intro", lang)}
            </p>
          ) : null}
          {load.items.length === 0 ? (
            <EmptyState
              title={t(
                filtered
                  ? "queue.empty.filtered"
                  : state === "SUGGESTED"
                    ? "queue.empty.waiting"
                    : state === "REJECTED"
                      ? "queue.empty.rejected"
                      : "queue.empty.undone",
                lang,
              )}
              hint=""
              {...(filtered
                ? {
                    action: (
                      <Button
                        variant="secondary"
                        onClick={() => go({ type: "", area: "", old: false })}
                      >
                        {t("queue.clearFilters", lang)}
                      </Button>
                    ),
                  }
                : {})}
            />
          ) : (
            <>
              <Table
                caption={t("queue.title", lang)}
                rows={load.items}
                rowKey={(row) => row.link_id}
                columns={columnsFor()}
                onOpenRow={(row) => openLink(row.link_id)}
                {...(state === "SUGGESTED"
                  ? { sort: { columnId: sort.id, direction: sort.dir } }
                  : {})}
                onSort={(columnId) => {
                  if (state !== "SUGGESTED") return;
                  const id = columnId as SortId;
                  setSort((now) => ({
                    id,
                    dir: now.id === id && now.dir === "up" ? "down" : "up",
                  }));
                }}
              />
              {load.next ? (
                more ? (
                  <Loading />
                ) : (
                  <Pager
                    shown={load.items.length}
                    total={Math.max(counts?.[state] ?? 0, load.items.length + 1)}
                    onMore={() => void loadMore(load.next as string)}
                  />
                )
              ) : null}
            </>
          )}
        </>
      ) : null}
    </div>
  );
}
