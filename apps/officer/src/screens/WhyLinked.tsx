import {
  Button,
  ConfirmStep,
  EvidenceSource,
  Loading,
  MoreDetail,
  Message,
  ReasonList,
  StrengthBadge,
  useUi,
} from "@tracex/ui";
import { useState } from "react";

import type { ApiResult } from "../api/http";
import type { FailureResult } from "../api/resultKeys";
import type { components } from "../api/schema";
import { useApp } from "../app-context";
import { FailureView } from "../components/FailureView";
import { Await, Screen, titleFor } from "../components/Screen";
import { panelContent } from "../lib/explain";
import { useLoad } from "../lib/useLoad";
import type { MessageKey } from "../i18n";
import { paths, useNav } from "../router";

type LinkDetail = components["schemas"]["LinkDetail"];
type Explanation = components["schemas"]["Explanation"];

/** Same limits as the contract for a decision reason (LinkReasonRequest). */
const REASON_MIN = 3;
const REASON_MAX = 1000;

type Outcome = "confirmed" | "rejected" | "undone" | "reopened";
type View =
  | { name: "panel" }
  | { name: "reject" }
  | { name: "undo" }
  | { name: "reopen" }
  | { name: "decided"; outcome: Outcome; detail: LinkDetail };

interface Loaded {
  detail: LinkDetail;
  explanation: Explanation;
}

async function loadBoth(
  getLink: () => Promise<ApiResult<LinkDetail>>,
  getExplanation: () => Promise<ApiResult<Explanation>>,
): Promise<ApiResult<Loaded>> {
  const [detail, explanation] = await Promise.all([getLink(), getExplanation()]);
  if (detail.kind !== "ok") return detail;
  if (explanation.kind !== "ok") return explanation;
  return { kind: "ok", data: { detail: detail.data, explanation: explanation.data } };
}

/** The sentence for a role that cannot decide (design-flows O6). Nothing for "no decision is legal now". */
function blockedKey(detail: LinkDetail, role: string): MessageKey | undefined {
  switch (detail.decision_block) {
    case "CROSS_AREA_SENIOR_ONLY":
      return "why.cannot.twoAreas";
    case "COVERAGE_INCOMPLETE":
      return "why.cannot.notBothAreas";
    case "GRANT_READ_ONLY":
      return "why.cannot.notBothCases";
    case "ROLE_VIEW_ONLY":
      return role === "JUNIOR" ? "why.cannot.lookOnly" : undefined;
    default:
      return undefined;
  }
}

