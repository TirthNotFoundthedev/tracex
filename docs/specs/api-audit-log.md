# Spec: API audit log

Owner: Khan (Backend Lead). Status: DRAFT for Security Reviewer. Task P1.3. Encoded as table-driven tests in `backend/tests/`. Companion: `api-access-control.md`.

## 1. Purpose
Show who knew what, and when. Every significant action and every access decision (allowed, redacted, denied) is recorded. The log is append-only and tamper-evident: a Postgres table where UPDATE, DELETE and TRUNCATE are blocked, and each row is hash-chained to the previous one. It stores ids and facts, never personal values.

## 2. Row schema: table `audit_log`
| Column | Type | Meaning |
|---|---|---|
| `seq` | bigint, primary key | Contiguous from 1, assigned inside the write lock as previous `seq` + 1 |
| `event_id` | uuid, unique | Random |
| `occurred_at` | timestamptz | Database clock at insert (UTC). Client-supplied times are ignored |
| `event_type` | text | One of section 3 (CHECK constraint on the list) |
| `outcome` | text | `SUCCESS`, `DENIED` or `FAILED` |
| `actor_kind` | text | `USER`, `SYSTEM` or `ANONYMOUS` |
| `actor_user_id` | uuid, null | Authenticated user; null for SYSTEM and ANONYMOUS |
| `actor_role`, `actor_district_id` | text, null | Snapshot at the time of the event |
| `session_id`, `request_id` | uuid, null | `sid` claim; per-request id |
| `client_ip` | inet, null | Caller address as seen by the API |
| `target_type` | text, null | `CASE`, `ENTITY`, `LINK`, `STUB`, `DOCUMENT`, `USER`, `ACCESS_REQUEST`, `GRANT`, `BATCH`, `RUN`, `SETTING`, `AUDIT`, `UNRESOLVED` |
| `target_id` | text, null | Id of the target, or for UNRESOLVED the raw id string supplied, cut to 64 chars |
| `case_id`, `district_id` | text, null | Case and district the target belongs to, denormalised so audit reads can be scoped by jurisdiction |
| `reason_code` | text, null | Policy rule that decided (for example `R2_NOT_VISIBLE`, `MATRIX_DENY`, `GRANT_ACTIVE`) |
| `detail` | jsonb | Only the keys listed for the event in section 3; unknown keys rejected |
| `prev_hash` | bytea(32) | `row_hash` of `seq - 1`; 32 zero bytes for `seq` 1 |
| `row_hash` | bytea(32) | See section 4 |

## 3. Events
"Written" says when; the row is committed in the same transaction as the action unless noted. `detail` keys are the only keys allowed.

