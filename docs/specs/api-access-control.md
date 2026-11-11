# Spec: API access control

Owner: Khan (Backend Lead). Status: DRAFT for Security Reviewer. Task P1.3. Encoded as table-driven tests in `backend/tests/`.

## 1. Purpose and principles
The API decides who sees what, in two dimensions: **seniority** (role) and **jurisdiction** (district within state). A link into a case the caller may not see reveals that a connection exists and nothing else. Every decision, allow or deny, is audited (see `api-audit-log.md`). The matching engine creates AUTO links regardless of jurisdiction; that is a system action and never waits for a human. Access control governs only what an officer sees of such a link, and who may make human decisions on it. Rules live in the API; the UI may hide things but is never the control. Deny by default.

## 2. Model
### 2.1 Roles (canonical names, defined once here; other specs, tests and UI mappings cite these names. Rank examples are illustration only)
| Role | Illustrative ranks | Jurisdiction scope | Purpose |
|---|---|---|---|
| JUNIOR | Constable, Head Constable | one district | View cases, entities, links, explanations |
| INVESTIGATOR | Sub-Inspector, Inspector | one district | Above, plus confirm / reject links, source lines |
| SUPERVISOR | DSP, SP | one district | Above, plus undo, approve access requests |
| SENIOR | DIG, IG | one state (all its districts) | Above across the state; approves sensitive admin changes |
| ADMIN | Technical staff, no rank | none | Runs the system; has no case-data rights |

### 2.2 Jurisdiction
Two levels: state contains districts. Every case belongs to exactly one district. A user has one role and one jurisdiction node (district, or state for SENIOR; none for ADMIN).

### 2.3 Relation of a user to a case (computed server-side from the database, never from the token)
| Relation | Definition |
|---|---|
| own case | User is active and listed in `case_assignments` for the case |
| own jurisdiction | Case district is inside the user's scope, user not assigned |
| other jurisdiction | Everything else. ADMIN has no scope, so every case is "other" for ADMIN |

### 2.4 Outcomes
ALLOW = full payload. REDACTED = stub only (section 4). DENY = no payload; response per rule R2.

### 2.5 Rules
| # | Rule |
|---|---|
| R1 | Deny by default. Every route declares a policy; a route without one fails startup and a route-inventory test. Unknown action or role = DENY. |
| R2 | Order of checks: authenticate (401) -> resource ALLOW-visible? (404, identical body whether the id is unknown, hidden or only REDACTED) -> role permits? (403) -> state valid? (409). Visibility is checked before role and state so errors never confirm hidden things. A REDACTED link is reachable only as a stub inside list responses; by link id it is 404, so id guessing gives no oracle. |
| R3 | Actions touching several cases (a link has two ends) evaluate every end case; the worst outcome wins (DENY > REDACTED > ALLOW). |
| R4 | The caller is the only source of: the token and the request body. Role, jurisdiction, assignments, active flag are read from the database on every request. |
| R5 | Redaction and filtering are applied in the query or service layer, before serialization. No endpoint returns case data without passing through the policy function. |
| R6 | An active access grant (section 5) adds ALLOW on exactly the granted links and their evidence; it never changes the matrix cell for anything else. |

## 3. Permission matrix
Each cell is `own case / own jurisdiction / other jurisdiction`. A = ALLOW, R = REDACTED, D = DENY. For links, the relation is that of each end case (R3).

