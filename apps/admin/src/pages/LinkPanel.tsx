import {
  Badge,
  Button,
  ConfirmStep,
  EvidenceSource,
  Loading,
  Message,
  MoreDetail,
  ReasonList,
  StrengthBadge,
} from "@tracex/ui";
import { useCallback, useEffect, useState } from "react";

import type { AdminApi } from "../api";
import type { ApiResult } from "../api/http";
import type { FailureResult } from "../api/resultKeys";
import type { components } from "../api/schema";
import { FailureView } from "../components/FailureView";
import { panelContent, groupPhone } from "../explain";
import { dateOnly } from "../format";
import { t, type Language, type MessageKey } from "../i18n";
import { lastDecision, reopeningOf, roleLabel, type Actor } from "../linkHistory";

type LinkDetail = components["schemas"]["LinkDetail"];
type Explanation = components["schemas"]["Explanation"];

/** Same limits as the contract for a decision reason (LinkReasonRequest). */
const REASON_MIN = 3;
const REASON_MAX = 1000;

type Outcome = "confirmed" | "rejected" | "undone" | "reopened";
type View =
  | { name: "panel" }
  | { name: "reject" | "undo" | "reopen" }
  | { name: "decided"; outcome: Outcome };

type Load =
  | { state: "loading" }
  | { state: "failed"; result: FailureResult }
  | { state: "ready"; detail: LinkDetail; explanation: Explanation };

export interface LinkPanelProps {
  api: AdminApi;
  lang: Language;
  linkId: string;
  /** Where this link stands in the list being worked through, when it is in it. */
  position?: { n: number; total: number; nextId: string | undefined };
  onBack: () => void;
  onOpen: (linkId: string) => void;
}

/** The sentence for a viewer who cannot decide (design-flows O6). Nothing when no decision is legal now. */
function blockedKey(detail: LinkDetail): MessageKey | undefined {
  switch (detail.decision_block) {
    case "CROSS_AREA_SENIOR_ONLY":
      return "queue.block.twoAreas";
    case "COVERAGE_INCOMPLETE":
      return "queue.block.notBothAreas";
    case "GRANT_READ_ONLY":
      return "queue.block.notBothCases";
    case "ROLE_VIEW_ONLY":
      return detail.state === "REJECTED" || detail.state === "UNDONE"
        ? "queue.noRight.role"
        : "queue.block.viewOnly";
    default:
      return undefined;
  }
}

const displayValue = (type: string, value: string) =>
  type === "PHONE" ? groupPhone(value) : value;

/**
 * A3b and A3d: the explanation panel with admin detail open, the history of a decided or reopened link,
 * and the decisions. Buttons come from `allowed_actions` and the line from `decision_block`; the screen
 * adds no role or state check of its own, so the API stays the one place that decides.
 */
