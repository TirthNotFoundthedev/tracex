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
| View audit log (rows by case relation) | D/D/D | D/D/D | A/A/D | A/A/D | D/D/D |
| Verify audit chain | D/D/D | D/D/D | D/D/D | A/A/A | D/D/D |
| View system link totals (`GET /stats/links`) | D/D/D | D/D/D | D/D/D | D/D/D | A/A/A |
| Read own access requests and grants; read requests and grants of cases in own authority | A/A/A (own) | A/A/A (own) | A/A/D (authority) | A/A/D (authority) | D/D/D |

Notes: "Request access" on an own case is DENY (nothing to request). System-wide rows have equal columns. Audit reads follow one row-level rule (audit spec section 7): rows the reader may not see do not exist for them; ADMIN reads system events only. Rejected and undone links are not connections: no stub.

### 3.1 Link states: who may change them
| From -> To | Role (both end cases must be ALLOW for the caller by their own scope, R3) | Reason |
|---|---|---|
| SUGGESTED -> CONFIRMED, AUTO -> CONFIRMED | INVESTIGATOR+ | no |
| SUGGESTED -> REJECTED | INVESTIGATOR+ | yes |
| AUTO or CONFIRMED -> UNDONE | SUPERVISOR+ | yes |
| REJECTED or UNDONE -> SUGGESTED (reopen) | SUPERVISOR+ | yes |
An AUTO link can be undone but not rejected (409). A link whose ends are in different districts or states is decided only by a SENIOR whose coverage includes both ends; a grant never qualifies. Reasons live in the link history, not the audit log. Engine transitions (create, demote) come as transition records; the API audits them.

### 3.2 Pending changes (four-eyes; "major changes require senior approval")
The MVP has seeded users and no password feature: no route sets or resets credentials. Every ADMIN change to users (create, enable, disable), roles, jurisdictions, case assignments and thresholds is one generic `pending_change` (kind, subject, old value, new value, proposer, `change_hash` = SHA-256 of the canonical content, state PENDING / APPROVED / DENIED, decider). It applies only on approval. **Closed allow-list (D35, D51):** each change type has a fixed list of keys it accepts (USER_CREATE: `username`, `display_name`, `role`, and one of `district_id` or `coverage`; USER_ENABLE and USER_DISABLE: none; USER_ROLE: `role`, plus `coverage` when the new role is SENIOR or `district_id` when a SENIOR or ADMIN becomes a district role (required there, refused elsewhere); USER_JURISDICTION: one of `district_id` or `coverage`; ASSIGNMENT_ADD and ASSIGNMENT_REMOVE: `case_number`; THRESHOLDS: `high_min`, `medium_min`). Any other key, at the top level, in `new_value` or in `coverage`, is refused with 422 `unknown_field` and nothing is stored. The stored value, the value the approver sees and the value that is applied are built from those keys only, and `change_hash` covers exactly that value. `coverage` is strict: `all_states` is a JSON boolean, and `state_ids` and `district_ids` are lists of unique ids, otherwise 422. A SENIOR or ADMIN has no district, so a district recorded for one never counts as authority to approve that district.
| Rule | |
|---|---|
| Approver | SENIOR whose coverage includes **every** jurisdiction the change touches, old and new: the subject's district; for an assignment change also the **district of the case**; for USER_CREATE and USER_JURISDICTION the new coverage must be a subset of the approver's coverage. Changes whose subject has no district (an ADMIN), changes of role to or from SENIOR or ADMIN, and thresholds need a SENIOR with all-state coverage. Not the proposer, not the subject. A caller outside that set gets 404 (a pending change and the case number inside it do not exist for them). |
| Binding | Approval presents the `change_hash`. A changed proposal is a new record needing new approval. If the current value no longer equals `old_value`, approval fails (409). |
| New accounts | USER_CREATE makes an account with no usable password; a login for it fails exactly like a wrong password. No route sets one. |
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

### 4.1 Masking of identifier values (N4)
Names and vehicles are not masked in the MVP. **PHONE and ACCOUNT values** (and any government-id type added later) are shown in full only to a caller who may read source lines of the case the value belongs to, by the "View source lines" cell: JUNIOR own case; INVESTIGATOR and above own case and own jurisdiction; a grant only for a non-JUNIOR holder. Everyone else sees a masked value.
| Rule | |
|---|---|
| Server side | The API masks. When a value is masked, the full value appears **nowhere** in that response: not in `display_value`, `facts`, explanation `records[].raw_text` and `normalized`, evidence params `value`, `value_a`, `value_b` and `list`, `main_reason.params`, or a header or error. Search matches on the full value only for callers who see it in full. |
| Flag | `masked` is true on an object when any value in it was masked. |
| Formats (fixed) | Phone: first 2 and last 4 digits, the rest `x` (`98xxxx1234`). Account: last 4 digits behind exactly 8 `x`, whatever its length. |
| Test | For each masked view (entity, list, explanation, graph, cluster, path, queue, stub-adjacent) scan the response body for every seeded full value; none may appear. |

