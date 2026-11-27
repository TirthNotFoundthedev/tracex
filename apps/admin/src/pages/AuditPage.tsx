import { Button, Message, Select, Table, TextField } from "@tracex/ui";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AdminApi } from "../api";
import type { FailureResult } from "../api/resultKeys";
import type { components } from "../api/schema";
import { FailureView } from "../components/FailureView";
import { dateTime } from "../format";
import { t, type AnyMessageKey, type Language } from "../i18n";
import type { Role } from "../nav";
import { PagedView, usePagedList } from "../usePagedList";
import { EVENT_TYPES, EVENT_WORDS, TARGET_WORDS } from "./auditWords";

type Row = components["schemas"]["AuditRow"];
type User = components["schemas"]["User"];

const PAGE = 50;
const USERS_PAGE = 100;
/** Names for the Person column: at most this many pages of users, read once. */
const USERS_MAX_PAGES = 10;
const NO_VALUE = "—";

interface Filters {
  from: string;
  to: string;
  person: string;
  action: string;
}
const NO_FILTERS: Filters = { from: "", to: "", person: "", action: "" };

/** Local start and end of the chosen days, as the moments the API takes. */
const startOf = (day: string) => new Date(`${day}T00:00:00`).toISOString();
const endOf = (day: string) => new Date(`${day}T23:59:59.999`).toISOString();

type Names =
  | { state: "none" }
  | { state: "loading" }
  | { state: "failed"; result: FailureResult }
  | { state: "ready"; users: User[] };

/**
 * One read of the users, for names in the Person column and for the Person filter. Only a Senior officer
 * or an Administrator may read users; a Supervisor sees the role in words instead.
 */
function useNames(api: AdminApi, wanted: boolean, attempt: number): Names {
  const [names, setNames] = useState<Names>({ state: wanted ? "loading" : "none" });
  useEffect(() => {
    if (!wanted) return setNames({ state: "none" });
    let live = true;
    setNames({ state: "loading" });
    void (async () => {
      const users: User[] = [];
      let cursor: string | undefined;
      for (let page = 0; page < USERS_MAX_PAGES; page++) {
        const result = await api.client.listUsers({
          limit: USERS_PAGE,
          ...(cursor ? { cursor } : {}),
        });
        if (!live) return;
        if (result.kind !== "ok") return setNames({ state: "failed", result });
        users.push(...result.data.items);
        cursor = result.data.next_cursor ?? undefined;
        if (!cursor) break;
      }
      setNames({ state: "ready", users });
    })();
    return () => {
      live = false;
    };
  }, [api, wanted, attempt]);
  return names;
}

type Verify =
  | { state: "idle" }
  | { state: "working" }
  | { state: "ok" }
  | { state: "broken"; firstBad: number | undefined }
  | { state: "failed"; result: FailureResult };

interface AuditPageProps {
  api: AdminApi;
  lang: Language;
  role: Role;
}

/**
 * A6 Activity log. Read-only: there is no export, download, edit or delete (audit spec, D44), and the
 * API shows each reader only the rows the row-level rule allows. A row has no sequence number, so none
 * is shown; the one exception is the first bad entry of a BROKEN check, which only a Senior officer can
 * run (D45). Role codes are never shown and an Administrator sees no case content (design flows A5).
 */