| Event | Written when | Actor | Target | `detail` keys |
|---|---|---|---|---|
| AUDIT_CHAIN_STARTED | Once, by migration | SYSTEM | none | `schema_version` |
| AUTH_LOGIN_SUCCESS | Login accepted | USER | USER | none |
| AUTH_LOGIN_FAILED | Login rejected (bad user or password, disabled) | ANONYMOUS | none | `claimed_username` (untrusted, cut to 64) |
| AUTH_TOKEN_REJECTED | Token missing, malformed, expired, bad signature, stale `ver` | ANONYMOUS | none | `failure` (code), `claimed_sub` (untrusted) |
| AUTH_LOGOUT / AUTH_REFRESHED | Logout / refresh token rotated | USER | USER | none |
| CASE_LISTED | Case list returned | USER | none | `result_count` |
| CASE_ENTITIES_VIEWED | Case entity list returned | USER | CASE | `entity_ids` (max 500) |
| ENTITY_VIEWED | Entity detail returned | USER | ENTITY | `link_ids_shown`, `stub_shown` (bool) |
| LINK_VIEWED | Link returned, or a stub shown for it | USER | LINK | `view_mode` (`FULL`, `REDACTED`) |
| EXPLANATION_VIEWED | Explanation returned | USER | LINK | none |
| SOURCE_LINES_VIEWED | Source lines returned | USER | DOCUMENT | `line_from`, `line_to` |
| SEARCH_RUN | Search executed | USER | none | `result_count`, `entity_type_filter` |
| ACCESS_DENIED | Any request refused by policy, including 404 for hidden ids and 403 for role | USER or ANONYMOUS | as attempted | `action`, `http_status` |
| LINK_AUTO_CREATED | Matching creates a high-band link | SYSTEM | LINK | `run_id`, `band`, `score`, `entity_ids` (2) |
| LINK_SUGGESTED | Matching creates a medium-band link | SYSTEM | LINK | same as above |
| LINK_CONFIRMED / LINK_REJECTED / LINK_UNDONE | Officer decides | USER | LINK | `previous_state`, `new_state` |
| ACCESS_REQUEST_CREATED / _WITHDRAWN / _EXPIRED | Request lifecycle | USER or SYSTEM | ACCESS_REQUEST | `stub_id`, `far_case_count` |
| ACCESS_REQUEST_APPROVED / _REJECTED | Approver decides | USER | ACCESS_REQUEST | `grant_id`, `expires_at` (approve only) |
| ACCESS_GRANT_REVOKED / _EXPIRED | Revocation, auto-revocation, expiry first seen | USER or SYSTEM | GRANT | `cause` (`MANUAL`, `ROLE_CHANGE`, `LINK_CLOSED`, `TIME`) |
| DATA_UPLOADED | Upload accepted | USER | BATCH | `file_sha256`, `byte_count`, `document_count` |
| MATCHING_RUN_STARTED / _COMPLETED | Matching begins / ends | USER | RUN | `thresholds_version`; completed adds `auto_count`, `suggested_count` (system-wide) |
| USER_CREATED / USER_DISABLED | Account lifecycle | USER | USER | `role`, `district_id` |
| CHANGE_PROPOSED / _APPROVED / _DENIED | `pending_change` workflow (thresholds, roles, jurisdictions, SUPERVISOR/SENIOR creation) | USER | SETTING or USER | `kind`, `old_value`, `new_value` (settings and role/district ids only) |
| AUDIT_VIEWED | An audit page is about to be returned | USER | AUDIT | `filters`, `seq_from`, `seq_to`, `result_count`, `redacted` (bool) |
| AUDIT_VERIFY_RUN | Verification run | USER or SYSTEM | AUDIT | `range_from`, `range_to`, `result` (`OK`, `BROKEN`), `first_bad_seq`, `head_seq`, `head_hash` |

Write rules:
| # | Rule |
|---|---|
| W1 | Reads and actions are logged before data leaves the API. If the audit insert fails the request fails (500) and returns no data. Fail closed. |
| W2 | Successful state changes: audit row and change commit or roll back together. |
| W3 | ACCESS_DENIED and AUTH_* rows are written in their own transaction, so they persist though the action rolled back. A denied attempt on an existing hidden target records its real `target_id`; on an id that does not exist, `UNRESOLVED` with the supplied string. |
| W4 | `reason_code` is always set on ACCESS_DENIED and on `REDACTED` LINK_VIEWED. |
| W5 | Writes go through one function (`audit.append`). No other code path inserts, and none updates or deletes. |

## 4. Hash chain
`row_hash = SHA-256( prev_hash || canonical(row without row_hash) )`.
`canonical` is JSON with keys sorted, no whitespace, UTF-8; timestamps as UTC ISO-8601 with microseconds and `Z`; uuids lowercase; bytea as lowercase hex; nulls kept as `null`.

Append (inside one transaction): take `pg_advisory_xact_lock(<audit key>)`; read the last row; set `seq`, `prev_hash`; compute `row_hash`; insert. Appends are serialised, so `seq` has no gaps and rollbacks leave none.