/** O6 the explanation panel, O7 the reject and undo check, O8 the result. All of it stays on one page. */
export function WhyLinked({ linkId, from }: { linkId: string; from: string | undefined }) {
  const { client, tt, lang, user } = useApp();
  const { t: shared } = useUi();
  const nav = useNav();
  const [epoch, setEpoch] = useState(0);
  const [loaded] = useLoad(
    () =>
      loadBoth(
        () => client.getLink(linkId),
        () => client.getLinkExplanation(linkId),
      ),
    `${linkId}|${epoch}`,
  );
  const [view, setView] = useState<View>({ name: "panel" });
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<FailureResult>();
  /** The link as the last decision left it, so a later step names the state it saw (expected_state). */
  const [latest, setLatest] = useState<LinkDetail>();

  const refresh = () => {
    setFailure(undefined);
    setLatest(undefined);
    setView({ name: "panel" });
    setEpoch((n) => n + 1);
  };

  async function decide(
    outcome: Outcome,
    run: () => Promise<ApiResult<LinkDetail>>,
  ): Promise<void> {
    setBusy(true);
    setFailure(undefined);
    const result = await run();
    setBusy(false);
    if (result.kind === "ok") {
      setLatest(result.data);
      setView({ name: "decided", outcome, detail: result.data });
    } else setFailure(result);
  }

  const title = titleFor(loaded, tt, (both) =>
    tt(both.detail.state === "SUGGESTED" ? "why.titlePossible" : "why.titleStrong"),
  );

  return (
    <Screen title={title}>
      <Await loaded={loaded} onRetry={refresh}>
        {({ detail: link, explanation }) => {
          const state = latest?.state ?? link.state;
          const caseNumbers: Record<string, string> = {};
          for (const end of link.ends) caseNumbers[end.case.case_id] = end.case.case_number;
          const ownCase =
            link.ends.find((end) => end.entity.entity_id === from)?.case ?? link.ends[0]?.case;
          const backToCase = () => nav.go(ownCase ? paths.case(ownCase.case_id) : paths.cases);

          if (failure?.kind === "notFound") return <FailureView result={failure} />;
          const problem = failure ? <FailureView result={failure} onRetry={refresh} /> : null;

          if (view.name === "reject" || view.name === "undo" || view.name === "reopen") {
            const rejecting = view.name === "reject";
            return (
              <>
                {problem}
                {busy ? (
                  <Loading label={tt("why.saving")} />
                ) : rejecting ? (
                  <ConfirmStep
                    title={tt("reject.title")}
                    body={tt("reject.body")}
                    confirmLabel={tt("reject.confirm")}
                    confirmIcon="reject"
                    confirmVariant="danger"
                    reason={{ label: tt("reject.reasonLabel"), min: REASON_MIN, max: REASON_MAX }}
                    onConfirm={(reason) =>
                      void decide("rejected", () =>
                        client.rejectLink(linkId, { reason: reason ?? "", expected_state: state }),
                      )
                    }
                    onCancel={() => setView({ name: "panel" })}
                  />
                ) : view.name === "reopen" ? (
                  <ConfirmStep
                    title={tt("reopen.title")}
                    body={tt("reopen.body")}
                    confirmLabel={tt("reopen.confirm")}
                    confirmVariant="primary"
                    cancelVariant="secondary"
                    reason={{ label: tt("reopen.reasonLabel"), min: REASON_MIN, max: REASON_MAX }}
                    onConfirm={(reason) =>
                      void decide("reopened", () =>
                        client.reopenLink(linkId, { reason: reason ?? "", expected_state: state }),
                      )
                    }
                    onCancel={() => setView({ name: "panel" })}
                  />
                ) : (
                  <ConfirmStep
                    title={tt("undo.title")}
                    body={tt("undo.body")}
                    confirmLabel={tt("undo.confirm")}
                    confirmVariant="primary"
                    cancelVariant="secondary"
                    reason={{ label: tt("undo.reasonLabel"), min: REASON_MIN, max: REASON_MAX }}
                    onConfirm={(reason) =>
                      void decide("undone", () =>
                        client.undoLink(linkId, { reason: reason ?? "", expected_state: state }),
                      )
                    }
                    onCancel={() => setView({ name: "panel" })}
                  />
                )}
              </>
            );
          }

          if (view.name === "decided") {
            const canUndo =
              view.outcome === "confirmed" && view.detail.allowed_actions.includes("UNDO");
            return (
              <>
                <Message kind={view.outcome === "rejected" ? "info" : "success"}>
                  {tt(`decided.${view.outcome}`)}
                </Message>
                <div className="tx-actions">
                  {view.outcome === "undone" || view.outcome === "reopened" ? (
                    <>
                      <Button variant="primary" onClick={refresh}>
                        {tt("decided.checkAgain")}
                      </Button>
                      <Button variant="secondary" onClick={backToCase}>
                        {tt("decided.backToCase")}
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button variant="primary" onClick={backToCase}>
                        {tt("decided.backToCase")}
                      </Button>
                      {canUndo ? (
                        <Button variant="secondary" onClick={() => setView({ name: "undo" })}>
                          {tt("decided.undo")}
                        </Button>
                      ) : null}
                    </>
                  )}
                </div>
              </>
            );
          }

          const content = panelContent(explanation, lang, caseNumbers, shared("item.case"));
          const allowed = new Set(link.allowed_actions);
          const suggested = link.state === "SUGGESTED";
          // The API list already encodes role, state and area. The screen follows it and adds no state check.
          const canConfirm = allowed.has("CONFIRM");
          const canReject = allowed.has("REJECT");
          const canUndo = allowed.has("UNDO");
          const canReopen = allowed.has("REOPEN");
          const blocked =
            !canConfirm && !canReject && !canUndo && !canReopen
              ? blockedKey(link, user.role)
              : undefined;
          const caseNumberOf = (caseId: string, own?: string) => own ?? caseNumbers[caseId] ?? "";

          return (
            <>
              {problem}
              <StrengthBadge strength={suggested ? "possible" : "strong"} />
              <ul className="tx-plainlist">
                {link.ends.map((end) => (
                  <li key={end.entity.entity_id}>
                    <span className="tx-mono">{end.entity.display_value}</span>
                    {", "}
                    {end.case.title
                      ? tt("also.caseLine", { number: end.case.case_number, title: end.case.title })
                      : shared("evidence.case", { case: end.case.case_number })}
                  </li>
                ))}
              </ul>
              {suggested
                ? content.gates.map((line) => (
                    <p key={line} className="tx-body">
                      {line}
                    </p>
                  ))
                : null}
              <ReasonList support={content.support} against={content.against} />
              {content.sources.length > 0 ? <EvidenceSource sources={content.sources} /> : null}
              <MoreDetail>
                <p className="tx-body">
                  {tt("why.moreScore", {
                    score: explanation.score,
                    high: explanation.thresholds.high_min,
                  })}
                </p>
                <ul className="tx-plainlist">
                  {explanation.records.map((record) => (
                    <li key={record.entity_id}>
                      {tt("why.rawValue", {
                        number: caseNumberOf(
                          record.case_id,
                          record.source.case_number ?? undefined,
                        ),
                        text: record.raw_text,
                      })}
                    </li>
                  ))}
                </ul>
              </MoreDetail>
              {link.state === "AUTO" && canUndo ? (
                <p className="tx-body">{tt("why.autoNote")}</p>
              ) : null}
              {blocked ? <Message kind="info">{tt(blocked)}</Message> : null}
              {busy ? <Loading label={tt("why.saving")} /> : null}
              {canConfirm || canReject || canUndo || canReopen ? (
                <div className="tx-actions">
                  {canConfirm ? (
                    <Button
                      variant="primary"
                      icon="confirm"
                      disabled={busy}
                      onClick={() =>
                        void decide("confirmed", () =>
                          client.confirmLink(linkId, { expected_state: link.state }),
                        )
                      }
                    >
                      {tt("why.confirm")}
                    </Button>
                  ) : null}
                  {canReject ? (
                    <Button
                      variant="secondary"
                      icon="reject"
                      disabled={busy}
                      onClick={() => setView({ name: "reject" })}
                    >
                      {tt("why.reject")}
                    </Button>
                  ) : null}
                  {canUndo ? (
                    <Button
                      variant={canConfirm ? "secondary" : "primary"}
                      disabled={busy}
                      onClick={() => setView({ name: "undo" })}
                    >
                      {tt("why.undo")}
                    </Button>
                  ) : null}
                  {canReopen ? (
                    <Button
                      variant={canConfirm || canReject || canUndo ? "secondary" : "primary"}
                      disabled={busy}
                      onClick={() => setView({ name: "reopen" })}
                    >
                      {tt("why.reopen")}
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </>
          );
        }}
      </Await>
    </Screen>
  );
}
