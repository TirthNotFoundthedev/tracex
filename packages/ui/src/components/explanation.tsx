import { useId, useState, type ReactNode } from "react";

import { useUi } from "./context";
import { Icon } from "./Icon";

export interface Source {
  /** Case number as stored, for example "24/118". */
  caseNumber: string;
  /** Plain document type, for example "call record". */
  documentType: string;
  page?: number;
  line?: number;
}

/** "Case 24/118, call record, page 2, line 14"; page and line are left out when unknown. */
export function SourceLine({ source }: { source: Source }) {
  const { t } = useUi();
  const parts = [t("evidence.case", { case: source.caseNumber }), source.documentType];
  if (source.page !== undefined) parts.push(t("evidence.page", { page: source.page }));
  if (source.line !== undefined) parts.push(t("evidence.line", { line: source.line }));
  return <span className="tx-source">{parts.join(", ")}</span>;
}

/** "Where this came from": one source line per document, in order. */
export function EvidenceSource({ sources }: { sources: Source[] }) {
  const { t } = useUi();
  const headingId = useId();
  return (
    <section className="tx-section" aria-labelledby={headingId}>
      <h2 className="tx-section__title" id={headingId}>
        {t("evidence.heading")}
      </h2>
      <ul className="tx-plainlist">
        {sources.map((source, index) => (
          <li key={`${index}-${source.caseNumber}-${source.documentType}`}>
            <SourceLine source={source} />
          </li>
        ))}
      </ul>
    </section>
  );
}

export interface Reason {
  /** One plain sentence, 12 words or fewer. */
  text: string;
  source?: Source;
}

export interface ReasonListProps {
  /** "Why we think so". */
  support: Reason[];
  /** "Why it may be wrong". Empty array shows "Nothing found against this link." */
  against: Reason[];
}

function ReasonItems({ reasons, kind }: { reasons: Reason[]; kind: "support" | "against" }) {
  const { t } = useUi();
  return (
    <ul className="tx-reasons">
      {reasons.map((reason, index) => (
        <li key={`${index}-${reason.text}`} className="tx-reason" data-kind={kind}>
          <Icon name={kind === "support" ? "confirm" : "possible"} />
          <span className="tx-reason__body">
            <span className="tx-sr-only">
              {t(kind === "support" ? "reasons.supportSr" : "reasons.againstSr")}{" "}
            </span>
            <span className="tx-reason__text">{reason.text}</span>
            {reason.source ? <SourceLine source={reason.source} /> : null}
          </span>
        </li>
      ))}
    </ul>
  );
}

/**
 * Both sections always appear; if nothing is against the link, it says so, so the
 * officer sees that the system looked (DESIGN_RULES section 9).
 */
export function ReasonList({ support, against }: ReasonListProps) {
  const { t } = useUi();
  const forId = useId();
  const againstId = useId();
  return (
    <>
      <section className="tx-section" aria-labelledby={forId}>
        <h2 className="tx-section__title" id={forId}>
          {t("reasons.for")}
        </h2>
        <ReasonItems reasons={support} kind="support" />
      </section>
      <section className="tx-section" aria-labelledby={againstId}>
        <h2 className="tx-section__title" id={againstId}>
          {t("reasons.against")}
        </h2>
        {against.length > 0 ? (
          <ReasonItems reasons={against} kind="against" />
        ) : (
          <p className="tx-body">{t("reasons.noneAgainst")}</p>
        )}
      </section>
    </>
  );
}

export interface MoreDetailProps {
  /** Override the default "More detail". */
  label?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}

/** The one disclosure, closed by default. A real button: Enter and Space work. */
export function MoreDetail({ label, defaultOpen = false, children }: MoreDetailProps) {
  const { t } = useUi();
  const [open, setOpen] = useState(defaultOpen);
  const panelId = useId();
  return (
    <div className="tx-detail" data-open={open ? "true" : undefined}>
      <button
        type="button"
        className="tx-detail__toggle"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        <Icon name={open ? "open" : "next"} />
        <span>{label ?? t("detail.label")}</span>
      </button>
      <div id={panelId} className="tx-detail__panel" hidden={!open}>
        {children}
      </div>
    </div>
  );
}