### 4.2 Actor names and reasons on queue items (TIR-85)
**Actor names.** `actor` on a history entry or on `last_decision` is a `UserRef` (name and role) only when the viewer may already know that person. The API checks this in the policy layer from the database at read time, never from the token, using the actor's current user record:
- the viewer is the actor; or
- the viewer is a SUPERVISOR, the actor is a JUNIOR, INVESTIGATOR or SUPERVISOR, and the actor's district is the viewer's district (chain of command, audit spec section 7 (b)); or
- the viewer is a SENIOR and `GET /users/{actor}` would return 200 for that viewer (actor inside coverage).

In every other case `actor` is `null`. This covers a JUNIOR or INVESTIGATOR viewing anyone else's decision, a SUPERVISOR viewing a SENIOR's decision, an actor outside the viewer's scope or coverage, and a SYSTEM or ADMIN actor. A null `actor` carries no role, district or partial name. `actor_user_id` stays as it is today. Resolving `actor` writes no audit row of its own, neither a user read nor an ACCESS_DENIED.

**Reason on queue items.** `last_decision.reason_text` follows the same rule as `reason_text` in link history: it is returned only when both ends of the link are ALLOW for the viewer by their own scope, never under a grant. It is built by the same policy function as the history entry (R5). Queue items are ALLOW-only by own scope (section 4), so every viewer who receives the queue item may receive its reason. `last_decision` is null for SUGGESTED items.

**Counts.** `total` on every page counts only the items the viewer may see (ALLOW), with the page's filters applied. It never includes stubs, grant-only links or hidden items.

## 5. Access-request lifecycle
| Item | Rule |
|---|---|
| Request | From one stub: one link, one far case. No fan-out, no aggregate. Reason 10 to 500 chars (no personal data). Requesters: JUNIOR, INVESTIGATOR, SUPERVISOR, SENIOR. Max 10 PENDING per user. |
| Approver | SUPERVISOR of the far case's district, or SENIOR whose coverage includes it. Never the requester, never ADMIN. |
| States | Request: PENDING -> APPROVED / DENIED / WITHDRAWN / EXPIRED (7 days). Grant: ACTIVE -> EXPIRED / REVOKED. Denied: re-request after 24 hours. |
| Duration | 7, 30 or 90 days (default 30); hard `expires_at`, checked every request; no renewal. |
| Grant scope | Read-only. The far entity of that one link, the link's explanation, and the **exact source-line ranges** cited by its evidence, fixed at approval. Capped by the holder's role in their own jurisdiction (a JUNIOR gets no source lines). Covers only the link existing at request time. |
| No pivot | The far entity under a grant shows only the granted link: no stubs, no counts, no other links; it cannot anchor a stub or request. Other entities of the far case stay hidden (404). |
| Closes when | Link REJECTED or UNDONE, evidence later cites a line outside the fixed ranges (cause EVIDENCE_CHANGED), holder's role, jurisdiction, assignment or active flag changes, expiry, or revocation by the approving authority (effective next request). |
| Status shown | One status per stub. Approval simply makes the link ALLOW. |
| Denial note | The optional note reaches the requester: it must carry no case detail (the field is 200 characters and the UI says so). |
| Approver's own stub | The approver gets a stub bound to (approver, link) with `near_entity_id` on the approver's side; the requester's `stub_id` and near entity are never shown to the approver. |
| Views | Requester and approver have different response shapes (`AccessRequestMine`, `AccessRequestToDecide`; `GrantHeld`, `GrantAuthority`); neither carries a field of the other. |
| Approver view of the far case | `AccessRequestToDecide` carries `far_case_id` and `far_case_number` of the far case, which lies in the decider's own district (SUPERVISOR) or coverage (SENIOR). It carries no other far-case field. `AccessRequestMine` never carries either field. |
| Approver view of the requester | The decider sees the requester only as `UserRef` (user id, display name, role) and the requester's reason. No district, state, coverage or case of the requester appears in `AccessRequestToDecide`, its errors or its audit detail: the requester's side is the far side of the decider's own stub (section 4). |

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
Seed (synthetic): state Northvale (districts Rivergate, Hillcrest), state Eastmark (Lakeside). Cases: C-101, C-102 Rivergate; C-201, C-202 Hillcrest; C-301 Lakeside; C-401 Rampur (Eastmark; no user, meena covers it). `case_number` is unique per district.
Users: asha JUNIOR Rivergate (C-101); isha JUNIOR Rivergate (no assignment); bharat INVESTIGATOR Rivergate (C-101, C-102); charu SUPERVISOR Rivergate; deepak SENIOR coverage Northvale; meena SENIOR coverage all states; esha INVESTIGATOR Hillcrest (C-201); farid SUPERVISOR Hillcrest; gita INVESTIGATOR Lakeside (C-301); hari ADMIN.
Entities: E-1 phone C-101; E-2 same phone C-201; E-3 C-102; E-4 vehicle C-101; E-5 C-301; E-7 C-201; E-8 C-202 (same phone value as E-1, in its own case so within-case merging cannot absorb it into E-2). A38 uses a second all-state SENIOR created only inside the test.
Links: L-1 E-1~E-2 AUTO; L-2 E-1~E-3 AUTO; L-3 E-4~E-5 CONFIRMED; L-4 E-1~E-7 REJECTED. L-5 E-1~E-8 AUTO is created after bharat's request in A22.

