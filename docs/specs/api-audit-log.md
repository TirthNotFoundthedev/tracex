# Spec: API audit log

Owner: Khan (Backend Lead). Status: DRAFT, revised after Security Reviewer findings. Task P1.3. Encoded as table-driven tests in `backend/tests/`. Companion: `api-access-control.md` (role names, relations, R-rules are defined there).

## 1. Purpose
Show who knew what, and when. Every significant action and every access decision (allowed, redacted, denied) is recorded. The log is append-only and tamper-evident: a Postgres table where UPDATE, DELETE and TRUNCATE are blocked, rows are hash-chained, and the head is anchored outside the database. It stores ids and facts, never personal values. The log itself must not leak: a reader sees a row only under the row-level rule of section 7, and never learns that other rows exist.

## 2. Row schema: table `audit_log`
Class (used by section 7 when a row is shown but references a case the reader cannot see): **A** actor and event; **S** side, tied to one case in `refs`; **J** joint, tied to the link or request as a whole; **P** private, never returned by the API.

| Column | Type | Class | Meaning |
|---|---|---|---|
| `seq` | bigint, primary key | P | Contiguous from 1, previous + 1, assigned in the append step. Readers get an opaque `row_ref` (HMAC of `seq` and reader id, server key) and an opaque paging cursor; `seq` is never returned, so gaps reveal nothing |
| `event_id` | uuid, unique | P | Random |
| `occurred_at` | timestamptz | A | Database clock, UTC. Client times ignored |
| `event_type`, `outcome` | text | A | Section 3; `SUCCESS`, `DENIED`, `FAILED` |
| `actor_kind`, `actor_user_id`, `actor_role`, `actor_district_id` | text, uuid | A | `USER`, `SYSTEM`, `ANONYMOUS`; role and district as at the event |
| `reason_code` | text, null | A | Policy rule (`R2_NOT_VISIBLE`, `MATRIX_DENY`, `GRANT_ACTIVE`, ...) |
| `refs` | jsonb | S | Every case the row references: `[{case_id, district_id}]`, including both ends of a link or the far case of a request. Empty for system events and for R2_NOT_VISIBLE denials (see W3) |
| `target_type`, `target_id` | text | S for `CASE`, `ENTITY`, `DOCUMENT`; J for `LINK`, `STUB`, `ACCESS_REQUEST`, `GRANT`; A otherwise | Target type: `CASE`, `ENTITY`, `LINK`, `STUB`, `DOCUMENT`, `USER`, `ACCESS_REQUEST`, `GRANT`, `BATCH`, `RUN`, `SETTING`, `CHANGE`, `AUDIT`, `UNRESOLVED` |
| `detail` | jsonb | per key | Only keys listed in section 3; keys marked `*` are class J, keys marked `^` are class P (stored, **never returned**: every key that carries a sequence number or chain position), others S (or A if no case is involved); unknown keys rejected. Each key has an owning case or case set, kept in the registry `audit_detail_key_owner` (`owner_ref` may be "every end of the link" for joint keys) |
| `session_id`, `request_id`, `client_ip` | uuid, inet | P | Kept for forensics through database access only |
| `row_nonce` | bytea(16) | P | Random 128-bit value per row, inside the hashed content |
| `prev_hash`, `row_hash` | bytea(32) | P | Section 4. Never returned by any endpoint |

## 3. Events
The row commits in the same transaction as the action unless noted. Detail keys marked `*` are joint. `via_grant` (bool) is on every view event.

