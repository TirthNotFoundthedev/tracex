# Spec: API access control

Owner: Khan (Backend Lead). Status: DRAFT, revised after Security Reviewer findings. Task P1.3. Encoded as table-driven tests in `backend/tests/`. Companion: `api-audit-log.md`.

## 1. Purpose and principles
The API decides who sees what on two dimensions: **seniority** (role) and **jurisdiction** (district within state). A link into a case the caller may not see reveals that a connection exists and nothing else. Every decision, allow or deny, is audited. Rules live in the API; the UI may hide things but is never the control. Deny by default. The matching engine creates AUTO links regardless of jurisdiction; that is a system action and never waits for a human. Access control governs what an officer sees of such a link and who may make human decisions on it.

## 2. Model
### 2.1 Roles (canonical names, defined once here; other specs, tests and the UI wording map cite these. Ranks are illustration only)
| Role | Illustrative ranks | Scope | Purpose |
|---|---|---|---|
| JUNIOR | Constable, Head Constable | one district | View cases, entities, links, explanations |
| INVESTIGATOR | Sub-Inspector, Inspector | one district | Above, plus confirm / reject links, source lines |
| SUPERVISOR | DSP, SP | one district | Above, plus undo, reopen, approve access requests |
| SENIOR | DIG, IG | a **coverage set** of districts and states (seeded; one SENIOR covers all states: "central desk") | Above across the coverage; approves pending changes |
| ADMIN | Technical staff | none | Runs the system; no case-data rights |

### 2.2 Jurisdiction
State contains districts. Every case belongs to one district. A user has one role and one jurisdiction (SENIOR: a coverage set; ADMIN: none).

### 2.3 Relation of a user to a case (read from the database on every request, never from the token)
| Relation | Definition |
|---|---|
| own case | User is active and in `case_assignments` for the case |
| own jurisdiction | Case district is inside the user's scope or coverage, not assigned |
| other jurisdiction | Everything else. ADMIN has no scope, so every case is "other" |

### 2.4 Rules
| # | Rule |
|---|---|
| R1 | Deny by default. Every route declares a policy and its audit event; a route lacking either fails startup and the route-inventory test. |
| R2 | One order everywhere: authenticate (401) -> can the caller see that the thing exists? If not, **404**, never 403 -> role permits? (403) -> state valid? (409) -> input valid (422). "Exists" means ALLOW on the resource: a REDACTED link, a hidden case, another user's access request, grant or pending change all give 404 by id. The 404 body is identical for unknown and hidden ids. Applies to cases, entities, links, stubs, requests, grants, changes and users. |
| R3 | Actions touching several cases (a link has two ends) evaluate every end; the worst outcome wins (DENY > REDACTED > ALLOW). |
| R4 | Role, jurisdiction, assignments, active flag come from the database, never from claims. |
| R5 | Redaction is applied in the query or service layer before serialization. No endpoint returns case data without the policy function. |
| R6 | A grant (section 5) adds ALLOW on exactly what it names, capped by what the holder's role may see in their own jurisdiction. It is not a role change and never widens any other cell. |

## 3. Permission matrix
Cell = `own case / own jurisdiction / other jurisdiction`. A = ALLOW, R = REDACTED, D = DENY. For links, the relation is that of each end (R3).

| Action (resource) | JUNIOR | INVESTIGATOR | SUPERVISOR | SENIOR | ADMIN |
|---|---|---|---|---|---|
| List cases | A/A/D | A/A/D | A/A/D | A/A/D | D/D/D |
| View case entities | A/A/D | A/A/D | A/A/D | A/A/D | D/D/D |
| View a link | A/A/R | A/A/R | A/A/R | A/A/R | D/D/D |
| View explanation | A/A/R | A/A/R | A/A/R | A/A/R | D/D/D |
| View source lines | A/D/D | A/A/D | A/A/D | A/A/D | D/D/D |
| Confirm / reject a link | D/D/D | A/A/D | A/A/D | A/A/D | D/D/D |
| Undo a link decision | D/D/D | D/D/D | A/A/D | A/A/D | D/D/D |
| Reopen a REJECTED / UNDONE link | D/D/D | D/D/D | A/A/D | A/A/D | D/D/D |
| Request access (via a stub) | D/A/A | D/A/A | D/A/A | D/A/A | D/D/D |
| Approve / deny access request (far case relation) | D/D/D | D/D/D | A/A/D | A/A/D | D/D/D |
| Revoke a grant (far case relation) | D/D/D | D/D/D | A/A/D | A/A/D | D/D/D |
| Upload data | D/D/D | D/D/D | D/D/D | D/D/D | A/A/A |
| Run matching | D/D/D | D/D/D | D/D/D | D/D/D | A/A/A |
| Propose a change (users, assignments, thresholds) | D/D/D | D/D/D | D/D/D | D/D/D | A/A/A |
| Approve / deny a pending change | D/D/D | D/D/D | D/D/D | A/A/D (subject in coverage) | D/D/D |
| View audit log (rows by case relation) | D/D/D | D/D/D | A/A/D | A/A/D | R/R/R |
| Verify audit chain | D/D/D | D/D/D | D/D/D | A/A/A | D/D/D |