Verification (`audit.verify(from_seq, to_seq)`):
| Step | Check |
|---|---|
| 1 | Rows in range are contiguous in `seq`; first row's `prev_hash` equals the `row_hash` of `from_seq - 1` (zeros if 1) |
| 2 | Each `prev_hash` equals the previous row's stored `row_hash` |
| 3 | Each `row_hash` equals the recomputed hash |
| Result | `OK` with `head_seq`, `head_hash`, or `BROKEN` with `first_bad_seq` and the failed check |

When run: last 1000 rows at API startup (failure blocks readiness); full chain nightly and on demand (`POST /audit/verify`, itself logged). Detects edited, deleted, inserted or reordered rows. Truncation of the tail is detected only by comparing `head_seq` and `head_hash` with a copy kept outside the database (runbook: record after each demo run).

## 5. Append-only enforcement
| Layer | Control |
|---|---|
| Trigger | `BEFORE UPDATE OR DELETE` row trigger and `BEFORE TRUNCATE` statement trigger on `audit_log` raise an exception |
| Privileges | The API's database role has `INSERT` and `SELECT` only on `audit_log`; `UPDATE`, `DELETE`, `TRUNCATE` revoked |
| Code | No ORM model method or SQL in `tracex_api` updates or deletes audit rows (checked by a grep test) |
| Honest limit | A database superuser could drop the triggers. This is not prevented but is detected by verification and the external head copy |

## 6. Deliberately not stored
| Not stored | Instead |
|---|---|
| Passwords, hashes, tokens (access, refresh), signing keys, secrets | `sid`, `request_id` only |
| Personal values: names, phone numbers, accounts, vehicle numbers, addresses, any entity value | Entity, link and case ids |
| Source line text, explanation text, signals and evidence | `line_from`, `line_to`, document id |
| Search terms | `result_count`, entity type filter |
| Free text: link decision notes, access request reasons | Kept in their own tables (access-controlled); the log holds the ids |
| Request or response bodies, uploaded file contents, stack traces, database error text | `file_sha256`, `http_status`, codes |
| Far-side details for REDACTED and denied events beyond the real target id | Audit readers see them only through the scoping in section 7 |

## 7. Who can read the log, and how reading is logged
| Role | Reads |
|---|---|
| JUNIOR, INVESTIGATOR | No: 403, ACCESS_DENIED |
| SUPERVISOR | Rows whose `district_id` is their district |
| SENIOR | Rows in their state in full; rows in other states: REDACTED (seq, time, event type, outcome, actor id) |
| ADMIN | System events (no `case_id`) in full; case-bound rows REDACTED as above |

Scoping is in the query, not after it. Hash columns are returned to every reader of a row. Redacted rows keep their `seq`, so gaps never appear in a contiguous range.
Every page returned writes AUDIT_VIEWED first (W1), with the filters, the `seq` range and count returned, and whether redaction was applied. The row is not part of the page it logs; it appears in the next read. Pagination is by `seq`; no export in the MVP. `POST /audit/verify` is allowed for ADMIN and SENIOR and returns no row content.

## 8. Acceptance cases
Users and seed data as in `api-access-control.md` section 7. "Tamper" tests use a superuser connection in the test database only.

