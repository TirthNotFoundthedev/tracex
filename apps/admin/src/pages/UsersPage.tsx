import { Badge, Button, Checkbox, Loading, Message, Select, Table, TextField } from "@tracex/ui";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AdminApi } from "../api";
import type { ApiResult } from "../api/http";
import type { FailureResult } from "../api/resultKeys";
import type { components } from "../api/schema";
import { FailureView } from "../components/FailureView";
import { t, type AnyMessageKey, type Language, type MessageKey } from "../i18n";
import type { Role } from "../nav";
import { PagedView, usePagedList, type PageShape } from "../usePagedList";
import {
  areaNeededForRoleChange,
  buildAreaChange,
  buildCreate,
  buildRoleChange,
  nameFits,
  usernameFits,
  coverageOf,
  EMPTY_AREA,
  type AreaDraft,
  type Scope,
} from "./userChange";

type User = components["schemas"]["User"];
type Change = components["schemas"]["PendingChange"];
type StateRow = components["schemas"]["State"];
type Proposal = components["schemas"]["ProposeChangeRequest"];

const PAGE = 50;
/** The change list is read at the contract's largest page. */
const PENDING_LIMIT = 100;
/** A stop for a list that never ends. */
const PENDING_MAX_PAGES = 100;
const ROLES: Role[] = ["JUNIOR", "INVESTIGATOR", "SUPERVISOR", "SENIOR", "ADMIN"];

const roleWord = (role: Role, lang: Language) =>
  t(`role.${role.toLowerCase()}` as AnyMessageKey, lang);
const roleSentence = (role: Role, lang: Language) =>
  t(`users.role.${role.toLowerCase()}` as MessageKey, lang);

interface Reference {
  scopes: Map<Role, Scope>;
  states: StateRow[];
  districts: Map<string, string>;
  stateNames: Map<string, string>;
  pending: Change[];
}

type RefLoad =
  | { state: "loading" }
  | { state: "failed"; result: FailureResult }
  | { state: "ready"; ref: Reference };

/**
 * Every change, waiting or decided (no state filter). The list is read to its last page, so no tag is missing and no second
 * proposal slips through.
 */
async function readAllPending(api: AdminApi): Promise<ApiResult<Change[]>> {
  const all: Change[] = [];
  let cursor: string | undefined;
  for (let page = 0; page < PENDING_MAX_PAGES; page++) {
    const result = await api.client.listPendingChanges({
      limit: PENDING_LIMIT,
      ...(cursor ? { cursor } : {}),
    });
    if (result.kind !== "ok") return result;
    all.push(...result.data.items);
    cursor = result.data.next_cursor ?? undefined;
    if (!cursor) return { kind: "ok", data: all };
  }
  // The cap is reached with pages left: a tag could be missing or wrong, so the page fails instead of guessing.
  return { kind: "serverError" };
}

/**
 * Which of two changes about one user is the newer. By proposal time; at the same time a waiting change
 * wins (a waiting tag is never hidden by a decided change), then the higher change id, so the result does not
 * depend on the order of the list. The backend sorts `proposed_at DESC, id`.
 */
function isNewer(a: Change, b: Change): boolean {
  const byTime = Date.parse(a.proposed_at) - Date.parse(b.proposed_at);
  if (byTime !== 0) return byTime > 0;
  const aWaiting = a.state === "PENDING";
  if (aWaiting !== (b.state === "PENDING")) return aWaiting;
  return a.change_id > b.change_id;
}

/**
 * Role scopes, area names and the waiting changes: one call each (the waiting list, one per page), once per visit. The tags on the table
 * rows come from the one list of waiting changes, never from a read of each user (D69, D71).
 */
function useReference(api: AdminApi, attempt: number): RefLoad {
  const [load, setLoad] = useState<RefLoad>({ state: "loading" });
  useEffect(() => {
    let live = true;
    setLoad({ state: "loading" });
    void Promise.all([
      api.client.listRoles(),
      api.client.listJurisdictions(),
      readAllPending(api),
    ]).then(([roles, areas, pending]) => {
      if (!live) return;
      if (roles.kind !== "ok") return setLoad({ state: "failed", result: roles });
      if (areas.kind !== "ok") return setLoad({ state: "failed", result: areas });
      if (pending.kind !== "ok") return setLoad({ state: "failed", result: pending });
      setLoad({
        state: "ready",
        ref: {
          scopes: new Map(roles.data.items.map((r) => [r.role, r.scope] as const)),
          states: areas.data.items,
          districts: new Map(
            areas.data.items.flatMap((s) =>
              s.districts.map((d) => [d.district_id, d.name] as const),
            ),
          ),
          stateNames: new Map(areas.data.items.map((s) => [s.state_id, s.name] as const)),
          pending: pending.data,
        },
      });
    });
    return () => {
      live = false;
    };
  }, [api, attempt]);
  return load;
}

