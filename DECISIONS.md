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