| # | Setup / attempt | Expected |
|---|---|---|
| U1 | API role runs `UPDATE audit_log SET outcome='SUCCESS'` | Fails with permission denied; no row changes |
| U2 | Superuser (trigger enabled) runs `UPDATE` on any row | Trigger exception; no row changes |
| U3 | Same for `DELETE` | Exception; row count unchanged |
| U4 | Same for `TRUNCATE` | Exception; row count unchanged |
| U5 | Grep test over `backend/tracex_api/` | No UPDATE, DELETE or TRUNCATE on `audit_log` |
| U6 | Append three events | `seq` 1,2,3 (after genesis); each `prev_hash` equals the earlier `row_hash` |
| U7 | Fixed row and fixed `prev_hash` | `row_hash` equals the published test vector (guards canonical form) |
| U8 | 50 concurrent appends | `seq` contiguous, `verify` is `OK` |
| U9 | Clean chain, run verify | `OK`, returns `head_seq` and `head_hash` |
| U10 | Trigger disabled, edit `detail` of row 5, re-enable, verify | `BROKEN`, `first_bad_seq` 5 |
| U11 | Trigger disabled, delete row 5, verify | `BROKEN`, gap at 5 |
| U12 | Trigger disabled, swap rows 5 and 6 | `BROKEN` |
| U13 | Recompute chain after editing row 5 but compare with saved head | `head_hash` differs from the saved copy |
| U14 | bharat views entity E-1 | ENTITY_VIEWED: actor bharat, role, district, `target_id` E-1, `case_id` C-101, time set by database |
| U15 | bharat's entity detail shows L-1 as a stub | LINK_VIEWED with `view_mode: REDACTED`, `reason_code` set |
| U16 | bharat requests `GET /links/L-1` by id | Response 404; ACCESS_DENIED with `target_id` L-1, `case_id` C-201, `reason_code` R2_NOT_VISIBLE |
| U17 | Request for a random UUID | Response 404; ACCESS_DENIED, `target_type` UNRESOLVED, `target_id` the supplied string |
| U18 | asha confirms L-2 | 403; ACCESS_DENIED `http_status` 403; link state unchanged |
| U19 | Denied confirm inside a transaction that rolls back the action | ACCESS_DENIED row still exists (W3) |
| U20 | Login with wrong password | AUTH_LOGIN_FAILED; no password in any column; `claimed_username` present |
| U21 | Token with tampered claims | AUTH_TOKEN_REJECTED, `claimed_sub` marked untrusted; actor null |
| U22 | Matching run creates one AUTO and one SUGGESTED link | LINK_AUTO_CREATED and LINK_SUGGESTED, SYSTEM actor, `run_id`, `band`, `score` |
| U23 | bharat confirms L-2, charu undoes it | LINK_CONFIRMED (`previous_state` AUTO), LINK_UNDONE (`previous_state` CONFIRMED), actors correct |
| U24 | Full access-request flow (create, approve, expire, revoke) | One event per step with `grant_id` and `cause` |
| U25 | Force `audit.append` to fail during a view | 500; response contains no case data (W1) |
| U26 | `detail` has a key not in section 3 | Insert rejected; test fails loudly |
| U27 | After the seeded scenario, scan every `detail` and text column | No seeded phone number, name or source line text found |
| U28 | Client sends `occurred_at` or `actor_user_id` in a request body | Ignored; values come from database clock and token |
| U29 | farid reads audit | Only rows with `district_id` Hillcrest; AUDIT_VIEWED written with range and count |
| U30 | deepak reads rows from Eastmark | REDACTED fields only; `case_id`, `target_id`, `detail` null |
| U31 | hari reads audit | System events full; case-bound rows REDACTED |
| U32 | asha reads audit | 403; ACCESS_DENIED logged |
| U33 | Read a page, then read the next | Second page contains the first page's AUDIT_VIEWED; the first page did not |
| U34 | `POST /audit/verify` by hari | AUDIT_VERIFY_RUN with result and head |
| U35 | Startup with a broken chain in the last 1000 rows | API not ready; AUDIT_VERIFY_RUN `BROKEN` recorded if the append is possible |

## 9. Out of scope
Log export, retention or purge (rows are kept for the life of the database), streaming to external systems, signing with external keys.

## Open questions for Fable
1. Entity lists log up to 500 entity ids per view, so "who viewed which entity" is exact. Recommend: yes.
2. Store `client_ip`. Recommend: yes (synthetic users, useful for forensics).
3. ADMIN reads system events only; case-bound rows REDACTED. Recommend: yes (separation of duties).