| Action (resource) | JUNIOR | INVESTIGATOR | SUPERVISOR | SENIOR | ADMIN |
|---|---|---|---|---|---|
| List cases | A/A/D | A/A/D | A/A/D | A/A/D | D/D/D |
| View case entities | A/A/D | A/A/D | A/A/D | A/A/D | D/D/D |
| View a link | A/A/R | A/A/R | A/A/R | A/A/R | D/D/D |
| View explanation | A/A/R | A/A/R | A/A/R | A/A/R | D/D/D |
| View source lines | A/D/D | A/A/D | A/A/D | A/A/D | D/D/D |
| Confirm / reject a link | D/D/D | A/A/D | A/A/D | A/A/D | D/D/D |
| Undo a link decision | D/D/D | D/D/D | A/A/D | A/A/D | D/D/D |
| Request access (via a stub) | D/A/A | D/A/A | D/A/A | D/A/A | D/D/D |
| Approve / deny access request (target case relation) | D/D/D | D/D/D | A/A/D | A/A/D | D/D/D |
| Revoke a grant (target case relation) | D/D/D | D/D/D | A/A/D | A/A/D | D/D/D |
| Upload data | D/D/D | D/D/D | D/D/D | D/D/D | A/A/A |
| Run matching | D/D/D | D/D/D | D/D/D | D/D/D | A/A/A |
| Manage users, roles, jurisdictions | D/D/D | D/D/D | D/D/D | D/D/D | A/A/A (see 3.1) |
| View audit log (rows whose target case has the relation) | D/D/D | D/D/D | A/A/D | A/A/R | R/R/R (see 3.2) |
| Change score thresholds | D/D/D | D/D/D | D/D/D | A/A/A (approver) | A/A/A (proposer, see 3.1) |

Notes: "Request access" on an own case is DENY because there is nothing to request. Upload, run matching, users and thresholds are system-wide, so the three columns are equal. Rejected and undone links are not connections: they produce no stub for anyone without ALLOW on both ends.

### 3.1 Senior approval ("major changes require senior approval")
One generic `pending_change` record (kind, subject, old value, new value, proposer, state PENDING / APPROVED / DENIED, decider). ADMIN changes to thresholds, to any user's role or jurisdiction, and creation of SUPERVISOR or SENIOR accounts create one. It takes effect only when a SENIOR other than the proposer approves; deny discards it. Until then the old value applies. ADMIN cannot hold an officer role on the same account.

### 3.2 ADMIN and the audit log
ADMIN reads system events (login, upload, matching, users, thresholds, audit views) in full. Case-bound events come back REDACTED: seq, time, event type, outcome, actor id only; target ids, case ids and details are null.

## 4. What a REDACTED link shows
Returned only as stubs embedded where a link would appear (entity detail, link list, graph neighbours, review queue) and from `GET /stubs/{stub_id}`. Never from any link-id route. At most one stub per near-side entity, however many links or cases are behind it.

| Field | Value |
|---|---|
| `redacted` | `true` |
| `stub_id` | Random opaque id, bound to (caller, near entity). Not derived from link, entity or case ids. Only usable for request access. |
| `near_entity_id` | The caller's own side entity (already visible) |
| `connection_exists` | `true` |
| `access_request` | `{status: NONE / PENDING / DENIED / EXPIRED, requested_at}` of the caller's own request only |
| `message_key` | i18n key, fixed text: a connection exists; request access to see details |

**Must never appear, in any response, header, log line shown to the caller, or error:**
far case id, number, title, district, state or officer; far entity id, type, name or value; link id, state (auto, suggested, confirmed), score, band, tier, signal names or evidence count; link creation time or run id; number of links or cases behind the stub.

| Channel | Rule |
|---|---|
| Counts | Totals, `link_count`, pagination totals, graph degree, dashboards and queue sizes count ALLOW items only. A stub counts as a boolean `has_hidden_connection`, never a number. |
| IDs | Hidden ids are never echoed. Unknown and hidden ids return the same 404 `{code: NOT_FOUND}`, same shape and comparable timing. |
| Errors | Messages are fixed strings per code. No 409 or 422 text derived from hidden data. Visibility check precedes validation (R2). |
| Search | Matches only ALLOW entities. A value that exists only in a hidden entity returns the same empty result as no match. Search never yields stubs. |
| Explanation | `GET /links/{id}/explanation` on a REDACTED link is 404. `GET /stubs/{stub_id}` returns the stub only: no signals, scores, bands, tier names, provenance. |
| Ordering | Stubs sort after visible items by `stub_id`, never by far-side attributes or time. |
| Graph | A stub is a leaf placeholder node with no label; no edges to far-side nodes. |
| Symmetry | The approver of a request sees the requester and reason, and only a stub of the requester's near side. |

