import { Badge, Button, Loading, Message, TextField } from "@tracex/ui";
import { useCallback, useEffect, useState } from "react";

import type { AdminApi } from "../api";
import type { Role } from "../nav";
import type { FailureResult } from "../api/resultKeys";
import type { components } from "../api/schema";
import { FailureView } from "../components/FailureView";
import { t, type Language } from "../i18n";

type Thresholds = components["schemas"]["Thresholds"];
type Pair = { high: number; medium: number };

const STRONG_MIN = 70;
const STRONG_MAX = 100;
const POSSIBLE_MIN = 30;
/** The possible level stays at least this far below the strong level (contract: medium_min <= high_min - 10). */
const GAP = 10;

type Load =
  | { state: "loading" }
  | { state: "failed"; result: FailureResult }
  | { state: "ready"; current: Thresholds; pending: Pair | undefined };

interface ThresholdsPageProps {
  api: AdminApi;
  lang: Language;
  role: Role;
}

const whole = (text: string): number | undefined =>
  /^\d{1,3}$/.test(text.trim()) ? Number(text.trim()) : undefined;

function possibleMax(highText: string): number {
  const high = whole(highText);
  const clamped = Math.min(STRONG_MAX, Math.max(STRONG_MIN, high ?? STRONG_MIN));
  return clamped - GAP;
}

function pairOf(value: unknown): Pair | undefined {
  const v = value as { high_min?: unknown; medium_min?: unknown } | null;
  return typeof v?.high_min === "number" && typeof v.medium_min === "number"
    ? { high: v.high_min, medium: v.medium_min }
    : undefined;
}

/**
 * A7 Match settings, on the 0 to 100 scale. Only an Administrator proposes new numbers, and a proposal
 * waits for a Senior officer (D35); the numbers in use do not change. There is no test run or preview
 * (D44), and the zone bar is only a score range: nothing is stored for the lowest zone (D49).
 */
export function ThresholdsPage({ api, lang, role }: ThresholdsPageProps) {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [strong, setStrong] = useState("");
  const [possible, setPossible] = useState("");
  const [bad, setBad] = useState<{ strong: boolean; possible: boolean }>({
    strong: false,
    possible: false,
  });
  const [problem, setProblem] = useState<FailureResult | undefined>();
  const [saving, setSaving] = useState(false);
  const [sent, setSent] = useState(false);

  const refresh = useCallback(async () => {
    const [current, waiting] = await Promise.all([
      api.client.getThresholds(),
      api.client.listPendingChanges({ state: "PENDING", kind: "THRESHOLDS", limit: 1 }),
    ]);
    if (current.kind !== "ok") return setLoad({ state: "failed", result: current });
    // Only a 200 says whether a change waits; until then the Save form stays hidden.
    if (waiting.kind !== "ok") return setLoad({ state: "failed", result: waiting });
    const pending = pairOf(waiting.data.items[0]?.new_value);
    setStrong(String(current.data.high_min));
    setPossible(String(current.data.medium_min));
    setLoad({ state: "ready", current: current.data, pending });
  }, [api]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

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

  const { current, pending } = load;
  const canEdit = role === "ADMIN";
  const max = possibleMax(strong);

  const save = async () => {
    setProblem(undefined);
    setSent(false);
    const high = whole(strong);
    const medium = whole(possible);
    const strongBad = high === undefined || high < STRONG_MIN || high > STRONG_MAX;
    const possibleBad = medium === undefined || medium < POSSIBLE_MIN || medium > max;
    setBad({ strong: strongBad, possible: possibleBad });
    if (high === undefined || medium === undefined || strongBad || possibleBad) return;

    setSaving(true);
    const result = await api.client.proposeChange({
      kind: "THRESHOLDS",
      new_value: { high_min: high, medium_min: medium },
    });
    setSaving(false);
    if (result.kind === "invalid") {
      setBad({
        strong: result.fieldErrors.some((e) => e.field.endsWith("high_min")),
        possible: result.fieldErrors.some((e) => e.field.endsWith("medium_min")),
      });
      return setProblem(result);
    }
    if (result.kind !== "ok") return setProblem(result);
    setSent(true);
    setLoad({ ...load, pending: pairOf(result.data.new_value) ?? { high, medium } });
  };

  const zones = [
    { id: "none", label: t("thresholds.zone.none", lang), size: current.medium_min },
    {
      id: "check",
      label: t("thresholds.zone.check", lang),
      size: current.high_min - current.medium_min,
    },
    { id: "auto", label: t("thresholds.zone.auto", lang), size: 100 - current.high_min },
  ];

  return (
    <div className="admin-page">
      <h2>{t("thresholds.title", lang)}</h2>
      <p>{t("thresholds.intro", lang)}</p>
      <div className="admin-zones" aria-label={t("thresholds.title", lang)}>
        {zones.map((zone) => (
          <div
            key={zone.id}
            className="admin-zone"
            data-zone={zone.id}
            style={{ flexGrow: zone.size }}
          >
            {zone.label}
          </div>
        ))}
      </div>
      {sent ? <Message kind="info">{t("approvals.sent", lang)}</Message> : null}
      {problem ? <FailureView result={problem} lang={lang} /> : null}
      {pending ? (
        <div className="admin-pending">
          <Badge icon="pending">{t("approvals.tag.waiting", lang)}</Badge>
          <p>{t("approvals.thresholds.pending", lang)}</p>
          <dl className="admin-values">
            <dt>{t("thresholds.strong", lang)}</dt>
            <dd>
              {t("approvals.oldValue", lang)}: <span>{current.high_min}</span>
              {" · "}
              {t("approvals.newValue", lang)}: <span>{pending.high}</span>
            </dd>
            <dt>{t("thresholds.possible", lang)}</dt>
            <dd>
              {t("approvals.oldValue", lang)}: <span>{current.medium_min}</span>
              {" · "}
              {t("approvals.newValue", lang)}: <span>{pending.medium}</span>
            </dd>
          </dl>
        </div>
      ) : null}
      {canEdit ? (
        <form
          className="admin-form"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <TextField
            label={t("thresholds.strong", lang)}
            hint={t("thresholds.strong.help", lang)}
            value={strong}
            inputMode="numeric"
            error={bad.strong ? t("thresholds.error.strong", lang) : undefined}
            onChange={setStrong}
          />
          <p className="admin-hint">{t("thresholds.range.strong", lang)}</p>
          <TextField
            label={t("thresholds.possible", lang)}
            hint={t("thresholds.possible.help", lang)}
            value={possible}
            inputMode="numeric"
            error={bad.possible ? t("thresholds.error.possible", lang, { max }) : undefined}
            onChange={setPossible}
          />
          <p className="admin-hint">{t("thresholds.range.possible", lang, { max })}</p>
          <p>{t("thresholds.afterApproval", lang)}</p>
          <div className="admin-actions">
            <Button variant="primary" type="submit" icon="confirm" disabled={saving || !!pending}>
              {t("thresholds.save", lang)}
            </Button>
          </div>
        </form>
      ) : (
        <div>
          <dl className="admin-values">
            <dt>{t("thresholds.strong", lang)}</dt>
            <dd>{current.high_min}</dd>
            <dt>{t("thresholds.possible", lang)}</dt>
            <dd>{current.medium_min}</dd>
          </dl>
          <p>{t("thresholds.readOnly", lang)}</p>
        </div>
      )}
    </div>
  );
}