export function AuditPage({ api, lang, role }: AuditPageProps) {
  const [draft, setDraft] = useState<Filters>(NO_FILTERS);
  const [applied, setApplied] = useState<Filters>(NO_FILTERS);
  const [dateProblem, setDateProblem] = useState(false);
  const [namesAttempt, setNamesAttempt] = useState(0);
  const [verify, setVerify] = useState<Verify>({ state: "idle" });

  const names = useNames(api, role === "SENIOR" || role === "ADMIN", namesAttempt);
  const nameOf = useMemo(() => {
    const map = new Map<string, string>();
    if (names.state === "ready") for (const u of names.users) map.set(u.user_id, u.display_name);
    return map;
  }, [names]);

  const fetchPage = useCallback(
    (cursor?: string) =>
      api.client.listAudit({
        limit: PAGE,
        sort: "occurred_at",
        order: "desc",
        ...(applied.from ? { occurred_from: startOf(applied.from) } : {}),
        ...(applied.to ? { occurred_to: endOf(applied.to) } : {}),
        ...(applied.person ? { actor_user_id: applied.person } : {}),
        ...(applied.action ? { event_type: applied.action as Row["event_type"] } : {}),
        ...(cursor ? { cursor } : {}),
      }),
    [api, applied],
  );
  const list = usePagedList<Row>(fetchPage);

  const show = () => {
    if (draft.from && draft.to && draft.from > draft.to) return setDateProblem(true);
    setDateProblem(false);
    setApplied(draft);
  };

  const check = async () => {
    setVerify({ state: "working" });
    const result = await api.client.verifyAuditChain();
    if (result.kind !== "ok") return setVerify({ state: "failed", result });
    setVerify(
      result.data.result === "OK"
        ? { state: "ok" }
        : {
            state: "broken",
            firstBad:
              typeof result.data.first_bad_seq === "number" ? result.data.first_bad_seq : undefined,
          },
    );
  };

  const person = (row: Row): string => {
    if (row.actor.kind === "SYSTEM") return t("audit.person.system", lang);
    if (row.actor.kind === "ANONYMOUS") return t("audit.person.anonymous", lang);
    const named = row.actor.user_id ? nameOf.get(row.actor.user_id) : undefined;
    if (named) return named;
    // No name to give: the role in words, never the code.
    return row.actor.role
      ? t(`role.${row.actor.role.toLowerCase()}` as AnyMessageKey, lang)
      : t("audit.person.unknown", lang);
  };

  const columns = [
    {
      id: "time",
      header: t("audit.col.time", lang),
      cell: (r: Row) => dateTime(r.occurred_at, lang),
    },
    { id: "person", header: t("audit.col.person", lang), cell: person },
    {
      id: "action",
      header: t("audit.col.action", lang),
      cell: (r: Row) => (
        <>
          <span>{t(EVENT_WORDS[r.event_type], lang)}</span>
          {r.outcome !== "SUCCESS" ? (
            <>
              {" "}
              <span>{t(`audit.outcome.${r.outcome}` as AnyMessageKey, lang)}</span>
            </>
          ) : null}
        </>
      ),
    },
    // An Administrator has no case rights, so no case is drawn for them.
    ...(role === "ADMIN"
      ? []
      : [
          {
            id: "case",
            header: t("audit.col.case", lang),
            cell: (r: Row) =>
              r.refs.length > 0 ? r.refs.map((ref) => ref.case_id).join(", ") : NO_VALUE,
          },
        ]),
    {
      id: "item",
      header: t("audit.col.item", lang),
      cell: (r: Row) => (r.target_type ? t(TARGET_WORDS[r.target_type], lang) : NO_VALUE),
    },
  ];

  return (
    <div className="admin-page">
      <h2 className="admin-panel-title">{t("audit.title", lang)}</h2>
      <p>{t("audit.cannotChange", lang)}</p>
      {names.state === "failed" ? (
        <FailureView
          result={names.result}
          lang={lang}
          onRetry={() => setNamesAttempt((n) => n + 1)}
        />
      ) : null}
      <form
        className="admin-filters"
        onSubmit={(event) => {
          event.preventDefault();
          show();
        }}
      >
        <TextField
          type="date"
          label={t("audit.filter.from", lang)}
          value={draft.from}
          onChange={(from) => setDraft((d) => ({ ...d, from }))}
        />
        <TextField
          type="date"
          label={t("audit.filter.to", lang)}
          value={draft.to}
          error={dateProblem ? t("audit.error.dates", lang) : undefined}
          onChange={(to) => setDraft((d) => ({ ...d, to }))}
        />
        {names.state === "ready" ? (
          <Select
            label={t("audit.filter.person", lang)}
            value={draft.person}
            options={[
              { value: "", label: t("audit.filter.anyone", lang) },
              ...[...names.users]
                .sort((a, b) => a.display_name.localeCompare(b.display_name))
                .map((u) => ({ value: u.user_id, label: u.display_name })),
            ]}
            onChange={(person) => setDraft((d) => ({ ...d, person }))}
          />
        ) : null}
        <Select
          label={t("audit.filter.action", lang)}
          value={draft.action}
          options={[
            { value: "", label: t("audit.filter.any", lang) },
            ...EVENT_TYPES.map((type) => ({ value: type, label: t(EVENT_WORDS[type], lang) })),
          ]}
          onChange={(action) => setDraft((d) => ({ ...d, action }))}
        />
        <Button variant="primary" type="submit">
          {t("audit.filter.apply", lang)}
        </Button>
      </form>
      {role === "SENIOR" ? (
        <div className="admin-actions">
          <Button
            variant="secondary"
            disabled={verify.state === "working"}
            onClick={() => void check()}
          >
            {t(verify.state === "working" ? "audit.verify.working" : "audit.verify", lang)}
          </Button>
        </div>
      ) : null}
      {verify.state === "ok" ? (
        <Message kind="success">{t("audit.verify.ok", lang)}</Message>
      ) : null}
      {verify.state === "broken" ? (
        <Message kind="error">
          <span>{t("audit.verify.broken", lang)}</span>
          {verify.firstBad !== undefined ? (
            <>
              {" "}
              <span>{t("audit.verify.brokenAt", lang, { n: verify.firstBad })}</span>
            </>
          ) : null}
        </Message>
      ) : null}
      {verify.state === "failed" ? <FailureView result={verify.result} lang={lang} /> : null}
      <PagedView lang={lang} list={list} empty={t("audit.empty", lang)}>
        {(rows) => (
          <Table
            caption={t("audit.title", lang)}
            rows={rows}
            rowKey={(row) => row.row_ref}
            columns={columns}
          />
        )}
      </PagedView>
    </div>
  );
}