## 5. Access-request lifecycle
| Item | Rule |
|---|---|
| Who requests | JUNIOR, INVESTIGATOR, SUPERVISOR, SENIOR, from a stub they hold. Reason required (10 to 500 chars, instruction: no personal data). Max 10 PENDING per user. |
| Fan-out | The server creates one approval item per distinct far case behind the stub. The requester sees one aggregate status. |
| Who approves | SUPERVISOR of the far case's district, or SENIOR whose state contains it (target relation own case or own jurisdiction). Never the requester. Never ADMIN. |
| Decision | Approve with duration 7, 30 or 90 days (default 30), or deny. Denied: requester may re-request the same stub after 24 hours. |
| States | Request: PENDING -> APPROVED / DENIED / WITHDRAWN (by requester) / EXPIRED (unanswered after 7 days). Grant: ACTIVE -> EXPIRED / REVOKED. |
| Grant scope | Read-only, limited to the links behind the stub at approval time: far-side entities of those links, their explanations, and the source lines cited as their evidence. Not the far case's other entities, not case lists, not confirm/reject/undo. A new link later is not covered. |
| Expiry | Hard `expires_at`; checked on every request; no renewal, re-request instead. Expiry returns the caller to the stub. |
| Revocation | By the approving authority (SUPERVISOR/SENIOR with the target relation), at any time, effective on the next request. Also automatic when the grantee's role, jurisdiction or active flag changes, or the link is rejected or undone. |
| Human decisions on cross-jurisdiction links | Only confirm / reject / undo. They need the matrix to ALLOW both ends (R3), which only a SENIOR whose state covers both ends satisfies; a grant does not qualify. No write grants in the MVP. The AUTO link itself exists from the start; it is not waiting for anyone. |
| Audit | Every create, decision, expiry, withdrawal and revocation is an audit event. |

## 6. Session rules
| Item | Rule |
|---|---|
| Auth | JWT, signing key from environment, algorithm pinned (`none` and algorithm switching rejected). Seeded synthetic users only. |
| Lifetime | Access token 15 minutes. Refresh token 8 hours absolute, rotated on use, single use. |
| Claims | `sub`, `sid`, `iat`, `exp`, `jti`, `ver`. Role and jurisdiction are not trusted from claims; any such claims are ignored. |
| Change of role, jurisdiction, assignment or disable | `authz_version` is bumped: tokens with an older `ver` get 401, refresh tokens are revoked, the user's grants are revoked. Assignment changes apply on the next request (database lookup). |
| Logout | Revokes the refresh token and `sid`. |
| Failures | Missing, malformed, expired, bad-signature or wrong-`ver` token: 401, audited as AUTH_TOKEN_REJECTED. Disabled user: 401. |

## 7. Acceptance cases
Seed (synthetic): states Northvale (districts Rivergate, Hillcrest), Eastmark (district Lakeside).
Cases: C-101 and C-102 Rivergate; C-201 Hillcrest; C-301 Lakeside.
Users: asha JUNIOR Rivergate (assigned C-101); isha JUNIOR Rivergate (no assignment); bharat INVESTIGATOR Rivergate (C-101, C-102); charu SUPERVISOR Rivergate; deepak SENIOR Northvale; esha INVESTIGATOR Hillcrest (C-201); farid SUPERVISOR Hillcrest; gita INVESTIGATOR Lakeside (C-301); hari ADMIN.
Entities and links: E-1 phone in C-101; E-2 same phone in C-201; E-3 in C-102; E-4 vehicle in C-101; E-5 in C-301; E-7 in C-201.
L-1 E-1~E-2 AUTO; L-2 E-1~E-3 AUTO; L-3 E-4~E-5 CONFIRMED; L-4 E-1~E-7 REJECTED.