export function LinkPanel({ api, lang, linkId, position, onBack, onOpen }: LinkPanelProps) {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [view, setView] = useState<View>({ name: "panel" });
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<FailureResult | undefined>();

  const refresh = useCallback(async () => {
    setLoad({ state: "loading" });
    setFailure(undefined);
    setView({ name: "panel" });
    const [detail, explanation] = await Promise.all([
      api.client.getLink(linkId),
      api.client.getLinkExplanation(linkId),
    ]);
    if (detail.kind !== "ok") return setLoad({ state: "failed", result: detail });
    if (explanation.kind !== "ok") return setLoad({ state: "failed", result: explanation });
    setLoad({ state: "ready", detail: detail.data, explanation: explanation.data });
  }, [api, linkId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const history = load.state === "ready" ? load.detail.history : [];
  const reopening = reopeningOf(history);
  const decision = lastDecision(history);

  if (load.state === "loading") return <Loading label={t("loading.default", lang)} />;
  if (load.state === "failed") {
    const gone = load.result.kind === "notFound";
    return (
      <div className="admin-page">
        <FailureView
          result={load.result}
          lang={lang}
          {...(gone ? {} : { onRetry: () => void refresh() })}
        />
        <div className="admin-actions">
          <Button variant="secondary" onClick={onBack}>
            {t("queue.backToList", lang)}
          </Button>
        </div>
      </div>
    );
  }

  const { detail, explanation } = load;
  async function decide(
    outcome: Outcome,
    run: () => Promise<ApiResult<LinkDetail>>,
  ): Promise<void> {
    setBusy(true);
    setFailure(undefined);
    const result = await run();
    setBusy(false);
    if (result.kind === "ok") setView({ name: "decided", outcome });
    else setFailure(result);
  }

  const nameOf = (actor: Actor | null | undefined): string =>
    actor ? actor.name : t("queue.someone", lang);

  const problem = failure ? (
    <div className="admin-page">
      <FailureView result={failure} lang={lang} />
      <div className="admin-actions">
        {failure.kind === "conflict" ? (
          <Button variant="secondary" onClick={onBack}>
            {t("queue.showList", lang)}
          </Button>
        ) : failure.kind === "notFound" ? (
          <Button variant="secondary" onClick={onBack}>
            {t("queue.backToList", lang)}
          </Button>
        ) : null}
      </div>
    </div>
  ) : null;
  // A link that is gone, or changed under us, has nothing more to do here.
  if (failure && (failure.kind === "notFound" || failure.kind === "conflict")) return problem;

  if (view.name === "reject" || view.name === "undo" || view.name === "reopen") {
    const reasonLabel = {
      reject: "reject.reasonLabel",
      undo: "undo.reasonLabel",
      reopen: "queue.reopen.reasonLabel",
    } as const;
    const copy = {
      reject: { title: "queue.reject.title", body: "queue.reject.body", yes: "queue.reject.yes" },
      undo: { title: "queue.undo.title", body: "queue.undo.body", yes: "queue.undo.yes" },
      reopen: { title: "queue.reopen.title", body: "queue.reopen.body", yes: "queue.reopen.yes" },
    } as const;
    const run = (reason: string) => {
      const body = { reason, expected_state: detail.state };
      if (view.name === "reject")
        return decide("rejected", () => api.client.rejectLink(linkId, body));
      if (view.name === "undo") return decide("undone", () => api.client.undoLink(linkId, body));
      return decide("reopened", () => api.client.reopenLink(linkId, body));
    };
    return (
      <div className="admin-page">
        {problem}
        {busy ? (
          <Loading label={t("queue.saving", lang)} />
        ) : (
          <ConfirmStep
            title={t(copy[view.name].title, lang)}
            body={t(copy[view.name].body, lang)}
            confirmLabel={t(copy[view.name].yes, lang)}
            {...(view.name === "reject"
              ? { confirmIcon: "reject" as const, confirmVariant: "danger" as const }
              : { cancelVariant: "secondary" as const })}
            reason={{ label: t(reasonLabel[view.name], lang), min: REASON_MIN, max: REASON_MAX }}
            onConfirm={(reason) => void run(reason ?? "")}
            onCancel={() => setView({ name: "panel" })}
          />
        )}
      </div>
    );
  }

  if (view.name === "decided") {
    return (
      <div className="admin-page">
        <Message kind={view.outcome === "rejected" ? "info" : "success"}>
          {view.outcome === "reopened"
            ? t("queue.reopen.done", lang)
            : t(`queue.decided.${view.outcome}`, lang)}
        </Message>
        <div className="admin-actions">
          {view.outcome === "reopened" ? (
            <Button variant="primary" onClick={() => void refresh()}>
              {t("queue.reopen.openIt", lang)}
            </Button>
          ) : (
            <Button
              variant="primary"
              onClick={() => (position?.nextId ? onOpen(position.nextId) : onBack())}
            >
              {position?.nextId ? t("queue.next", lang) : t("queue.backToList", lang)}
            </Button>
          )}
          {view.outcome === "reopened" || position?.nextId ? (
            <Button variant="secondary" onClick={onBack}>
              {t("queue.backToList", lang)}
            </Button>
          ) : null}
        </div>
      </div>
    );
  }

  const caseNumbers: Record<string, string> = {};
  for (const end of detail.ends) caseNumbers[end.case.case_id] = end.case.case_number;
  const content = panelContent(explanation, lang, caseNumbers, t("item.case", lang));
  const allowed = new Set(detail.allowed_actions);
  const canConfirm = allowed.has("CONFIRM");
  const canReject = allowed.has("REJECT");
  const canUndo = allowed.has("UNDO");
  const canReopen = allowed.has("REOPEN");
  const anyAction = canConfirm || canReject || canUndo || canReopen;
  const blocked = anyAction ? undefined : blockedKey(detail);
  const decided = detail.state === "REJECTED" || detail.state === "UNDONE";
  const suggested = detail.state === "SUGGESTED";
  const strength = detail.state === "AUTO" || detail.state === "CONFIRMED" ? "strong" : "possible";
  const primary = canConfirm ? "confirm" : canUndo ? "undo" : canReopen ? "reopen" : undefined;
  const variant = (which: string) => (primary === which ? "primary" : "secondary");
  const record = (id: string) => explanation.records.find((r) => r.case_id === id);

  return (
    <div className="admin-page">
      {problem}
      {position ? (
        <p className="admin-hint">
          {t("queue.position", lang, { n: position.n, total: position.total })}
        </p>
      ) : null}
      <h2 className="admin-panel-title">
        {t(
          decided
            ? detail.state === "REJECTED"
              ? "queue.panel.rejected"
              : "queue.panel.undone"
            : strength === "strong"
              ? "queue.panel.strong"
              : "queue.panel.possible",
          lang,
        )}
      </h2>
      {decided && decision ? (
        <Message kind="info">
          <span className="admin-block">
            {(() => {
              const actor = decision.actor;
              const date = dateOnly(decision.at, lang);
              const key = decision.state === "REJECTED" ? "queue.rejected" : "queue.undone";
              return actor
                ? t(`${key}.history`, lang, {
                    name: actor.name,
                    role: roleLabel(actor.role, lang),
                    date,
                  })
                : t(`${key}.historyNoName`, lang, { date });
            })()}
          </span>
          {decision.reason ? (
            <span className="admin-block">
              {t("queue.history.reason", lang, { reason: decision.reason })}
            </span>
          ) : null}
        </Message>
      ) : null}
      {!decided ? (
        <div className="admin-badges">
          <StrengthBadge strength={strength} adminScore={detail.score} />
          {reopening ? <Badge icon="pending">{t("queue.tag.reopened", lang)}</Badge> : null}
        </div>
      ) : null}
      {reopening ? (
        <>
          <p className="admin-body">
            {t("queue.reopened.history", lang, {
              name: nameOf(reopening.actor),
              date: dateOnly(reopening.at, lang),
              name2: nameOf(reopening.earlier?.actor),
              date2: reopening.earlier ? dateOnly(reopening.earlier.at, lang) : "",
            })}
          </p>
          <p className="admin-body">{t("queue.reopened.rerun", lang)}</p>
        </>
      ) : null}
      <ul className="admin-plain">
        {detail.ends.map((end) => (
          <li key={end.entity.entity_id}>
            <span className="admin-mono">
              {displayValue(end.entity.type, end.entity.display_value)}
            </span>
            {", "}
            {t("evidence.case", lang, { case: end.case.case_number })}
          </li>
        ))}
      </ul>
      {suggested
        ? content.gates.map((line) => (
            <p key={line} className="admin-body">
              {line}
            </p>
          ))
        : null}
      <ReasonList support={content.support} against={content.against} />
      {content.sources.length > 0 ? <EvidenceSource sources={content.sources} /> : null}
      <MoreDetail defaultOpen>
        <p className="admin-body">{t("queue.more.score", lang, { score: explanation.score })}</p>
        <p className="admin-body">
          {t("queue.more.levels", lang, {
            high: explanation.thresholds.high_min,
            medium: explanation.thresholds.medium_min,
          })}
        </p>
        <ul className="admin-plain">
          {detail.ends.map((end) => {
            const raw = record(end.case.case_id);
            return raw ? (
              <li key={end.case.case_id}>
                {t("queue.more.raw", lang, { case: end.case.case_number, text: raw.raw_text })}
              </li>
            ) : null;
          })}
        </ul>
      </MoreDetail>
      {detail.state === "AUTO" && canUndo ? (
        <p className="admin-body">{t("queue.autoNote", lang)}</p>
      ) : null}
      {blocked ? <Message kind="info">{t(blocked, lang)}</Message> : null}
      {busy ? <Loading label={t("queue.saving", lang)} /> : null}
      <div className="admin-actions">
        {canConfirm ? (
          <Button
            variant={variant("confirm")}
            icon="confirm"
            disabled={busy}
            onClick={() =>
              void decide("confirmed", () =>
                api.client.confirmLink(linkId, { expected_state: detail.state }),
              )
            }
          >
            {t("queue.confirm", lang)}
          </Button>
        ) : null}
        {canReject ? (
          <Button
            variant={variant("reject")}
            icon="reject"
            disabled={busy}
            onClick={() => setView({ name: "reject" })}
          >
            {t("queue.reject", lang)}
          </Button>
        ) : null}
        {canUndo ? (
          <Button
            variant={variant("undo")}
            disabled={busy}
            onClick={() => setView({ name: "undo" })}
          >
            {t("queue.undo", lang)}
          </Button>
        ) : null}
        {canReopen ? (
          <Button
            variant={variant("reopen")}
            disabled={busy}
            onClick={() => setView({ name: "reopen" })}
          >
            {t("queue.reopen.button", lang)}
          </Button>
        ) : null}
        {position?.nextId ? (
          <Button variant="secondary" onClick={() => onOpen(position.nextId as string)}>
            {t("queue.next", lang)}
          </Button>
        ) : null}
        <Button variant="secondary" onClick={onBack}>
          {t("queue.backToList", lang)}
        </Button>
      </div>
    </div>
  );
}
