import { Button, EmptyState, Loading, Message, Pager, Select, Table, TextField } from "@tracex/ui";
import { useCallback, useEffect, useRef, useState } from "react";

import type { AdminApi } from "../api";
import type { ApiResult } from "../api/http";
import type { FailureResult } from "../api/resultKeys";
import type { components } from "../api/schema";
import { FailureView } from "../components/FailureView";
import { dateOnly } from "../format";
import { t, type AnyMessageKey, type Language, type MessageKey } from "../i18n";
import type { Role } from "../nav";

type AccessItem = components["schemas"]["AccessRequestToDecide"];
type Change = components["schemas"]["PendingChange"];

const PAGE = 50;
const NOTE_MAX = 200;
const DAYS = [7, 30, 90] as const;
const NO_VALUE = "—";

type Tab = "access" | "changes";

interface ApprovalsPageProps {
  api: AdminApi;
  lang: Language;
  role: Role;
  /** The signed-in person: the one who may not decide their own request or change. */
  userId: string;
}

interface PageShape<T> {
  items: T[];
  next_cursor: string | null;
  total?: number | undefined;
}

type ListLoad<T> =
  | { state: "loading" }
  | { state: "failed"; result: FailureResult }
  | { state: "ready"; items: T[]; next: string | null; total: number | undefined };

/**
 * One paged list. A refresh starts a new generation, and an answer that belongs to an older one is
 * dropped, so a slow answer never overwrites a newer list (the same goes for Show more).
 */