| # | Actor | Attempt | Expected |
|---|---|---|---|
| A1 | asha | List cases | C-101, C-102 only |
| A2 | asha | View L-2 | ALLOW |
| A3 | asha | Confirm L-2 | 403 |
| A4 | asha | Source lines of C-102 (case visible, cell D) | 403 |
| A5 | bharat | E-1 detail; E-4 detail | E-1: one stub for L-1 (L-4 is REJECTED, no stub). E-4: one stub for L-3. Same shape whatever the state; no far fields |
| A6 | bharat | GET /links/L-1 by id | Same 404 as a random UUID; audited |
| A7 | bharat | GET /links/L-1/explanation; GET /stubs/{L-1 stub} | 404; stub only |
| A8 | bharat | E-1 `link_count`; E-4 `link_count` | E-1 excludes L-1; E-4 excludes L-3; both `has_hidden_connection: true` |
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
| A38 | hari | In a test with a second all-state SENIOR who is then the only other approver: propose disabling the SENIOR who is the last able to approve Lakeside; approve | 409 `LAST_APPROVER` refused |
| A39 | Any | Token with edited `role`, bad signature; `alg: none`; expired; none | 401 each, audited |
| A40 | isha | Valid token plus `role: SENIOR`, `district: Hillcrest` claims | Ignored; JUNIOR Rivergate |
| A41 | Any | 1000 random or sequential ids on case, entity, link, stub, explanation, request, grant, change routes, as bharat and as hari | Identical 404 body and headers; each audited |
| A42 | esha | `?district=Rivergate` or `?case_id=C-101` on list | Filters never widen scope |
| A43 | Disabled user; logged-out `sid` | Unexpired access token | 401 |
| A44 | Any | Reuse a rotated refresh token | 401; whole `sid` revoked; audited |
| A45 | Any | 6 failed logins for the same username string, then for a nonexistent one | 429 in both cases |
| A46 | bharat | Review queue | Only ALLOW links; no stub appears |
| A47 | test | Walk the route table | Every route has a policy and an audit event |
| A52 | bharat | `GET /links/{id}`, its explanation and a stub of a WITHDRAWN link | Same 404 as a random id; not listed anywhere |
| A53 | hari | Start a run scoped to one batch, then read the run | Matched against all loaded cases; response has totals of AUTO and SUGGESTED created only: no LOW count, no per-case or per-pair counts |
| A54 | charu | Review queue, REJECTED, after bharat (INVESTIGATOR, Rivergate) rejected a Rivergate-only link; and after deepak (SENIOR) did | `last_decision.actor` is bharat's `UserRef`; `null` for deepak. Same on `GET /links/{id}` history |
| A55 | asha | Queue, UNDONE, after charu undid a link; and a link whose stored decider is asha | `actor` null; asha's own `UserRef` for her own decision |
| A56 | deepak | Queue, after meena (all-state SENIOR) rejected a Rivergate-only link | `actor` null: `GET /users/{meena}` would be 404 for deepak |
| A57 | charu | One review-queue page with `last_decision` | Exactly one REVIEW_QUEUE_VIEWED row; no LINK_VIEWED, user-read or ACCESS_DENIED row; no name or reason text in the log |
| A58 | bharat / deepak | Review queue `total` with and without filters | Equals the number of ALLOW items matching the filters (bharat 1, deepak 3 of the three SUGGESTED person links) |
| A49 | deepak | Approve an ASSIGNMENT_ADD naming C-301 for a Northvale officer; approve a USER_CREATE of a SENIOR covering Eastmark | 404 (case district outside coverage); 404 (new coverage not a subset) |
| A50 | asha, isha, bharat | Fetch entity, list, explanation of a phone in C-102 (asha: own case) and in C-201 under a grant held by isha (JUNIOR) | asha sees it in full; the other masked (`98xxxx1234`); the full value is in no field of the body |
| A51 | hari | `GET /stats/links` | One object of totals; no parameters, no breakdown; any officer role 404; `/review-queue` 404 for hari |
| A48 | Worked scenario | AUTO person link between C-101 and C-201; bharat sees stub, requests, deepak approves, bharat reads explanation | Link AUTO throughout; stub, PENDING, grant ACTIVE; explanation returned |

## 8. Out of scope
Case management, FIR storage, SSO, per-field permissions, export, MFA, password reset or credential changes, citizen access.
