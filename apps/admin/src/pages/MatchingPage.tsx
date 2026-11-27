import { Button, Loading, Message } from "@tracex/ui";
import { useCallback, useEffect, useState } from "react";

import type { AdminApi } from "../api";
import type { FailureResult } from "../api/resultKeys";
import type { components } from "../api/schema";
import { FailureView } from "../components/FailureView";
import { dateTime } from "../format";
import { t, type Language } from "../i18n";

type Run = components["schemas"]["MatchRun"];
type Totals = components["schemas"]["LinkTotals"];

interface MatchingPageProps {
  api: AdminApi;
  lang: Language;
  /** How often a running run is checked. Tests pass a small number. */
  pollMs?: number;
}

type Load =
  | { state: "loading" }
  | { state: "failed"; result: FailureResult }
  | { state: "ready"; last: Run | undefined; totals: Totals; running: Run | undefined };

type Outcome = { kind: "finished"; run: Run } | { kind: "failed" } | undefined;

/**
 * A2 Matching. The contract returns only the status and the totals of links made (auto and suggested), so
 * that is all this page shows: no progress count, no band or per-pair numbers (D49), and no stop button
 * because a run cannot be stopped.
 */
export function MatchingPage({ api, lang, pollMs = 3000 }: MatchingPageProps) {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [running, setRunning] = useState<Run | undefined>();
  const [outcome, setOutcome] = useState<Outcome>();
  const [problem, setProblem] = useState<FailureResult | undefined>();
  const [starting, setStarting] = useState(false);

  const refresh = useCallback(async () => {
    const [runs, totals] = await Promise.all([
      api.client.listMatchingRuns({ limit: 5 }),
      api.client.getLinkTotals(),
    ]);
    if (runs.kind !== "ok") return setLoad({ state: "failed", result: runs });
    if (totals.kind !== "ok") return setLoad({ state: "failed", result: totals });
    const items = runs.data.items;
    const current = items.find((run) => run.status === "RUNNING");
    setRunning(current);
    setLoad({
      state: "ready",
      last: items.find((run) => run.status === "SUCCEEDED"),
      totals: totals.data,
      running: current,
    });
  }, [api]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const runId = running?.run_id;
  const [pollTick, setPollTick] = useState(0);
  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      void (async () => {
        const result = await api.client.getMatchingRun(runId);
        if (cancelled) return;
        if (result.kind !== "ok") {
          setProblem(result);
          return;
        }
        if (result.data.status === "RUNNING") {
          setPollTick((n) => n + 1);
          return;
        }
        setRunning(undefined);
        setOutcome(
          result.data.status === "SUCCEEDED"
            ? { kind: "finished", run: result.data }
            : { kind: "failed" },
        );
        await refresh();
      })();
    }, pollMs);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [api, runId, pollMs, pollTick, refresh]);

  const start = async () => {
    setStarting(true);
    setProblem(undefined);
    setOutcome(undefined);
    const result = await api.client.startMatchingRun();
    setStarting(false);
    if (result.kind !== "ok") {
      setProblem(result);
      return;
    }
    setRunning(result.data);
  };

  if (load.state === "loading") return <Loading label={t("loading.default", lang)} />;
  if (load.state === "failed") {
    return (
      <FailureView
        result={load.result}
        lang={lang}
        onRetry={() => {
          setLoad({ state: "loading" });
          void refresh();
        }}
      />
    );
  }

  const { last, totals } = load;
  const busy = running !== undefined || starting;
  return (
    <div className="admin-page">
      <h2>{t("matching.title", lang)}</h2>
      <p>
        {last
          ? t("matching.last", lang, {
              date: dateTime(last.finished_at ?? last.started_at, lang),
              strong: last.auto_created,
              possible: last.suggested_created,
            })
          : t("matching.never", lang)}
      </p>
      <p>
        {t("matching.totals", lang, {
          strong: totals.auto,
          possible: totals.waiting,
          confirmed: totals.confirmed,
        })}
      </p>
      <div className="admin-actions">
        <Button variant="primary" icon="alsoAppearsIn" disabled={busy} onClick={() => void start()}>
          {t("matching.start", lang)}
        </Button>
      </div>
      {problem ? (
        <FailureView
          result={problem}
          lang={lang}
          {...(runId ? { onRetry: () => setPollTick((n) => n + 1) } : {})}
        />
      ) : null}
      {running ? (
        <Message kind="info">
          <span>{t("matching.running", lang)}</span> <span>{t("matching.noStop", lang)}</span>
        </Message>
      ) : null}
      {outcome?.kind === "finished" ? (
        <Message kind="success">
          {t("matching.finished", lang, { n: outcome.run.suggested_created })}
        </Message>
      ) : null}
      {outcome?.kind === "failed" ? (
        <Message kind="error">{t("matching.failed", lang)}</Message>
      ) : null}
    </div>
  );
}