function usePagedList<T>(fetchPage: (cursor?: string) => Promise<ApiResult<PageShape<T>>>) {
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

/** The open tab's number comes from its own list `total`: no separate count read (D69). */
function useReportTotal<T>(load: ListLoad<T>, onTotal: (n: number) => void) {
  useEffect(() => {
    if (load.state === "ready") onTotal(load.total ?? load.items.length);
  }, [load, onTotal]);
}

interface Column<T> {
  id: string;
  header: string;
  cell: (row: T) => React.ReactNode;
}

interface ListViewProps<T> {
  lang: Language;
  list: ReturnType<typeof usePagedList<T>>;
  caption: string;
  empty: string;
  columns: Column<T>[];
  rowKey: (row: T) => string;
  onOpen: (row: T) => void;
}

function ListView<T>({ lang, list, caption, empty, columns, rowKey, onOpen }: ListViewProps<T>) {
  const { load, more, moreFailure, refresh, loadMore } = list;
  if (load.state === "loading") return <Loading label={t("loading.default", lang)} />;
  if (load.state === "failed") {
    return <FailureView result={load.result} lang={lang} onRetry={() => void refresh()} />;
  }
  if (load.items.length === 0) return <EmptyState title={empty} hint="" />;
  const next = load.next;
  return (
    <>
      <Table
        caption={caption}
        rows={load.items}
        rowKey={rowKey}
        columns={columns}
        onOpenRow={onOpen}
      />
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

const roleName = (role: unknown, lang: Language): string =>
  typeof role === "string" ? t(`role.${role.toLowerCase()}` as AnyMessageKey, lang) : NO_VALUE;

/** Failures that end the decision: the request or change is gone or already changed. */
const isFinal = (failure: FailureResult | undefined) =>
  failure?.kind === "notFound" || failure?.kind === "conflict";

// ---------------------------------------------------------------- access requests

function AccessDetail({
  api,
  lang,
  item,
  userId,
  onBack,
}: {
  api: AdminApi;
  lang: Language;
  item: AccessItem;
  userId: string;
  onBack: () => void;
}) {
  const [step, setStep] = useState<"view" | "confirm">("view");
  const [days, setDays] = useState("30");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<FailureResult | undefined>();
  const [done, setDone] = useState<string | undefined>();

  const own = item.requester.user_id === userId;
  const canDecide = item.status === "PENDING" && !own && !done && !isFinal(failure);

  const approve = async () => {
    setBusy(true);
    setFailure(undefined);
    const result = await api.client.approveAccessRequest(item.request_id, {
      duration_days: Number(days) as (typeof DAYS)[number],
    });
    setBusy(false);
    setStep("view");
    if (result.kind !== "ok") return setFailure(result);
    const ends =
      result.data.grant?.expires_at ??
      new Date(Date.now() + Number(days) * 86_400_000).toISOString();
    setDone(t("approvals.access.approved", lang, { date: dateOnly(ends, lang) }));
  };

  const refuse = async () => {
    setBusy(true);
    setFailure(undefined);
    const result = await api.client.denyAccessRequest(
      item.request_id,
      // An empty note is a 422 at the API, so a blank one is left out.
      note.trim() ? { note: note.trim() } : {},
    );
    setBusy(false);
    if (result.kind !== "ok") return setFailure(result);
    setDone(t("approvals.access.refused", lang));
  };

  return (
    <div className="admin-detail">
      <dl className="admin-values">
        <dt>{t("approvals.col.requestedBy", lang)}</dt>
        <dd>{item.requester.display_name}</dd>
        <dt>{t("approvals.col.forCase", lang)}</dt>
        <dd>{item.far_case_number}</dd>
        <dt>{t("common.date", lang)}</dt>
        <dd>{dateOnly(item.requested_at, lang)}</dd>
        <dt>{t("common.status", lang)}</dt>
        <dd>{t(`approvals.access.status.${item.status}` as MessageKey, lang)}</dd>
      </dl>
      <h3>{t("approvals.col.reason", lang)}</h3>
      <p className="admin-body">{item.reason}</p>
      {done ? <Message kind="success">{done}</Message> : null}
      {failure ? <FailureView result={failure} lang={lang} /> : null}
      {own ? <Message kind="info">{t("approvals.access.ownRequest", lang)}</Message> : null}
      {canDecide && step === "view" ? (
        <div className="admin-form">
          <Select
            label={t("approvals.access.ends", lang)}
            value={days}
            options={DAYS.map((d) => ({
              value: String(d),
              label: t("approvals.access.days", lang, { days: d }),
            }))}
            onChange={setDays}
          />
          <TextField
            label={t("approvals.access.refuseReason", lang)}
            hint={t("approvals.access.refuseHint", lang)}
            value={note}
            multiline
            maxLength={NOTE_MAX}
            onChange={setNote}
          />
          <div className="admin-actions">
            <Button
              variant="primary"
              icon="confirm"
              disabled={busy}
              onClick={() => setStep("confirm")}
            >
              {t("approvals.access.approve", lang)}
            </Button>
            <Button variant="secondary" disabled={busy} onClick={() => void refuse()}>
              {t("approvals.access.refuse", lang)}
            </Button>
          </div>
        </div>
      ) : null}
      {canDecide && step === "confirm" ? (
        <div className="admin-form">
          <p>
            {t("approvals.access.confirm", lang, {
              name: item.requester.display_name,
              case: item.far_case_number,
              days,
            })}
          </p>
          <div className="admin-actions">
            <Button variant="primary" icon="confirm" disabled={busy} onClick={() => void approve()}>
              {t("approvals.access.yes", lang)}
            </Button>
            <Button variant="secondary" disabled={busy} onClick={() => setStep("view")}>
              {t("confirm.no", lang)}
            </Button>
          </div>
        </div>
      ) : null}
      <div className="admin-actions">
        <Button variant="secondary" onClick={onBack}>
          {t("state.backToList", lang)}
        </Button>
      </div>
    </div>
  );
}

function AccessTab({
  api,
  lang,
  userId,
  onTotal,
}: {
  api: AdminApi;
  lang: Language;
  userId: string;
  onTotal: (n: number) => void;
}) {
  const fetchPage = useCallback(
    (cursor?: string) =>
      api.client.listAccessRequests({
        scope: "to_decide",
        status: "PENDING",
        limit: PAGE,
        ...(cursor ? { cursor } : {}),
      }),
    [api],
  );
  const list = usePagedList<AccessItem>(
    fetchPage as (cursor?: string) => Promise<ApiResult<PageShape<AccessItem>>>,
  );
  const [opened, setOpened] = useState<AccessItem | undefined>();
  useReportTotal(list.load, onTotal);

  if (opened) {
    return (
      <AccessDetail
        key={opened.request_id}
        api={api}
        lang={lang}
        item={opened}
        userId={userId}
        onBack={() => {
          setOpened(undefined);
          void list.refresh();
        }}
      />
    );
  }
  return (
    <ListView
      lang={lang}
      list={list}
      caption={t("approvals.title", lang)}
      empty={t("approvals.access.empty", lang)}
      rowKey={(row) => row.request_id}
      onOpen={setOpened}
      columns={[
        {
          id: "by",
          header: t("approvals.col.requestedBy", lang),
          cell: (r) => r.requester.display_name,
        },
        { id: "case", header: t("approvals.col.forCase", lang), cell: (r) => r.far_case_number },
        { id: "reason", header: t("approvals.col.reason", lang), cell: (r) => r.reason },
        { id: "date", header: t("common.date", lang), cell: (r) => dateOnly(r.requested_at, lang) },
        {
          id: "status",
          header: t("common.status", lang),
          cell: (r) => t(`approvals.access.status.${r.status}` as MessageKey, lang),
        },
      ]}
    />
  );
}

// ---------------------------------------------------------------- pending changes

type Areas =
  | { status: "loading" }
  | { status: "failed"; result: FailureResult }
  | { status: "ready"; districts: Map<string, string>; states: Map<string, string> };

const record = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" ? (value as Record<string, unknown>) : {};

/**
 * The words for the area in `value` (a district or a coverage set), or undefined when a name cannot be
 * found. The approver must see what the change hash binds, so an unknown name is never shown as a dash.
 */
function areaOf(value: Record<string, unknown>, areas: Areas, lang: Language): string | undefined {
  if (areas.status !== "ready") return undefined;
  if (typeof value.district_id === "string") return areas.districts.get(value.district_id);
  const coverage = record(value.coverage);
  if (value.coverage && typeof value.coverage === "object") {
    if (coverage.all_states === true) return t("shell.noArea", lang);
    const names = [
      ...(Array.isArray(coverage.state_ids) ? coverage.state_ids : []).map((id) =>
        areas.states.get(String(id)),
      ),
      ...(Array.isArray(coverage.district_ids) ? coverage.district_ids : []).map((id) =>
        areas.districts.get(String(id)),
      ),
    ];
    if (names.length === 0) return t("approvals.area.none", lang);
    return names.some((n) => n === undefined) ? undefined : names.join(", ");
  }
  return t("approvals.area.none", lang);
}

const areaText = (value: Record<string, unknown>, areas: Areas, lang: Language) =>
  areaOf(value, areas, lang) ?? t("approvals.area.unknown", lang);

/** True when this change shows an area whose name we cannot give. Approve stays hidden until it loads. */
function areaMissing(change: Change, areas: Areas, lang: Language): boolean {
  if (change.kind !== "USER_JURISDICTION" && change.kind !== "USER_CREATE") return false;
  const values =
    change.kind === "USER_CREATE" ? [change.new_value] : [change.old_value, change.new_value];
  return values.some((v) => v && areaOf(record(v), areas, lang) === undefined);
}

/** The change in plain words. */
function changeText(change: Change, areas: Areas, lang: Language): string {
  const name = change.subject?.display_name ?? "";
  const from = record(change.old_value);
  const to = record(change.new_value);
  switch (change.kind) {
    case "USER_CREATE":
      return t("approvals.change.userCreate", lang, { name: String(to.display_name ?? "") });
    case "USER_ENABLE":
    case "USER_DISABLE":
      return t("approvals.change.userActive", lang, {
        state: t(
          change.kind === "USER_ENABLE" ? "approvals.state.on" : "approvals.state.off",
          lang,
        ),
        name,
      });
    case "USER_ROLE":
      return t("approvals.change.userRole", lang, {
        name,
        from: roleName(from.role, lang),
        to: roleName(to.role, lang),
      });
    case "USER_JURISDICTION":
      return t("approvals.change.userArea", lang, {
        name,
        from: areaText(from, areas, lang),
        to: areaText(to, areas, lang),
      });
    case "ASSIGNMENT_ADD":
    case "ASSIGNMENT_REMOVE":
      return t(
        change.kind === "ASSIGNMENT_ADD"
          ? "approvals.change.assignmentAdd"
          : "approvals.change.assignmentRemove",
        lang,
        { name, case: String(to.case_number ?? "") },
      );
    case "THRESHOLDS":
      return t("approvals.change.thresholds", lang, {
        high: String(to.high_min ?? ""),
        medium: String(to.medium_min ?? ""),
      });
  }
}

interface ValueRow {
  label: string;
  from: string;
  to: string;
}

/** Old and new value side by side, one row per thing that changes. */
function valueRows(change: Change, areas: Areas, lang: Language): ValueRow[] {
  const from = record(change.old_value);
  const to = record(change.new_value);
  const text = (v: unknown) => (v === undefined || v === null ? NO_VALUE : String(v));
  switch (change.kind) {
    case "THRESHOLDS":
      return [
        { label: t("thresholds.strong", lang), from: text(from.high_min), to: text(to.high_min) },
        {
          label: t("thresholds.possible", lang),
          from: text(from.medium_min),
          to: text(to.medium_min),
        },
      ];
    case "USER_ROLE":
      return [
        {
          label: t("users.field.role", lang),
          from: roleName(from.role, lang),
          to: roleName(to.role, lang),
        },
      ];
    case "USER_JURISDICTION":
      return [
        {
          label: t("users.field.area", lang),
          from: areaText(from, areas, lang),
          to: areaText(to, areas, lang),
        },
      ];
    case "USER_ENABLE":
    case "USER_DISABLE": {
      const status = (v: unknown) =>
        typeof v === "boolean" ? t(v ? "users.status.active" : "users.status.off", lang) : NO_VALUE;
      return [
        { label: t("common.status", lang), from: status(from.active), to: status(to.active) },
      ];
    }
    case "USER_CREATE":
      return [
        { label: t("users.field.name", lang), from: NO_VALUE, to: text(to.display_name) },
        { label: t("approvals.signInName", lang), from: NO_VALUE, to: text(to.username) },
        { label: t("users.field.role", lang), from: NO_VALUE, to: roleName(to.role, lang) },
        { label: t("users.field.area", lang), from: NO_VALUE, to: areaText(to, areas, lang) },
      ];
    case "ASSIGNMENT_ADD":
      return [
        { label: t("approvals.col.forCase", lang), from: NO_VALUE, to: text(to.case_number) },
      ];
    case "ASSIGNMENT_REMOVE":
      return [
        { label: t("approvals.col.forCase", lang), from: text(to.case_number), to: NO_VALUE },
      ];
  }
}

const statusKey = (state: Change["state"]): MessageKey =>
  state === "PENDING"
    ? "approvals.status.waiting"
    : state === "APPROVED"
      ? "approvals.status.approved"
      : "approvals.status.refused";

function ChangeDetail({
  api,
  lang,
  role,
  item,
  userId,
  areas,
  onRetryAreas,
  onBack,
}: {
  api: AdminApi;
  lang: Language;
  role: Role;
  item: Change;
  userId: string;
  areas: Areas;
  onRetryAreas: () => void;
  onBack: () => void;
}) {
  const [step, setStep] = useState<"view" | "confirm">("view");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<FailureResult | undefined>();
  const [done, setDone] = useState<"approved" | "refused" | undefined>();

  const proposer = item.proposer.user_id === userId;
  const subject = item.subject?.user_id === userId;
  const canDecide =
    role === "SENIOR" &&
    item.state === "PENDING" &&
    !proposer &&
    !subject &&
    !done &&
    !isFinal(failure);
  // The approver must see every area name the change binds; until they load, Approve stays hidden.
  const missing = areaMissing(item, areas, lang);
  const canApprove = canDecide && !missing;

  const approve = async () => {
    setBusy(true);
    setFailure(undefined);
    // The hash the person saw: if the proposal changed meanwhile, the API answers 409 (stale).
    const result = await api.client.approveChange(item.change_id, {
      change_hash: item.change_hash,
    });
    setBusy(false);
    setStep("view");
    if (result.kind !== "ok") return setFailure(result);
    setDone("approved");
  };

  const refuse = async () => {
    setBusy(true);
    setFailure(undefined);
    const result = await api.client.denyChange(item.change_id);
    setBusy(false);
    if (result.kind !== "ok") return setFailure(result);
    setDone("refused");
  };

  const rows = valueRows(item, areas, lang);
  const side = (which: "from" | "to") => (
    <section className="admin-compare__side">
      <h3>{t(which === "from" ? "approvals.oldValue" : "approvals.newValue", lang)}</h3>
      <dl className="admin-values">
        {rows.map((row) => (
          <div key={row.label} className="admin-values__row">
            <dt>{row.label}</dt>
            <dd>{row[which]}</dd>
          </div>
        ))}
      </dl>
    </section>
  );

  return (
    <div className="admin-detail">
      <p className="admin-body">{changeText(item, areas, lang)}</p>
      <dl className="admin-values">
        <dt>{t("approvals.col.proposedBy", lang)}</dt>
        <dd>{item.proposer.display_name}</dd>
        <dt>{t("common.date", lang)}</dt>
        <dd>{dateOnly(item.proposed_at, lang)}</dd>
        <dt>{t("common.status", lang)}</dt>
        <dd>{t(statusKey(item.state), lang)}</dd>
      </dl>
      <div className="admin-compare">
        {side("from")}
        {side("to")}
      </div>
      {done ? (
        <Message kind="success">
          {t(done === "approved" ? "approvals.done.approved" : "approvals.done.refused", lang)}
        </Message>
      ) : null}
      {failure ? <ChangeFailure result={failure} lang={lang} /> : null}
      {role === "SENIOR" && item.state === "PENDING" && proposer ? (
        <Message kind="info">{t("approvals.noRight.proposer", lang)}</Message>
      ) : null}
      {role === "SENIOR" && item.state === "PENDING" && !proposer && subject ? (
        <Message kind="info">{t("approvals.noRight.subject", lang)}</Message>
      ) : null}
      {canDecide && missing ? (
        <>
          <Message kind="info">{t("approvals.area.hidden", lang)}</Message>
          {areas.status === "failed" ? (
            <FailureView result={areas.result} lang={lang} onRetry={onRetryAreas} />
          ) : null}
        </>
      ) : null}
      {canDecide && step === "view" ? (
        <div className="admin-actions">
          {canApprove ? (
            <Button
              variant="primary"
              icon="confirm"
              disabled={busy}
              onClick={() => setStep("confirm")}
            >
              {t("approvals.approve", lang)}
            </Button>
          ) : null}
          <Button variant="secondary" disabled={busy} onClick={() => void refuse()}>
            {t("approvals.refuse", lang)}
          </Button>
        </div>
      ) : null}
      {canApprove && step === "confirm" ? (
        <div className="admin-form">
          <p>{t("approvals.approve.confirm", lang)}</p>
          <div className="admin-actions">
            <Button variant="primary" icon="confirm" disabled={busy} onClick={() => void approve()}>
              {t("approvals.approve.yes", lang)}
            </Button>
            <Button variant="secondary" disabled={busy} onClick={() => setStep("view")}>
              {t("confirm.no", lang)}
            </Button>
          </div>
        </div>
      ) : null}
      <div className="admin-actions">
        <Button variant="secondary" onClick={onBack}>
          {t("state.backToList", lang)}
        </Button>
      </div>
    </div>
  );
}

/** Change decisions add three 409 reasons; a 404 is the plain "no such change" (access spec 3.2). */
function ChangeFailure({ result, lang }: { result: FailureResult; lang: Language }) {
  if (result.kind === "conflict") {
    const key: MessageKey | undefined =
      result.code === "CHANGE_HASH_STALE"
        ? "approvals.error.stale"
        : result.code === "OLD_VALUE_CHANGED"
          ? "approvals.error.oldValue"
          : result.code === "LAST_APPROVER"
            ? "approvals.error.lastApprover"
            : undefined;
    if (key) return <Message kind="error">{t(key, lang)}</Message>;
  }
  if (result.kind === "notFound") {
    return <Message kind="error">{t("approvals.error.notFound", lang)}</Message>;
  }
  return <FailureView result={result} lang={lang} />;
}

function ChangesTab({
  api,
  lang,
  role,
  userId,
  areas,
  onRetryAreas,
  onTotal,
}: {
  api: AdminApi;
  lang: Language;
  role: Role;
  userId: string;
  areas: Areas;
  onRetryAreas: () => void;
  onTotal: (n: number) => void;
}) {
  // A senior officer decides pending changes; an administrator sees all the changes they proposed.
  const fetchPage = useCallback(
    (cursor?: string) =>
      api.client.listPendingChanges({
        ...(role === "ADMIN" ? {} : { state: "PENDING" as const }),
        limit: PAGE,
        ...(cursor ? { cursor } : {}),
      }),
    [api, role],
  );
  const list = usePagedList<Change>(fetchPage);
  const [opened, setOpened] = useState<Change | undefined>();
  useReportTotal(list.load, onTotal);

  if (opened) {
    return (
      <ChangeDetail
        key={opened.change_id}
        api={api}
        lang={lang}
        role={role}
        item={opened}
        userId={userId}
        areas={areas}
        onRetryAreas={onRetryAreas}
        onBack={() => {
          setOpened(undefined);
          void list.refresh();
        }}
      />
    );
  }
  return (
    <ListView
      lang={lang}
      list={list}
      caption={t("approvals.title", lang)}
      empty={t("approvals.change.empty", lang)}
      rowKey={(row) => row.change_id}
      onOpen={setOpened}
      columns={[
        {
          id: "by",
          header: t("approvals.col.proposedBy", lang),
          cell: (r) => r.proposer.display_name,
        },
        {
          id: "change",
          header: t("approvals.col.change", lang),
          cell: (r) => changeText(r, areas, lang),
        },
        {
          id: "about",
          header: t("approvals.col.about", lang),
          cell: (r) => r.subject?.display_name ?? NO_VALUE,
        },
        { id: "date", header: t("common.date", lang), cell: (r) => dateOnly(r.proposed_at, lang) },
        {
          id: "status",
          header: t("common.status", lang),
          cell: (r) => t(statusKey(r.state), lang),
        },
      ]}
    />
  );
}

// ---------------------------------------------------------------- page

/** Who gets which tab. ADMIN gets 404 on requests to decide (D44), and a SUPERVISOR gets 403 on changes. */
function tabsFor(role: Role): Tab[] {
  return role === "ADMIN" ? ["changes"] : role === "SENIOR" ? ["access", "changes"] : ["access"];
}

/**
 * A4 Approvals and A4a Changes to approve. Which tabs a role sees only saves calls the API would refuse;
 * the API decides, and every refusal shows here through FailureView. Details come from the list rows:
 * opening one reads nothing more, because each detail read is written to the audit log.
 */
export function ApprovalsPage({ api, lang, role, userId }: ApprovalsPageProps) {
  const tabs = tabsFor(role);
  const [tab, setTab] = useState<Tab>(tabs[0] ?? "access");
  // The number on the open tab is the `total` of its own list; the other tab shows none until opened.
  const [total, setTotal] = useState<number | undefined>();
  const [areas, setAreas] = useState<Areas>({ status: "loading" });
  const [areasTry, setAreasTry] = useState(0);
  const wantsAreas = tabs.includes("changes");

  useEffect(() => {
    if (!wantsAreas) return;
    let live = true;
    setAreas({ status: "loading" });
    // Names for the areas a change names; if they do not load, Approve stays hidden on those changes.
    void api.client.listJurisdictions().then((result) => {
      if (!live) return;
      if (result.kind !== "ok") return setAreas({ status: "failed", result });
      setAreas({
        status: "ready",
        districts: new Map(
          result.data.items.flatMap((state) =>
            state.districts.map((d) => [d.district_id, d.name] as const),
          ),
        ),
        states: new Map(result.data.items.map((state) => [state.state_id, state.name] as const)),
      });
    });
    return () => {
      live = false;
    };
  }, [api, wantsAreas, areasTry]);

  const choice = (which: Tab) => {
    const open = tab === which;
    const key =
      which === "access"
        ? open && total !== undefined
          ? "approvals.show.access"
          : "approvals.tab.access"
        : open && total !== undefined
          ? "approvals.show.changes"
          : "approvals.tab.changes";
    return (
      <Button
        key={which}
        variant="secondary"
        {...(open ? { icon: "confirm" as const } : {})}
        aria-pressed={open}
        onClick={() => {
          // The open tab does not reload, so its number must stay.
          if (open) return;
          setTotal(undefined);
          setTab(which);
        }}
      >
        {t(key, lang, { n: total ?? 0 })}
      </Button>
    );
  };

  return (
    <div className="admin-page">
      <h2 className="admin-panel-title">{t("approvals.title", lang)}</h2>
      <div className="admin-switch" role="group" aria-label={t("approvals.title", lang)}>
        {tabs.map(choice)}
      </div>
      {tab === "access" ? (
        <AccessTab api={api} lang={lang} userId={userId} onTotal={setTotal} />
      ) : (
        <ChangesTab
          api={api}
          lang={lang}
          role={role}
          userId={userId}
          areas={areas}
          onRetryAreas={() => setAreasTry((n) => n + 1)}
          onTotal={setTotal}
        />
      )}
    </div>
  );
}
