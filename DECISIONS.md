# DECISIONS

Append-only log. Newest at the bottom. `[A]` = assumption from the source document adopted as a working default; `[O]` = ruled by the owner.

| # | Date | Decision | Reason |
|---|---|---|---|
| D1 | 2026-11-11 | FastAPI only; Flask dropped | PPT lists both; one framework is enough (C4) |
| D2 | 2026-11-11 | Neo4j Community + PostgreSQL in Docker Compose | PPT stack; free, runs offline |
| D3 | 2026-11-11 | React + TypeScript + Vite, D3 for graph view | PPT says React + D3; TS and Vite for type safety and speed |
| D4 | 2026-11-11 | RapidFuzz + phonetic keys for fuzzy matching | PPT silent; small, fast, explainable |
| D5 | 2026-11-11 | Deterministic extractor is the default; LLM extractor is an optional adapter, off by default | Explainable and offline-safe (C2). Owner has no LLM/Bhashini credentials [O] |
| D6 | 2026-11-11 | Offline transliteration library by default; Bhashini adapter is a stretch item | No Bhashini credentials [O]; demo must not hinge on a network call even though the venue has internet |
| D7 | 2026-11-11 | Audit log = Postgres table, UPDATE/DELETE blocked by trigger, rows hash-chained | Append-only and tamper-evident without a blockchain |
| D8 | 2026-11-11 | JWT auth with seeded synthetic users; access rules enforced in the API | Simple, testable |
| D9 | 2026-11-11 | Surfaces: backend, officer app, admin panel, data kit. No citizen app | Scope is the entity-resolution MVP |
| D10 | 2026-11-11 | Core scope is entity resolution; a "most connected" indicator is a stretch item | PPT promises kingpin ranking, document scopes it out (C1); owner did not overrule |
| D11 | 2026-11-11 | Confirm / reject / undo link is core; manual "add missing entity" is a stretch item | C3; owner did not overrule |
| D12 | 2026-11-11 | Synthetic data only, from our own generator; no data.gov.in | Owner ground rule (C5) |
| D13 | 2026-11-11 | IDs shown in the product: Problem Statement ID PS26189, Team ID 158221, Team TraceX | Owner: PPT team ID is the accurate one; "PS<number>" is the problem statement ID [O] |
| D14 | 2026-11-11 | PPT slide 4 "Major changes require…" read as "require senior approval" | Truncated in the deck (C7); matches the document's access rules |
| D15 | 2026-11-11 | Demo languages: English and Hindi (Devanagari). Urdu-origin names appear in Roman and Devanagari only | [O] |
| D16 | 2026-11-11 | No date-based freeze. Build continuously; when limits bite, checkpoint and hand the owner resume prompts | [O] |
| D17 | 2026-11-11 | Private GitHub repo `tracex` under the logged-in account | [O] |
| D18 | 2026-11-11 | The source document and PPT stay on disk, ignored by git | Agents must get only the sections they need, never the whole files |
| D19 | 2026-11-11 | One bootstrap commit of governance files goes straight to `main`; every later change goes through a PR | A repo needs a first commit before branches and PRs exist |
| D20 | 2026-11-11 | [A] Three confidence bands: high = auto SAME_AS, medium = review queue, low = no link. Thresholds set in the matching spec, adjustable by admin | Document assumption |
| D21 | 2026-11-11 | [A] Tier signals follow the document's examples; exact list fixed in the matching spec | Document assumption |
| D22 | 2026-11-11 | [A] Junior officers view links in their own cases; confirm / reject needs a higher role. Other-jurisdiction links show "a connection exists" plus request access | Document assumption |
| D23 | 2026-11-11 | [A] A wrongly confirmed link is undone by removing the edge; it is audited; the rejected pair is not auto-linked again. No score feedback loop | Document open question; simplest honest behaviour |
| D24 | 2026-11-11 | Role continuity across sessions comes from the role card + STATE.md + repo, not agent memory | Agents do not persist between sessions |
| D25 | 2026-11-11 | Roles: JUNIOR, INVESTIGATOR, SUPERVISOR, SENIOR, ADMIN; jurisdiction = district within state. Canonical table lives in `docs/specs/api-access-control.md` | Khan's access spec, accepted |
| D26 | 2026-11-11 | High-band links are created automatically regardless of jurisdiction. Officers outside the jurisdiction see a redacted "connection exists" stub until access is granted. Human confirm / reject / undo on a cross-jurisdiction link needs a SENIOR covering both ends. No write grants | Khan proposed holding such links for a human; that contradicts the document and breaks the worked scenario |
| D27 | 2026-11-11 | ADMIN changes to thresholds, roles and jurisdictions need approval by a SENIOR via one generic pending-change record | PPT: "major changes require" approval; kept minimal |
| D28 | 2026-11-11 | Audit insert failure fails the request; head hash is also copied by hand into the runbook; tokens 15 min access / 8 h refresh; one role per user | Khan's recommendations, accepted |
| D29 | 2026-11-11 | The admin panel is used by SUPERVISOR, SENIOR and ADMIN. Review queue, access requests and graph show case details only to roles with case rights in that jurisdiction; ADMIN sees counts and status, plus uploads, matching runs, users, thresholds and system audit events | ADMIN has no case-data rights (D25); raised by Sen |
| D30 | 2026-11-11 | UI: Western digits in Hindi; Reject takes a second step, Confirm has Undo; low-band pairs are never stored, listed or drawn | Sen's design rules, accepted |
| D31 | 2026-11-11 | Visual identity: white and cool grey, one dark action blue, Noto Sans + Noto Sans Devanagari, Lucide icons; officer app 20px body, 56px targets | Sen's DESIGN_RULES.md (PR #2) |
| D32 | 2026-11-11 | Who decides links: INVESTIGATOR+ confirm / reject a suggested link on cases they can access; SUPERVISOR+ undo and reopen; SENIOR covering both ends for cross-jurisdiction links; an AUTO link can only be undone, not rejected. Supersedes the looser wording in D22 | Access spec is canonical; Khan's review of PR #3 |
| D33 | 2026-11-11 | Link and cluster ids are opaque; cluster and path responses are computed per viewer with hidden segments as stubs; explanation params are codes, wording lives in template keys; the engine returns transition records and the API writes audit rows | Khan's review of PR #3 (blocker: id and path leaks) |
| D34 | 2026-11-11 | "Reopen a rejected link" lives only in the admin panel review queue (a Rejected filter), not in the officer app | Keeps the officer app simple; raised by Sen. To be added to design-flows A3 with the next design task |
| D35 | 2026-11-11 | Security rulings on the access/audit specs: two-case audit rows are scoped by both sides with the far side redacted; every ADMIN change to users, roles, assignments, jurisdictions and thresholds needs approval by a SENIOR covering the subject who is neither proposer nor subject; no password reset in the MVP; an access grant is for one link and one far case, read-only, fixed at approval, capped by the requester's role; unseen things return 404 never 403; the API database role cannot alter the audit table; head hash is also anchored automatically to a file outside the database; SENIOR coverage is a set of jurisdictions and one seeded SENIOR covers all states for cross-state links | Dutta's gate review of PR #1 |
| D36 | 2026-11-11 | Branch protection on `main`: PR required, CI checks `backend` and `frontend` required, no force-push. Zero GitHub approvals required because all agents act through one GitHub account; review by a different agent is enforced by PROTOCOLS §3 | A single account cannot approve its own PR on GitHub |