Notes: "Request access" on an own case is DENY (nothing to request). System-wide rows have equal columns. ADMIN audit: system events (no case reference) in full, case-bound rows redacted (audit spec section 7). Rejected and undone links are not connections: no stub.

### 3.1 Link states: who may change them
| From -> To | Role (both end cases must be ALLOW for the caller by their own scope, R3) | Reason |
|---|---|---|
| SUGGESTED -> CONFIRMED, AUTO -> CONFIRMED | INVESTIGATOR+ | no |
| SUGGESTED -> REJECTED | INVESTIGATOR+ | yes |
| AUTO or CONFIRMED -> UNDONE | SUPERVISOR+ | yes |
| REJECTED or UNDONE -> SUGGESTED (reopen) | SUPERVISOR+ | yes |
An AUTO link can be undone but not rejected (409). A link whose ends are in different districts or states is decided only by a SENIOR whose coverage includes both ends; a grant never qualifies. Reasons live in the link history, not the audit log. Engine transitions (create, demote) come as transition records; the API audits them.

### 3.2 Pending changes (four-eyes; "major changes require senior approval")
The MVP has seeded users and no password feature: no route sets or resets credentials. Every ADMIN change to users (create, enable, disable), roles, jurisdictions, case assignments and thresholds is one generic `pending_change` (kind, subject, old value, new value, proposer, `change_hash` = SHA-256 of the canonical content, state PENDING / APPROVED / DENIED, decider). It applies only on approval.
| Rule | |
|---|---|
| Approver | SENIOR whose coverage includes the subject's jurisdiction (old and new, for a move); for thresholds, a SENIOR with all-state coverage. Not the proposer, not the subject. A caller outside the subject's coverage gets 404. |
| Binding | Approval presents the `change_hash`. A changed proposal is a new record needing new approval. If the current value no longer equals `old_value`, approval fails (409). |
| Last approver | Disabling or moving the last SENIOR able to approve a jurisdiction is refused (409). |

## 4. What a REDACTED link shows
Stubs are embedded where a link would appear (entity detail, link list, graph neighbours) and returned by `GET /stubs/{stub_id}`. **Never** from a link-id route and **never** in the review queue (the queue lists ALLOW items only). One stub per hidden link, with the same shape whatever the link state (AUTO, SUGGESTED, CONFIRMED).

| Field | Value |
|---|---|
| `redacted` | `true` |
| `stub_id` | Random opaque id bound to (caller, link); not derived from link, entity or case ids; usable only to request access |
| `near_entity_id` | The caller's own side entity |
| `connection_exists` | `true` |
| `access_request` | `{status: NONE / PENDING / DENIED / EXPIRED, requested_at}`, the caller's own request for this stub |
| `message_key` | Fixed i18n key |

**Never appears, in any response, header or error:** far case id, number, title, district, state, officer; far entity id, type, name, value; link id, state, score, band, tier, signals, evidence count, creation time, run id.

| Channel | Rule |
|---|---|
| Counts | `link_count`, totals, pagination, graph degree, queue sizes count ALLOW items only. Stubs add only `has_hidden_connection`. The number of stub objects on an entity equals its hidden links; this is accepted (one request per link). |
| Ids | Hidden ids never echoed; unknown and hidden ids give the same 404 (R2). The test compares status, body and headers; no timing claim. |
| Errors | Fixed strings per code; none derived from hidden data. |
| Search | Matches ALLOW entities only; a value existing only in a hidden entity returns the same empty result as no match; no stubs. |
| Explanation | By link id: 404. `GET /stubs/{stub_id}`: the stub only. |
| Ordering | Stubs after visible items, ordered by `stub_id`. |
| Graph | A stub is an unlabelled leaf with no far-side edges. |
| Approver view | Approver sees requester, reason and a stub of the near side. |