/** The words for a user's area: a district name, "All areas", a list of names, or "No area" for an administrator. */
function areaText(user: User, ref: Reference, lang: Language): string {
  if (user.district_id) {
    return ref.districts.get(user.district_id) ?? t("approvals.area.unknown", lang);
  }
  const coverage = user.coverage;
  if (coverage) {
    if (coverage.all_states === true) return t("users.coverage.all", lang);
    const names = [
      ...coverage.state_ids.map((id) => ref.stateNames.get(id)),
      ...coverage.district_ids.map((id) => ref.districts.get(id)),
    ].map((name) => name ?? t("approvals.area.unknown", lang));
    if (names.length > 0) return names.join(", ");
  }
  return t("approvals.area.none", lang);
}

function draftOf(user: User): AreaDraft {
  return {
    districtId: user.district_id ?? "",
    all: user.coverage?.all_states === true,
    stateIds: user.coverage?.state_ids ?? [],
    districtIds: user.coverage?.district_ids ?? [],
  };
}

const sameCoverage = (a: AreaDraft, b: AreaDraft) =>
  JSON.stringify(coverageOf(a) ?? null) === JSON.stringify(coverageOf(b) ?? null);

function PendingTag({ lang }: { lang: Language }) {
  return <Badge icon="pending">{t("approvals.tag.waiting", lang)}</Badge>;
}

/** The contract keeps no refusal reason (the deny route takes no body, D71), so the tag has words only. */
function RefusedTag({ lang }: { lang: Language }) {
  return (
    <Badge icon="reject" kind="danger">
      {t("approvals.tag.refused", lang)}
    </Badge>
  );
}

// ---------------------------------------------------------------- the area pickers