| # | Actor | Attempt | Expected |
|---|---|---|---|
| A1 | asha | List cases | C-101, C-102 only; no C-201, C-301 |
| A2 | asha | View L-2 (C-101~C-102) | ALLOW full link |
| A3 | asha | Confirm L-2 | 403 |
| A4 | asha | View source lines of C-102 | 404 (D in own jurisdiction) |
| A5 | bharat | View L-1 (far end Hillcrest) | REDACTED stub; no far fields (section 4) |
| A6 | bharat | GET /links/L-1 directly by id | Same 404 as a random UUID, not 403 or 200; audited |
| A7 | bharat | GET /links/L-1/explanation; GET /stubs/{his L-1 stub_id} | 404; stub only (no signals, scores, tiers) |
| A8 | bharat | Entity E-1 detail | `link_count` excludes L-1 and L-3; `has_hidden_connection: true`; one stub only though two hidden links exist |
| A9 | bharat | Search the phone value that exists in E-2 only | Empty result identical to a non-existent number |
| A10 | bharat | Confirm L-2 | ALLOW; state CONFIRMED; audited |
| A11 | bharat | Undo L-2 | 403 (INVESTIGATOR cannot undo) |
| A12 | charu | Undo L-2 | ALLOW; state UNDONE; pair not auto-linked again |
| A13 | charu | Confirm L-1 | 404 (C-201 end is other jurisdiction; visibility fails before role) |
| A14 | deepak | Confirm L-1 (both ends in Northvale) | ALLOW; AUTO becomes CONFIRMED |
| A15 | deepak | View L-3 (far end Eastmark) | REDACTED |
| A16 | bharat | Request access on L-1's stub with a valid reason | Request PENDING; stub shows PENDING |
| A17 | bharat | Request access using a link id, case id or entity id in place of `stub_id` | 404 |
| A18 | bharat | Approve own request | 403 |
| A19 | charu | Approve bharat's request (target C-201 is not hers) | 404 |
| A20 | farid | Approve bharat's request for 30 days | Grant ACTIVE; farid saw only a stub of bharat's near side |
| A21 | bharat | After A20: view L-1, explanation, cited source lines of E-2 | ALLOW. View other entities of C-201, or list C-201: 404 |
| A22 | bharat | After A20 or A38: confirm L-1 | 403 (visible via grant, role/state: grant does not qualify, R3). Stays AUTO |
| A23 | bharat | After A20 and 31 days (clock injected) | Back to stub; AccessGrant EXPIRED |
| A24 | farid | Revoke the grant; bharat repeats A21 | Stub again on the next request |
| A25 | bharat | Role raised or district changed by hari and approved by deepak; reuse old access token | 401; grant revoked |
| A26 | hari | List cases, view entities, view L-1, view explanation | All DENY (404 for case resources); hari holds no jurisdiction rights |
| A27 | hari | Approve an access request; confirm a link | 403 |
| A28 | hari | Upload data; run matching | ALLOW; response contains only batch id and system-wide totals, no case ids or per-case counts |
| A29 | hari | Raise a threshold | PROPOSED, old value still applies; approval by hari rejected; deepak approves, value changes |
| A30 | hari | View audit log | System events full; case-bound rows REDACTED (section 3.2) |
| A31 | Any | Token with `role` claim edited to SENIOR, signature invalid | 401; AUTH_TOKEN_REJECTED |
| A32 | Any | Valid token for isha with extra `role: SENIOR`, `district: Hillcrest` claims | Claims ignored; treated as JUNIOR Rivergate |
| A33 | Any | Token with `alg: none`; expired token; no token | 401 each |
| A34 | Any | Enumerate 1000 sequential or random UUIDs on case, entity, link, explanation routes | Every non-visible id: identical 404 body; each denial audited |
| A35 | test | Walk the route table | Every route has a policy; a route without one fails |
| A36 | esha | List C-101 via `?district=Rivergate` or `?case_id=` filter | Filter cannot widen scope; result empty |
| A37 | Disabled user | Valid unexpired token | 401 |
| A38 | Worked scenario: person link L-1 is AUTO between C-101 (Rivergate) and C-201 (Hillcrest) | bharat sees stub; requests access; deepak (SENIOR, Northvale) approves; bharat reads the explanation | Link existed AUTO before any human acted; stub, then PENDING, then grant ACTIVE; explanation returns signals and scores; state still AUTO |

## 8. Out of scope
Case management, FIR storage, SSO, per-field permissions, export/print, MFA, citizen access.

## Open questions for Fable
1. Token lifetimes 15 min / 8 h and one role per user. Recommend: accept for the demo.