| Event | Written when | Target | `detail` keys |
|---|---|---|---|
| AUDIT_CHAIN_STARTED | Once, by migration | none | `schema_version` |
| AUTH_LOGIN_SUCCESS / _LOGOUT / _REFRESHED | Login, logout, refresh rotated | USER | none |
| AUTH_LOGIN_FAILED | Login rejected or throttled | none | `claimed_username` (raw only if it equals an existing username, section 6), `throttled` |
| AUTH_TOKEN_REJECTED | Token missing, malformed, expired, bad signature, stale `ver`, dead `sid` | none | `failure`, `claimed_sub` |
| AUTH_REFRESH_REUSED | A rotated refresh token is presented again; `sid` revoked | USER | none |
| CASE_LISTED | Case list returned | none | `case_ids` (max 500) |
| CASE_ENTITIES_VIEWED | Case entity list returned | CASE | `entity_ids` (max 500) |
| ENTITY_VIEWED | Entity detail returned | ENTITY | `link_ids_shown*`, `stub_ids_shown*` |
| LINK_VIEWED | Link returned in full | LINK | none |
| STUB_VIEWED | One event per response that shows stubs (entity detail, link list, `GET /stubs/{id}`) | none | `stub_ids*`, `near_entity_ids` |
| ACCESS_REQUEST_VIEWED | Access-request list or detail returned (requester or approver view); replaces STUB_VIEWED on those routes | none | `request_ids*`, `stub_ids*`, `near_entity_ids` |
| GRANT_VIEWED | Grant list or detail returned | none | `grant_ids*`, `link_ids*` |
| CHANGE_VIEWED | Pending-change list or detail returned | none | `change_ids`, `case_ids` (of any assignment change) |
| GRAPH_VIEWED | Graph neighbours returned | ENTITY | `entity_ids`, `link_ids*`, `stub_ids*` |
| REVIEW_QUEUE_VIEWED | Review queue page returned | none | `link_ids*` |
| EXPLANATION_VIEWED | Explanation returned | LINK | none |
| SOURCE_LINES_VIEWED | Source lines returned | DOCUMENT | `line_from`, `line_to` |
| SEARCH_RUN | Search executed | none | `entity_ids` returned (max 500), `entity_type_filter` |
| ACCESS_DENIED | Any request refused by policy, including 404 for hidden ids, 403 for role | as attempted | `action`, `http_status` |
| LINKS_LISTED | Link-list response returned | none | `link_ids*`, `stub_ids*` |
| LINK_AUTO_CREATED / LINK_SUGGESTED | API records an engine transition (create) | LINK | `run_id*`, `band*`, `score*`, `entity_ids*` |
| LINK_DEMOTED | API records an engine demotion (AUTO to SUGGESTED, threshold change or lost evidence) | LINK | `run_id*`, `previous_state*`, `new_state*`, `cause` |
| LINK_PROMOTED | API records an engine promotion (SUGGESTED to AUTO on a rerun) | LINK | `run_id*`, `previous_state*`, `new_state*` |
| LINK_WITHDRAWN | API records an engine withdrawal (a SUGGESTED edge fell below the medium threshold; the row stays in state WITHDRAWN, not block-listed) | LINK | `run_id*`, `previous_state*` |
| LINK_CONFIRMED / _REJECTED / _UNDONE / _REOPENED | Officer decides | LINK | `previous_state*`, `new_state*` |
| ACCESS_REQUEST_CREATED / _WITHDRAWN / _EXPIRED | Request lifecycle (one link, one far case) | ACCESS_REQUEST | `stub_id*` |
| ACCESS_REQUEST_APPROVED / _REJECTED | Approver decides | ACCESS_REQUEST | `grant_id*`, `expires_at` (approve) |
| ACCESS_GRANT_REVOKED / _EXPIRED / _CLOSED | Revoked, expired, or closed by the system | GRANT | `cause` (`MANUAL`, `ROLE_CHANGE`, `LINK_CLOSED`, `EVIDENCE_CHANGED`, `TIME`) |
| DATA_UPLOADED | Upload accepted. `refs` holds the target case, so that case's SUPERVISOR sees under rule (c) that material was added | BATCH | `file_sha256`, `byte_count`, `document_count` |
| MATCHING_RUN_STARTED / _COMPLETED | Run begins / ends | RUN | `thresholds_version`; completed adds `auto_count`, `suggested_count` (system-wide) |
| CHANGE_PROPOSED / _APPROVED / _DENIED | `pending_change` workflow: users create/enable/disable, roles, jurisdictions, assignments, thresholds | CHANGE | `kind`, `subject_id`, `change_hash`, `old_value`, `new_value` (ids, roles, settings only) |
| ASSIGNMENT_CHANGED | An approved assignment change takes effect | USER | `case_id`, `added` (bool) |
| USER_CREATED / _ENABLED / _DISABLED | An approved account change takes effect | USER | `role`, `district_id` |
| AUDIT_VIEWED | An audit page is about to be returned | AUDIT | `filter_keys`, `seq_from^`, `seq_to^`, `result_count`, `redacted` (bool) |
| AUDIT_VERIFY_RUN | Verification run | AUDIT | `range_from^`, `range_to^`, `result`, `first_bad_seq^`, `head_seq^`, `anchor_seq^` |