## 5. Access-request lifecycle
| Item | Rule |
|---|---|
| Request | From one stub: one link, one far case. No fan-out, no aggregate. Reason 10 to 500 chars (no personal data). Requesters: JUNIOR, INVESTIGATOR, SUPERVISOR, SENIOR. Max 10 PENDING per user. |
| Approver | SUPERVISOR of the far case's district, or SENIOR whose coverage includes it. Never the requester, never ADMIN. Approver sees the requester's reason. |
| States | Request: PENDING -> APPROVED / DENIED / WITHDRAWN / EXPIRED (7 days). Grant: ACTIVE -> EXPIRED / REVOKED. Denied: re-request after 24 hours. |
| Duration | 7, 30 or 90 days (default 30); hard `expires_at`, checked every request; no renewal. |
| Grant scope | Read-only. The far entity of that one link, the link's explanation, and the **exact source-line ranges** cited by its evidence, fixed at approval. Capped by the holder's role in their own jurisdiction (a JUNIOR gets no source lines). Covers only the link existing at request time. |
| No pivot | The far entity under a grant shows only the granted link: no stubs, no counts, no other links; it cannot anchor a stub or request. Other entities of the far case stay hidden (404). |
| Closes when | Link REJECTED or UNDONE, evidence later cites a line outside the fixed ranges (cause EVIDENCE_CHANGED), holder's role, jurisdiction, assignment or active flag changes, expiry, or revocation by the approving authority (effective next request). |
| Status shown | One status per stub. Approval simply makes the link ALLOW. |

## 6. Session rules
| Item | Rule |
|---|---|
| Auth | JWT, key from environment, algorithm pinned (`none`/switching rejected). Seeded users only. |
| Lifetime | Access token 15 min; refresh 8 h absolute, rotated, single use. |
| Claims | `sub`, `sid`, `iat`, `exp`, `jti`, `ver`. Role and jurisdiction claims ignored. |
| Live session | Every request checks `sid` is live (database), so logout bites at once. Reuse of a rotated refresh token revokes the whole `sid` and is audited. |
| Change of role, jurisdiction, assignment, disable | Bump `authz_version`: old tokens 401, refresh tokens revoked, the user's grants closed. |
| Throttle | 5 failed logins per (username string, IP) in 15 minutes: 429 for 15 minutes, applied whether or not the username exists; audited. |
| Failures | Missing, malformed, expired, bad signature, stale `ver`, dead `sid`: 401, audited. |

## 7. Acceptance cases
Seed (synthetic): state Northvale (districts Rivergate, Hillcrest), state Eastmark (Lakeside). Cases: C-101, C-102 Rivergate; C-201 Hillcrest; C-301 Lakeside.
Users: asha JUNIOR Rivergate (C-101); isha JUNIOR Rivergate (no assignment); bharat INVESTIGATOR Rivergate (C-101, C-102); charu SUPERVISOR Rivergate; deepak SENIOR coverage Northvale; meena SENIOR coverage all states; esha INVESTIGATOR Hillcrest (C-201); farid SUPERVISOR Hillcrest; gita INVESTIGATOR Lakeside (C-301); hari ADMIN.
Entities: E-1 phone C-101; E-2 same phone C-201; E-3 C-102; E-4 vehicle C-101; E-5 C-301; E-7 C-201; E-8 C-201.
Links: L-1 E-1~E-2 AUTO; L-2 E-1~E-3 AUTO; L-3 E-4~E-5 CONFIRMED; L-4 E-1~E-7 REJECTED. L-5 E-1~E-8 AUTO is created after bharat's request in A22.

