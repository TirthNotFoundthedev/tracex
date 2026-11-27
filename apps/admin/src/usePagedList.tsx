import { Button, EmptyState, Loading, Pager } from "@tracex/ui";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import type { ApiResult } from "./api/http";
import type { FailureResult } from "./api/resultKeys";
import { FailureView } from "./components/FailureView";
import { t, type Language } from "./i18n";

export interface PageShape<T> {
  items: T[];
  next_cursor: string | null;
  total?: number | undefined;
}

export type ListLoad<T> =
  | { state: "loading" }
  | { state: "failed"; result: FailureResult }
  | { state: "ready"; items: T[]; next: string | null; total: number | undefined };

/**
 * One paged list. A refresh starts a new generation, and an answer that belongs to an older one is
 * dropped, so a slow answer never overwrites a newer list (the same goes for Show more).
 */
export function usePagedList<T>(fetchPage: (cursor?: string) => Promise<ApiResult<PageShape<T>>>) {
  const [load, setLoad] = useState<ListLoad<T>>({ state: "loading" });
  const [more, setMore] = useState(false);
  const [moreFailure, setMoreFailure] = useState<FailureResult | undefined>();
  const generation = useRef(0);

  const refresh = useCallback(async () => {
    const mine = ++generation.current;
    setLoad({ state: "loading" });
    setMore(false);
    setMoreFailure(undefined);
    const result = await fetchPage();
    if (mine !== generation.current) return;
    if (result.kind !== "ok") return setLoad({ state: "failed", result });
    setLoad({
      state: "ready",
      items: result.data.items,
      next: result.data.next_cursor,
      total: result.data.total,
    });
  }, [fetchPage]);

  useEffect(() => {
    void refresh();
    const counter = generation;
    return () => {
      counter.current++;
    };
  }, [refresh]);

  const loadMore = async (cursor: string) => {
    const mine = generation.current;
    setMore(true);
    setMoreFailure(undefined);
    const result = await fetchPage(cursor);
    if (mine !== generation.current) return;
    setMore(false);
    // The rows already loaded stay; the failure shows under them.
    if (result.kind !== "ok") return setMoreFailure(result);
    setLoad((now) =>
      now.state === "ready"
        ? {
            state: "ready",
            items: [...now.items, ...result.data.items],
            next: result.data.next_cursor,
            total: result.data.total ?? now.total,
          }
        : now,
    );
  };

  return { load, more, moreFailure, refresh, loadMore };
}

export type PagedList<T> = ReturnType<typeof usePagedList<T>>;

interface PagedViewProps<T> {
  lang: Language;
  list: PagedList<T>;
  empty: string;
  /** The loaded rows. Not called while loading, failed or empty. */
  children: (items: T[]) => ReactNode;
}

/** Loading, failure with Try again, empty, the rows, and "Show more" under them. */
export function PagedView<T>({ lang, list, empty, children }: PagedViewProps<T>) {
  const { load, more, moreFailure, refresh, loadMore } = list;
  if (load.state === "loading") return <Loading label={t("loading.default", lang)} />;
  if (load.state === "failed") {
    return <FailureView result={load.result} lang={lang} onRetry={() => void refresh()} />;
  }
  if (load.items.length === 0) return <EmptyState title={empty} hint="" />;
  const next = load.next;
  return (
    <>
      {children(load.items)}
      {next ? (
        more ? (
          <Loading label={t("loading.default", lang)} />
        ) : (
          <>
            {moreFailure ? (
              <FailureView result={moreFailure} lang={lang} onRetry={() => void loadMore(next)} />
            ) : null}
            {load.total !== undefined ? (
              <Pager
                shown={load.items.length}
                total={load.total}
                onMore={() => void loadMore(next)}
              />
            ) : (
              <Button variant="secondary" onClick={() => void loadMore(next)}>
                {t("pager.more", lang)}
              </Button>
            )}
          </>
        )
      ) : null}
    </>
  );
}