Write rules:
| # | Rule |
|---|---|
| W1 | Reads and actions are audited before data leaves the API. If the append fails, the request fails (500) with no data. Fail closed. |
| W2 | Successful state changes: audit row and change commit or roll back together. |
| W3 | ACCESS_DENIED and AUTH_* rows are appended in their own transaction after the business transaction has ended, so they persist though the action rolled back. A request never opens a W3 append while holding the append lock. An R2_NOT_VISIBLE denial is stored identically whether the id exists or not: `target_type` UNRESOLVED, `target_id` the string supplied (section 6), `refs` empty. The resolved target is kept in a private column (`resolved_target`, class P) for forensics through the database only. |
| W4 | `reason_code` is set on every ACCESS_DENIED and on view events with `via_grant` true. |
| W5 | One function, `audit.append`, writes; no code path updates or deletes. |
| W6 | Every route declares its audit event; the route-inventory test fails a route that has none. |
| W8 | Keys marked `^` are stored for forensics and never returned by any endpoint, and `GET /audit` serializes `detail` through a per-event allow-list (additional keys forbidden). A test scans every `GET /audit` response for `seq`, `*_seq` and `range_*` keys. The only sequence number the API ever returns is `first_bad_seq` in a BROKEN result of `POST /audit/verify`, to a SENIOR. |
| W7 | `refs` must list every case a row's ids or fields reveal, including ids inside `detail`. A write whose `refs` do not cover its case-bearing keys is rejected. |

## 4. Hash chain, verification, anchor
`row_hash = SHA-256( prev_hash || canonical(all columns except row_hash) )`, including `row_nonce`. `canonical`: JSON, sorted keys, no whitespace, UTF-8, timestamps UTC ISO-8601 with microseconds and `Z`, uuids lowercase, bytea lowercase hex, nulls kept. `seq` 1 has `prev_hash` of 32 zero bytes. The nonce means a hidden field cannot be confirmed by hashing a guess.

Append (last step before commit, W2): take `pg_advisory_xact_lock`, read the last row, set `seq` and `prev_hash`, compute `row_hash`, insert, commit. The lock is held only for those steps. `seq` has no gaps.

Verification (`audit.verify`, server-side; `POST /audit/verify`, SENIOR or system only) returns `OK`, or `BROKEN` plus `first_bad_seq`, and nothing else: no rows, no hashes, no head position. This is the one place a sequence number leaves the API (D38, as amended).
| Step | Check |
|---|---|
| 1 | Rows contiguous; first `prev_hash` matches the preceding row (zeros for 1) |
| 2 | Each `prev_hash` equals the previous `row_hash` |
| 3 | Each `row_hash` equals the recomputed hash |
| 4 | Against the latest anchor: chain must reach `anchor.seq` and the row there must hash to `anchor.row_hash` |

Anchor: the API appends `{seq, row_hash, at}` as one line to an append-only file outside the database (`AUDIT_ANCHOR_PATH`, opened O_APPEND, never rewritten) every 60 seconds, on every verify and on shutdown. The anchor is written by a separate OS user or sidecar process (or the file is set append-only with `chattr +a`); the API's own OS user and the database credentials cannot truncate it. Startup verifies the last 1000 rows plus step 4; failure blocks readiness. Full verify runs nightly and on demand. A manual copy of the head goes in the runbook as well. Residual risk: someone with both database owner rights and the anchor file can still rewrite history.