| # | Actor | Attempt | Expected |
|---|---|---|---|
| A1 | asha | List cases | C-101, C-102 only |
| A2 | asha | View L-2 | ALLOW |
| A3 | asha | Confirm L-2 | 403 |
| A4 | asha | Source lines of C-102 (case visible, cell D) | 403 |
| A5 | bharat | E-1 detail | One stub for L-1 and one for L-3, same shape (state not shown); no far fields |
| A6 | bharat | GET /links/L-1 by id | Same 404 as a random UUID; audited |
| A7 | bharat | GET /links/L-1/explanation; GET /stubs/{L-1 stub} | 404; stub only |
| A8 | bharat | E-1 `link_count` | Excludes L-1, L-3; `has_hidden_connection: true` |
| A9 | bharat | Search the phone value existing only in E-2 | Same empty result as an unknown number |
| A10 | bharat | Confirm L-2 | ALLOW; CONFIRMED |
| A11 | bharat | Undo L-2 | 403 |
| A12 | charu | Undo L-2 without, then with, a reason | 422; ALLOW, UNDONE; pair not auto-linked again |
| A13 | bharat | Reject L-2 while it is AUTO (before A10) | 409 invalid transition; AUTO can only be undone |
| A14 | charu / bharat | Reopen L-2 (UNDONE) | charu ALLOW to SUGGESTED; bharat 403 |
| A15 | charu | Confirm L-1 (end C-201 hidden) | 404 |
| A16 | deepak | Confirm L-1 (both ends in coverage) | ALLOW; CONFIRMED |
| A17 | deepak | View L-3 (Eastmark end); confirm or undo L-3 by id | Stub; 404 |
| A18 | meena | Undo L-3 (coverage includes both ends) | ALLOW; UNDONE |
| A19 | bharat | Request access on L-1's stub with reason | PENDING; stub shows PENDING |
| A20 | bharat | Request with a link, case or entity id instead of `stub_id`; other user's stub | 404 |
| A21 | bharat / charu | bharat approves own request; charu approves it | 403 (visible to bharat, requester); 404 (charu cannot see it) |
| A22 | farid | Approve bharat's request, 30 days; then L-5 is created | Grant ACTIVE on L-1 only; bharat still sees only a stub for L-5; farid saw a stub of bharat's near side |
| A23 | bharat | After A22: L-1, its explanation, cited source line ranges | ALLOW. Any other line range of the same document: 403 |
| A24 | bharat | After A22: open E-2 | Shows only L-1: no stubs, no counts; request access from E-2 or list C-201: 404 |
| A25 | isha (JUNIOR, own request approved) | Source lines of the cited ranges | 403 (role cap); explanation and E-2 ALLOW |
| A26 | bharat | After A22: confirm L-1 | 403 (visible, grant does not qualify) |
| A27 | bharat | After A22 and 31 days (clock injected) | Stub again; grant EXPIRED |
| A28 | farid | Revoke; bharat repeats A23 | Stub on the next request |
| A29 | system | Evidence of L-1 later cites a new line | Grant closed, EVIDENCE_CHANGED; stub again |
| A30 | bharat | Role or district changed (pending change approved); reuse old token | 401; grants closed |
| A31 | hari | List cases, view E-1, L-1, explanation | 404 for every case resource |
| A32 | hari | Approve a request; confirm a link; GET a grant or pending change not his | 404 (cannot see them) |
| A33 | hari | Upload; run matching | ALLOW; response has batch id and system-wide totals only |
| A34 | hari | Propose: create an INVESTIGATOR in Hillcrest; re-enable a disabled user; add bharat to C-201; raise a threshold; disable a user | Each is PENDING, nothing applies. No route exists to set or reset a password (404) |
| A35 | deepak / hari | deepak approves a change whose subject is deepak; deepak approves a change for a Lakeside user; hari approves any change | 403; 404 (outside coverage); 403 |
| A36 | deepak | Approve a threshold change | 404 (needs all-state coverage); meena approves, value changes |
| A37 | meena | Approve with a stale `change_hash`; approve after `old_value` changed | 409; new proposal needed |
| A38 | hari | Disable the only SENIOR covering Lakeside (approved) | 409 refused |
| A39 | Any | Token with edited `role`, bad signature; `alg: none`; expired; none | 401 each, audited |
| A40 | isha | Valid token plus `role: SENIOR`, `district: Hillcrest` claims | Ignored; JUNIOR Rivergate |
| A41 | Any | 1000 random or sequential ids on case, entity, link, stub, explanation, request, grant, change routes, as bharat and as hari | Identical 404 body and headers; each audited |
| A42 | esha | `?district=Rivergate` or `?case_id=C-101` on list | Filters never widen scope |
| A43 | Disabled user; logged-out `sid` | Unexpired access token | 401 |
| A44 | Any | Reuse a rotated refresh token | 401; whole `sid` revoked; audited |
| A45 | Any | 6 failed logins for the same username string, then for a nonexistent one | 429 in both cases |
| A46 | bharat | Review queue | Only ALLOW links; no stub appears |
| A47 | test | Walk the route table | Every route has a policy and an audit event |
| A48 | Worked scenario | AUTO person link between C-101 and C-201; bharat sees stub, requests, deepak approves, bharat reads explanation | Link AUTO throughout; stub, PENDING, grant ACTIVE; explanation returned |

## 8. Out of scope
Case management, FIR storage, SSO, per-field permissions, export, MFA, password reset or credential changes, citizen access.

## Open questions for Fable
1. One stub per hidden link makes the count of hidden links on one entity visible, a consequence of your one-link-per-request ruling. Recommend: accept for the MVP.