function CoveragePicker({
  lang,
  states,
  value,
  error,
  onChange,
}: {
  lang: Language;
  states: StateRow[];
  value: AreaDraft;
  error: string | undefined;
  onChange: (next: AreaDraft) => void;
}) {
  const toggle = (list: string[], id: string, on: boolean) =>
    on ? [...new Set([...list, id])] : list.filter((x) => x !== id);
  return (
    <fieldset className="admin-coverage">
      <legend>{t("users.field.area", lang)}</legend>
      <Checkbox
        label={t("users.coverage.all", lang)}
        checked={value.all}
        onChange={(all) => onChange({ ...value, all })}
      />
      {value.all
        ? null
        : states.map((state) => (
            <div key={state.state_id} className="admin-coverage__state">
              <Checkbox
                label={state.name}
                checked={value.stateIds.includes(state.state_id)}
                onChange={(on) =>
                  onChange({ ...value, stateIds: toggle(value.stateIds, state.state_id, on) })
                }
              />
              <div className="admin-coverage__districts">
                {state.districts.map((district) => (
                  <Checkbox
                    key={district.district_id}
                    label={district.name}
                    checked={value.districtIds.includes(district.district_id)}
                    onChange={(on) =>
                      onChange({
                        ...value,
                        districtIds: toggle(value.districtIds, district.district_id, on),
                      })
                    }
                  />
                ))}
              </div>
            </div>
          ))}
      {error ? (
        <p className="admin-error" role="alert">
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}

function DistrictPicker({
  lang,
  states,
  value,
  error,
  onChange,
}: {
  lang: Language;
  states: StateRow[];
  value: string;
  error: string | undefined;
  onChange: (districtId: string) => void;
}) {
  return (
    <Select
      label={t("users.field.area", lang)}
      value={value}
      options={[
        { value: "", label: t("users.area.choose", lang) },
        ...states.flatMap((state) =>
          state.districts.map((district) => ({
            value: district.district_id,
            label: `${district.name} (${state.name})`,
          })),
        ),
      ]}
      error={error}
      onChange={onChange}
    />
  );
}

// ---------------------------------------------------------------- the form

const KIND_OF_SCOPE = { DISTRICT: "district", COVERAGE: "coverage", NONE: "none" } as const;

/**
 * What the area part of the form asks for. A new user, or a user whose role stays, follows the role's
 * scope. A role change asks only for what the change must carry (D72): coverage to SENIOR, a district from
 * SENIOR or ADMIN to a district role. Between two district roles the area stays as it is ("later").
 */
function areaKindOf(
  user: User | undefined,
  role: Role | "",
  scopeOf: (role: Role) => Scope,
): "district" | "coverage" | "later" | "none" {
  if (!role) return "none";
  if (!user || role === user.role) return KIND_OF_SCOPE[scopeOf(role)];
  const needed = areaNeededForRoleChange(user.role, role, scopeOf);
  if (needed !== "none") return needed;
  return scopeOf(role) === "DISTRICT" ? "later" : "none";
}

type Mode = { kind: "new" } | { kind: "user"; user: User };

/**
 * Opening a user reads that one user and builds the form from the answer: a list row can be stale, and a
 * changed coverage is sent back as a whole replacement. Only on open, never per row (D69).
 */
function FreshUser({
  api,
  lang,
  mode,
  onBack,
  children,
}: {
  api: AdminApi;
  lang: Language;
  mode: Mode;
  onBack: () => void;
  children: (mode: Mode) => React.ReactNode;
}) {
  const id = mode.kind === "user" ? mode.user.user_id : undefined;
  const [attempt, setAttempt] = useState(0);
  const [read, setRead] = useState<
    | { state: "loading" }
    | { state: "failed"; result: FailureResult }
    | { state: "ready"; user: User }
  >({ state: "loading" });
  useEffect(() => {
    if (!id) return;
    let live = true;
    setRead({ state: "loading" });
    void api.client.getUser(id).then((result) => {
      if (!live) return;
      setRead(
        result.kind === "ok" ? { state: "ready", user: result.data } : { state: "failed", result },
      );
    });
    return () => {
      live = false;
    };
  }, [api, id, attempt]);

  if (!id) return <>{children(mode)}</>;
  if (read.state === "loading") return <Loading label={t("loading.default", lang)} />;
  if (read.state === "failed") {
    return (
      <>
        <FailureView result={read.result} lang={lang} onRetry={() => setAttempt((n) => n + 1)} />
        <div className="admin-actions">
          <Button variant="secondary" onClick={onBack}>
            {t("state.backToList", lang)}
          </Button>
        </div>
      </>
    );
  }
  return <>{children({ kind: "user", user: read.user })}</>;
}

interface FormProps {
  api: AdminApi;
  lang: Language;
  mode: Mode;
  /** Only an administrator proposes changes; a senior officer reads. */
  canEdit: boolean;
  reference: Reference;
  waiting: Change | undefined;
  refused: boolean;
  onSent: (change: Change) => void;
  onBack: () => void;
}

function UserForm({
  api,
  lang,
  mode,
  canEdit,
  reference,
  waiting,
  refused,
  onSent,
  onBack,
}: FormProps) {
  const user = mode.kind === "user" ? mode.user : undefined;
  const scopeOf = useCallback(
    (role: Role): Scope => reference.scopes.get(role) ?? "NONE",
    [reference],
  );
  const initialArea = useMemo(() => (user ? draftOf(user) : EMPTY_AREA), [user]);

  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [role, setRole] = useState<Role | "">(user?.role ?? "");
  const [area, setArea] = useState<AreaDraft>(initialArea);
  const [bad, setBad] = useState<{
    name?: boolean;
    username?: boolean;
    role?: boolean;
    area?: boolean;
  }>({});
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<FailureResult | undefined>();
  const [sentNow, setSentNow] = useState(false);
  const [step, setStep] = useState<"view" | "confirm">("view");

  const roleChanged = !!user && role !== user.role;
  // What the area part of the form asks for, by the role chosen and the role the user has now.
  const areaKind = areaKindOf(user, role, scopeOf);

  const changeRole = (next: string) => {
    const nextRole = (next || "") as Role | "";
    const scopeNow = role ? scopeOf(role) : undefined;
    setRole(nextRole);
    setBad((b) => ({ ...b, role: false, area: false }));
    if (user && nextRole === user.role) return setArea(initialArea);
    // A district picked for one kind of role is not carried to the other kind.
    if (!user && nextRole && scopeOf(nextRole) === scopeNow) return;
    setArea(EMPTY_AREA);
  };

  const dirty =
    !!user &&
    (roleChanged ||
      (areaKind === "district" && area.districtId !== initialArea.districtId) ||
      (areaKind === "coverage" && !sameCoverage(area, initialArea)));

  const send = async (body: Proposal) => {
    setBusy(true);
    setFailure(undefined);
    const result = await api.client.proposeChange(body);
    setBusy(false);
    setStep("view");
    if (result.kind === "invalid") {
      setBad({
        username: result.fieldErrors.some((e) => e.field.endsWith("username")),
        name: result.fieldErrors.some((e) => e.field.endsWith("display_name")),
        role: result.fieldErrors.some((e) => e.field.endsWith("role")),
        area: result.fieldErrors.some((e) =>
          /district_id|coverage|state_ids|all_states/.test(e.field),
        ),
      });
      return setFailure(result);
    }
    if (result.kind !== "ok") return setFailure(result);
    setSentNow(true);
    onSent(result.data);
  };

  const areaError = (): string | undefined =>
    bad.area
      ? t(areaKind === "coverage" ? "users.error.coverage" : "users.error.area", lang)
      : undefined;

  // A role /roles does not list has no known scope, so nothing is built or sent for it.
  const roleKnown = !role || reference.scopes.has(role);

  const save = () => {
    setFailure(undefined);
    if (!roleKnown) return;
    if (!user) {
      const built = buildCreate({ name, username, role, scopeOf, area });
      setBad({
        name: !nameFits(name.trim()),
        username: !usernameFits(username.trim()),
        role: !role,
        area: !built.ok && built.field === "area",
      });
      if (!built.ok) return;
      return void send(built.body);
    }
    const built = roleChanged
      ? buildRoleChange({
          subjectId: user.user_id,
          from: user.role,
          to: role as Role,
          scopeOf,
          area,
        })
      : buildAreaChange({ subjectId: user.user_id, role: user.role, scopeOf, area });
    setBad({ area: !built.ok });
    if (!built.ok) return;
    void send(built.body);
  };

  const turn = () =>
    user &&
    void send({
      kind: user.active ? "USER_DISABLE" : "USER_ENABLE",
      subject_user_id: user.user_id,
    });

  const pendingNow = waiting !== undefined;
  const showSent = (canEdit && pendingNow) || sentNow;

  // A new user that was sent shows the message and nothing to fill in again.
  if (!user && sentNow) {
    return (
      <div className="admin-detail">
        <Message kind="info">{t("approvals.sent", lang)}</Message>
        <PendingTag lang={lang} />
        <div className="admin-actions">
          <Button variant="secondary" onClick={onBack}>
            {t("state.backToList", lang)}
          </Button>
        </div>
      </div>
    );
  }

  const areaPicker =
    areaKind === "district" ? (
      <DistrictPicker
        lang={lang}
        states={reference.states}
        value={area.districtId}
        error={areaError()}
        onChange={(districtId) => {
          setBad((b) => ({ ...b, area: false }));
          setArea({ ...area, districtId });
        }}
      />
    ) : areaKind === "coverage" ? (
      <CoveragePicker
        lang={lang}
        states={reference.states}
        value={area}
        error={areaError()}
        onChange={(next) => {
          setBad((b) => ({ ...b, area: false }));
          setArea(next);
        }}
      />
    ) : areaKind === "later" ? (
      <p className="admin-hint">{t("users.areaLater", lang)}</p>
    ) : null;

  return (
    <div className="admin-detail">
      {user ? (
        <dl className="admin-values">
          <dt>{t("users.field.name", lang)}</dt>
          <dd>{user.display_name}</dd>
          <dt>{t("users.field.userId", lang)}</dt>
          <dd>{user.username}</dd>
          <dt>{t("common.status", lang)}</dt>
          <dd>{t(user.active ? "users.status.active" : "users.status.off", lang)}</dd>
          {user.assignment_count !== undefined ? (
            <>
              <dt>{t("users.col.cases", lang)}</dt>
              <dd>{t("users.cases", lang, { n: user.assignment_count })}</dd>
            </>
          ) : null}
          {!canEdit ? (
            <>
              <dt>{t("users.field.role", lang)}</dt>
              <dd>{roleWord(user.role, lang)}</dd>
              <dt>{t("users.field.area", lang)}</dt>
              <dd>{areaText(user, reference, lang)}</dd>
            </>
          ) : null}
        </dl>
      ) : null}
      {showSent ? <Message kind="info">{t("approvals.sent", lang)}</Message> : null}
      {pendingNow || sentNow ? <PendingTag lang={lang} /> : null}
      {refused && !pendingNow && !sentNow ? <RefusedTag lang={lang} /> : null}
      {failure ? <FailureView result={failure} lang={lang} /> : null}
      {canEdit ? (
        <form
          className="admin-form"
          onSubmit={(event) => {
            event.preventDefault();
            save();
          }}
        >
          {!user ? (
            <>
              <TextField
                label={t("users.field.name", lang)}
                value={name}
                error={
                  bad.name
                    ? name.trim()
                      ? t("users.error.nameLong", lang)
                      : t("common.fillIn", lang, { field: t("users.field.name", lang) })
                    : undefined
                }
                onChange={(value) => {
                  setName(value);
                  setBad((b) => ({ ...b, name: false }));
                }}
              />
              <TextField
                label={t("users.field.userId", lang)}
                value={username}
                error={
                  bad.username
                    ? username.trim()
                      ? usernameFits(username.trim())
                        ? t("users.error.userId", lang)
                        : t("users.error.userIdFormat", lang)
                      : t("common.fillIn", lang, { field: t("users.field.userId", lang) })
                    : undefined
                }
                onChange={(value) => {
                  setUsername(value);
                  setBad((b) => ({ ...b, username: false }));
                }}
              />
            </>
          ) : null}
          <Select
            label={t("users.field.role", lang)}
            value={role}
            options={[
              { value: "", label: t("users.role.choose", lang) },
              // Only roles that /roles lists can be chosen.
              ...ROLES.filter((r) => reference.scopes.has(r)).map((r) => ({
                value: r,
                label: roleSentence(r, lang),
              })),
            ]}
            error={bad.role ? t("users.error.role", lang) : undefined}
            onChange={changeRole}
          />
          {!roleKnown ? (
            <p className="admin-error" role="alert">
              {t("users.error.roleUnknown", lang)}
            </p>
          ) : null}
          {areaPicker}
          {role === "ADMIN" ? <p className="admin-hint">{t("users.noCaseContent", lang)}</p> : null}
          <div className="admin-actions">
            <Button
              variant="primary"
              type="submit"
              icon="confirm"
              disabled={busy || pendingNow || !roleKnown || (!!user && !dirty)}
            >
              {t("users.save", lang)}
            </Button>
          </div>
        </form>
      ) : null}
      {canEdit && user && step === "view" ? (
        <div className="admin-actions">
          <Button
            variant={user.active ? "danger" : "secondary"}
            disabled={busy || pendingNow}
            onClick={() => setStep("confirm")}
          >
            {t(user.active ? "users.turnOff" : "users.turnOn", lang)}
          </Button>
        </div>
      ) : null}
      {canEdit && user && step === "confirm" ? (
        <div className="admin-form">
          <p>
            {t(user.active ? "users.turnOff.confirm" : "users.turnOn.confirm", lang, {
              name: user.display_name,
            })}
          </p>
          {user.active ? <p>{t("approvals.turnoff.warn", lang)}</p> : null}
          <div className="admin-actions">
            <Button variant="primary" icon="confirm" disabled={busy} onClick={turn}>
              {t("approvals.turnoff.yes", lang)}
            </Button>
            <Button variant="secondary" disabled={busy} onClick={() => setStep("view")}>
              {t("confirm.no", lang)}
            </Button>
          </div>
        </div>
      ) : null}
      {!canEdit ? <p>{t("users.readOnly", lang)}</p> : null}
      <div className="admin-actions">
        <Button variant="secondary" onClick={onBack}>
          {t("state.backToList", lang)}
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- the page

interface UsersPageProps {
  api: AdminApi;
  lang: Language;
  role: Role;
}

/**
 * A5 Users and roles. An administrator proposes (add, role, area, turn on or off) and a Senior officer
 * decides on the Approvals page (D35); a Senior officer reads the users inside their coverage. The form
 * always sends exactly one of `district_id` or `coverage` where the role has an area (see userChange.ts).
 * Opening a row reads that one user (never one per row, D69).
 */
export function UsersPage({ api, lang, role }: UsersPageProps) {
  const [attempt, setAttempt] = useState(0);
  const refLoad = useReference(api, attempt);
  const [mode, setMode] = useState<Mode | undefined>();
  // Changes this person sent during this visit, added to the list read at the start.
  const [sent, setSent] = useState<Change[]>([]);

  const fetchPage = useCallback(
    (cursor?: string) => api.client.listUsers({ limit: PAGE, ...(cursor ? { cursor } : {}) }),
    [api],
  );
  const list = usePagedList<User>(
    fetchPage as (cursor?: string) => Promise<ApiResult<PageShape<User>>>,
  );

  const knownChanges = useMemo(
    () => (refLoad.state === "ready" ? [...refLoad.ref.pending, ...sent] : sent),
    [refLoad, sent],
  );
  const bySubject = useMemo(() => {
    const map = new Map<string, Change>();
    for (const change of knownChanges) {
      if (change.state === "PENDING" && change.subject) map.set(change.subject.user_id, change);
    }
    return map;
  }, [knownChanges]);
  // A user shows "Change refused" when the newest change about them (by proposal time) was refused.
  const refusedSubjects = useMemo(() => {
    const latest = new Map<string, Change>();
    for (const change of knownChanges) {
      const id = change.subject?.user_id;
      if (!id) continue;
      const seen = latest.get(id);
      if (!seen || isNewer(change, seen)) {
        latest.set(id, change);
      }
    }
    return new Set([...latest].filter(([, c]) => c.state === "DENIED").map(([id]) => id));
  }, [knownChanges]);
  const newUsers = knownChanges.filter((c) => c.kind === "USER_CREATE" && c.state === "PENDING");

  if (refLoad.state === "loading") return <Loading label={t("loading.default", lang)} />;
  if (refLoad.state === "failed") {
    return (
      <FailureView result={refLoad.result} lang={lang} onRetry={() => setAttempt((n) => n + 1)} />
    );
  }
  const reference = refLoad.ref;
  const canEdit = role === "ADMIN";

  if (mode) {
    return (
      <div className="admin-page">
        <h2 className="admin-panel-title">{t("users.title", lang)}</h2>
        <FreshUser
          key={mode.kind === "user" ? mode.user.user_id : "new"}
          api={api}
          lang={lang}
          mode={mode}
          onBack={() => setMode(undefined)}
        >
          {(fresh) => (
            <UserForm
              api={api}
              lang={lang}
              mode={fresh}
              canEdit={canEdit}
              reference={reference}
              waiting={fresh.kind === "user" ? bySubject.get(fresh.user.user_id) : undefined}
              refused={fresh.kind === "user" && refusedSubjects.has(fresh.user.user_id)}
              onSent={(change) => setSent((now) => [...now, change])}
              onBack={() => setMode(undefined)}
            />
          )}
        </FreshUser>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <h2 className="admin-panel-title">{t("users.title", lang)}</h2>
      {canEdit ? <p>{t("users.noCaseContent", lang)}</p> : null}
      {canEdit ? (
        <div className="admin-actions">
          <Button variant="primary" icon="person" onClick={() => setMode({ kind: "new" })}>
            {t("users.add", lang)}
          </Button>
        </div>
      ) : null}
      {newUsers.length > 0 ? (
        <ul className="admin-plain">
          {newUsers.map((change) => (
            <li key={change.change_id}>
              {t("approvals.change.userCreate", lang, {
                name: String((change.new_value as { display_name?: unknown }).display_name ?? ""),
              })}{" "}
              <PendingTag lang={lang} />
            </li>
          ))}
        </ul>
      ) : null}
      <PagedView lang={lang} list={list} empty={t("users.empty", lang)}>
        {(items) => (
          <Table
            caption={t("users.title", lang)}
            rows={items}
            rowKey={(row) => row.user_id}
            onOpenRow={(user) => setMode({ kind: "user", user })}
            columns={[
              { id: "name", header: t("users.col.name", lang), cell: (u) => u.display_name },
              { id: "userId", header: t("users.col.userId", lang), cell: (u) => u.username },
              {
                id: "role",
                header: t("users.col.role", lang),
                cell: (u) => roleWord(u.role, lang),
              },
              {
                id: "area",
                header: t("users.col.area", lang),
                cell: (u) => areaText(u, reference, lang),
              },
              {
                id: "status",
                header: t("users.col.status", lang),
                cell: (u) => (
                  <span className="admin-status">
                    <span>{t(u.active ? "users.status.active" : "users.status.off", lang)}</span>
                    {bySubject.has(u.user_id) ? (
                      <PendingTag lang={lang} />
                    ) : refusedSubjects.has(u.user_id) ? (
                      <RefusedTag lang={lang} />
                    ) : null}
                  </span>
                ),
              },
            ]}
          />
        )}
      </PagedView>
    </div>
  );
}