## 5. Append-only enforcement
| Layer | Control |
|---|---|
| Trigger | `BEFORE UPDATE OR DELETE` row trigger and `BEFORE TRUNCATE` statement trigger raise an exception |
| Roles | A separate owner role (`tracex_migrator`) owns the table and triggers and runs migrations only. The API connects as `tracex_api`: `INSERT` and `SELECT` on `audit_log` only; not the owner, not a superuser, not a member of the owner role; no `ALTER`, `TRIGGER`, `GRANT` |
| Code | No SQL in `tracex_api` updates or deletes audit rows (grep test) |
| Honest limit | A superuser could drop the triggers. Not prevented; detected by verification and the anchor |

## 6. Deliberately not stored
| Not stored | Instead |
|---|---|
| Passwords, hashes, tokens, signing keys, secrets | `sid`, `request_id` (private columns) |
| Personal values: names, phones, accounts, vehicle numbers, addresses, any entity value | Entity, link, case ids |
| Source line text, explanation text, signals, evidence | `line_from`, `line_to`, document id |
| Search terms | `entity_ids` returned, type filter |
| Free text: link decision reasons, access-request reasons | Their own access-controlled tables; the log holds ids |
| Request or response bodies, file contents, stack traces, database errors | `file_sha256`, `http_status`, codes |
| Raw attacker or reader strings | `claimed_username` holds the raw string only if it equals an existing username; `claimed_sub` and an UNRESOLVED `target_id` only if they are a well-formed uuid; otherwise `hmac:<16 hex>` of a keyed hash (key from environment). `filter_keys` lists filter names only, never values |

## 7. Who can read the log, and how reading is logged
JUNIOR and INVESTIGATOR: 403, ACCESS_DENIED. SUPERVISOR, SENIOR and ADMIN read under one **row-level rule**. A row exists for the reader only if:
| | Condition |
|---|---|
| (a) | the reader is the actor; or |
| (b) | the actor is in the reader's chain of command (SUPERVISOR or SENIOR: actor district inside their scope or coverage), including the actor's denied probes; or |
| (c) | `refs` is non-empty and the reader has ALLOW on **every** case in `refs`; or |
| (d) | `refs` is empty and the row is a system event (AUTH_*, DATA_UPLOADED, MATCHING_RUN_*, CHANGE_*, USER_*, AUDIT_*) and the reader is ADMIN, or a SENIOR for whom every user and district the row names (target, `subject_id`, `old_value`, `new_value`; an actor with no jurisdiction, such as ADMIN or SYSTEM, does not count) lies inside the SENIOR's coverage. An all-state SENIOR sees every such row. Rule (d) never admits a row that references a case. |

Any other row does not exist for that reader: no placeholder, no gap, no count, no paging effect. There are no partial views of other people's actions. For a row shown under (a) or (b) that references a case the reader cannot see, the hidden `refs` entries, every S field of those cases and every J field are **dropped from the response** (keys absent, not null). Rows shown under (c) or (d) are complete. The API never returns P columns, hashes, nonces or `seq`.

Example: charu (SUPERVISOR, Rivergate). L-3 joins C-101 (Rivergate) to C-301 (Lakeside). The rows LINK_AUTO_CREATED (engine), LINK_VIEWED (gita), LINK_CONFIRMED (meena) and ACCESS_REQUEST_CREATED (gita) do not exist for her: she lacks ALLOW on C-301 and none of the actors is hers. She learns nothing of the far officers, the far district, or the link's state or timing. She does see bharat's own STUB_VIEWED row for E-4 with `refs` [C-101] and no `stub_ids`, because bharat is in her chain of command.

**Filters, sorting and paging** run only over the rows and fields the reader can see, after the rule above. A filter on a value the reader cannot see (a hidden case id, a guessed link id, an officer outside their scope) returns exactly what a filter on a non-existent value returns: same empty page, same `result_count`, same cursor. Sort keys are visible fields only.

Pagination uses an opaque cursor; no export. The cursor is **encrypted** (authenticated encryption, server key), bound to the reader and the filters, and expires after 15 minutes; it carries the visible sort key and the `row_ref` as position, never `seq` or an id. A cursor of another reader, other filters, an expired or altered one is a 422 like a malformed one. Every page returned writes AUDIT_VIEWED first (W1) with filter names, `result_count` and whether any field was dropped, and is not part of the page it logs.

## 8. Acceptance cases
Users and seed as in `api-access-control.md` section 7. "Tamper" tests use a superuser connection in the test database only.

| # | Setup / attempt | Expected |
|---|---|---|
| U1 | API role runs `UPDATE audit_log ...` | Permission denied; no change |
| U2 | Superuser (trigger enabled) runs `UPDATE` | Trigger exception |
| U3 | Same for `DELETE` | Exception; row count unchanged |
| U4 | Same for `TRUNCATE` | Exception; row count unchanged |
| U5 | API role runs `ALTER TABLE audit_log DISABLE TRIGGER ALL`, `DROP TRIGGER`, `GRANT`, `ALTER TABLE ... OWNER` | Each fails; API role is not owner or superuser or member of the owner role (catalog check) |
| U6 | Grep `backend/tracex_api/` | No UPDATE, DELETE, TRUNCATE on `audit_log` |
| U7 | Append three events | `seq` contiguous; each `prev_hash` equals the previous `row_hash` |
| U8 | Fixed row, nonce and `prev_hash` | `row_hash` equals the test vector |
| U9 | 50 concurrent appends mixing W2 (in transactions) and W3 (denials) | No deadlock, `seq` contiguous, verify `OK` |
| U10 | Clean chain, `POST /audit/verify` by meena | `OK`; body has no rows, no hashes; AUDIT_VERIFY_RUN written |
| U11 | Trigger disabled, edit row 5, verify | `BROKEN`, `first_bad_seq` 5 |
| U12 | Trigger disabled, delete row 5; swap rows 5 and 6 | `BROKEN` each |
| U13 | Delete the last 10 rows (trigger disabled); verify | `BROKEN` (shorter than anchor) |
| U14 | Edit row 5 and recompute every later hash; verify | `BROKEN` (hash at `anchor.seq` differs) |
| U15 | Anchor file written every interval, on verify and on shutdown | Entries present; API cannot truncate it (opened O_APPEND) |
| U16 | Startup with a broken chain in the last 1000 rows | Not ready |
| U17 | bharat views E-1 | ENTITY_VIEWED: actor, role, district, E-1, `refs` [C-101], `via_grant` false |
| U18 | Entity detail with stubs for L-1 and L-3 | STUB_VIEWED with both `stub_ids`; `refs` lists C-101, C-201, C-301 |
| U19 | bharat GETs `/links/L-1` | 404; ACCESS_DENIED: `target_type` UNRESOLVED, `target_id` the string, empty `refs`, `reason_code` R2_NOT_VISIBLE; `resolved_target` L-1 (private) |
| U20 | Random uuid | 404; row identical in shape to U19; `resolved_target` null |
| U21 | A phone number put in an id path; a lowercase password typed as username; an existing username with a wrong password | `hmac:...` for the first two, raw string absent; the existing username is stored raw |
| U22 | asha confirms L-2 | 403; ACCESS_DENIED `http_status` 403 |
| U23 | Denied action inside a rolled-back transaction | ACCESS_DENIED row persists (W3) |
| U24 | Wrong password; 6th attempt throttled | AUTH_LOGIN_FAILED (`throttled` true on the 6th); no password in any column |
| U25 | Tampered token; reused refresh token | AUTH_TOKEN_REJECTED; AUTH_REFRESH_REUSED |
| U26 | Matching run: one AUTO, one SUGGESTED; later threshold change demotes the AUTO | LINK_AUTO_CREATED, LINK_SUGGESTED, LINK_DEMOTED, SYSTEM actor, `run_id`, written by the API from engine transition records |
| U27 | bharat confirms L-2; charu undoes, reopens | LINK_CONFIRMED (previous AUTO), LINK_UNDONE, LINK_REOPENED; reasons absent from the log |
| U28 | Request, approve, read under grant, revoke | One event per step; reads have `via_grant` true and `reason_code` GRANT_ACTIVE |
| U29 | Entity search; graph view; review queue | SEARCH_RUN with `entity_ids`; GRAPH_VIEWED; REVIEW_QUEUE_VIEWED with ids shown |
| U30 | hari proposes a change; deepak approves | CHANGE_PROPOSED then CHANGE_APPROVED with equal `change_hash`; then ASSIGNMENT_CHANGED or USER_* when applied |
| U31 | Force `audit.append` to fail during a view | 500; no case data |
| U32 | `detail` key not in section 3; `refs` missing a case named in `detail` | Insert rejected (W7) |
| U33 | After the seeded scenario, scan all columns | No seeded phone number, name or line text |
| U34 | Client sends `occurred_at`, `actor_user_id` in a body | Ignored |
| U35 | Seeded L-3 activity: engine creates L-3, gita views, meena confirms, gita requests access. charu reads audit | None of these rows appear; page, `result_count` and cursor equal those of a database that never had them; no gita, meena, Lakeside or L-3 state or time anywhere in the response |
| U36 | deepak reads the same | Same: C-301 is outside his coverage, so none of the rows exist for him; his own actions (a) appear |
| U37 | charu reads bharat's denied probes of L-1 and of a random uuid | Both shown under (b), identical shape: ACCESS_DENIED, `reason_code` R2_NOT_VISIBLE, `target_id` the string supplied, empty `refs` |
| U38 | farid reads audit after U37 and after bharat's access request for L-1 | Neither the probe nor the request row appears (bharat is not his; `refs` include C-101). His own ACCESS_REQUEST_APPROVED appears under (a) with the C-101 entry and `grant_id` dropped |
| U39 | deepak reads LINK_AUTO_CREATED for L-1 (C-101 and C-201, both in coverage) | Shown in full under (c) |
| U40 | charu reads bharat's STUB_VIEWED for E-1 | Shown under (b); `refs` contains only C-101; `stub_ids` key absent (not null) |
| U41 | charu filters by `case_id` C-301, by C-999, by actor gita, by a non-existent user, by L-3's id; sorts by each visible field | All results identical to the non-existent value: same empty page, count and cursor |
| U42 | hari reads audit | System events and hari's own rows only; no case-bound rows, no hashes |
| U43 | asha reads audit | 403; ACCESS_DENIED |
| U44 | Read a page, then the next | Second page includes the first page's AUDIT_VIEWED; no `seq` in any response; two readers get different `row_ref` for the same row |
| U45 | meena verifies; charu verifies | OK; 403 |
| U46 | Link-list response | LINKS_LISTED with `link_ids` and `stub_ids`; route inventory fails a route without an event |
| U47 | Read pages of AUDIT_VIEWED and AUDIT_VERIFY_RUN rows as the actor and as ADMIN | No `seq`, `*_seq`, `range_*` key in any response; `detail` has only allow-listed keys |
| U48 | hari proposes a role change for gita; gita logs in; deepak reads audit | Neither the CHANGE_PROPOSED row nor gita's AUTH rows exist for deepak (outside coverage); meena sees both |
| U49 | Decode a cursor | It does not decode to a `seq` or an id; another reader's, expired or altered cursor gives 422 |
| U50 | Engine promotes and withdraws links in a rerun; a decision is recorded | LINK_PROMOTED and LINK_WITHDRAWN rows written from the transition records; LINK_CONFIRMED committed with the decision, before the engine call |
| U51 | Read grants, pending changes and access requests | GRANT_VIEWED, CHANGE_VIEWED, ACCESS_REQUEST_VIEWED with the ids shown |
| U52 | hari uploads to C-101 | DATA_UPLOADED has `refs` [C-101]; charu sees it under (c) |

## 8.1 Keys
The JWT signing key, the cursor key, the `row_ref` key and the `hmac:` key are four distinct secrets from the environment; none is derived from another.

## 9. Out of scope
Export, retention or purge (rows live as long as the database), streaming to external systems, external signing keys.
