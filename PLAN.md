# TraceX — PLAN

Status: APPROVED by the owner 2026-11-11. Rulings on §3 and §11 are recorded in DECISIONS.md, which wins where it differs from this file. Written by Fable (CEO / Project Lead / CTO).
Sources: "TraceX: How the Project Works" (behaviour, authoritative) and the SIH PPT (stack and pitch, authoritative).
Nothing below has been built. No agent has been spawned.

## 1. Product surfaces

One monorepo, four deliverables, one backend.

| Surface | Users | What it does | Simplicity level |
|---|---|---|---|
| **Engine + API** (`backend/`) | none directly | Stages 1–6: ingest, extract, normalize, per-case graphs, three-tier matching, composite score, unified graph with SAME_AS edges. Also auth, access control, audit log, review queue. | n/a |
| **Officer app** (`apps/officer/`) | Constables to inspectors, incl. low-literacy officers | My cases → a person/phone/account/vehicle → "also appears in" other cases → explanation panel → confirm / reject (if role allows) → request access to another jurisdiction's case. English and Hindi. | Simplest. One primary action per screen. |
| **Admin panel** (`apps/admin/`) | Senior officers, system admins | Upload case material, run matching, review queue for medium-band matches, access requests, users / roles / jurisdictions, audit log viewer, score thresholds. Network graph view lives here. | Denser, still plain. |
| **Synthetic data kit** (`data-kit/`) | us, demo | Generates multilingual synthetic cases (FIR text, CDR rows, bank rows, case metadata, investigator notes) with planted ground-truth links, including the document's Irfan scenario. | n/a |

Connections: both apps talk only to the API over HTTP (OpenAPI contract in `contracts/`). Apps share a UI package (`packages/ui/`: tokens, components, i18n strings). The engine is a Python package the API imports; it never talks to the apps directly. Neo4j holds the graphs; PostgreSQL holds users, roles, source documents and provenance, review decisions, access requests and the audit log.

Deliberately not built: a separate public/citizen app, FIR storage or case management, machine-learned matching.

## 2. Stack (from the PPT, gaps filled)

| Area | Choice | Source |
|---|---|---|
| API | Python, **FastAPI only** | PPT says "Flask + FastAPI"; two frameworks is waste. See conflict C4. |
| Graph | Neo4j Community (Docker), Cypher | PPT |
| Relational | PostgreSQL (Docker) | PPT |
| Frontend | React + TypeScript + Vite, D3 for the graph view | PPT (TypeScript and Vite are my additions) |
| Data processing | Pandas for CDR / bank parsing; scikit-learn only if needed | PPT |
| Fuzzy matching | RapidFuzz + phonetic keys tuned for Indian names | Mine: PPT is silent |
| Transliteration | Offline library (indic-transliteration) by default; Bhashini behind an adapter, optional | PPT names Bhashini; demo must not depend on a network call |
| Entity extraction | Deterministic rules + gazetteers + transliteration by default; LLM extractor behind the same interface, optional | See conflict C2 |
| Auth | JWT, seeded synthetic users, role + jurisdiction checks enforced in the API | Mine |
| Audit log | Postgres table, UPDATE/DELETE blocked by trigger, each row hash-chained to the previous | Mine: fits the "Blockchain & Cybersecurity" theme honestly, without a blockchain |
| Tests | Pytest, Vitest, Playwright; Postman collection exported from OpenAPI | PPT + mine |
| Tooling | uv, Ruff, mypy, ESLint, Prettier, Docker Compose, GitHub Actions | Mine |
| Run | `docker compose up` + one seed command | Mine |

Toolchain already present on this machine: git, Docker, Node, Python, uv, gh (logged in).

## 3. Conflicts between the PPT and the document (need your ruling)

| # | PPT says | Document says | My working default |
|---|---|---|---|
| C1 | System "ranks importance", finds the "kingpin", "detects patterns" | Scope is cross-case entity resolution only | Core = entity resolution. Add one cheap "most connected" indicator on identity clusters as a stretch item, so the pitch claim is not empty. |
| C2 | Extraction by "LLM, local generative models" | No tech named; prototype is rule-based and must be explainable | Deterministic extractor is the default and the one the demo runs on. LLM extractor is pluggable and off by default. |
| C3 | "Allow users to add data on their own" when the AI misses something | Not mentioned; only confirm / reject links | Confirm / reject / undo a link is core. Manual "add a missing entity" is a stretch item. |
| C4 | Flask + FastAPI | — | FastAPI only. |
| C5 | Demo data from data.gov.in / LLM | — (your ground rule: synthetic only) | Synthetic generator only. No external datasets. |
| C6 | PS ID "SIH26189", Team ID 158221 | "PS26189", "Group 68" | Cosmetic. I use SIH26189 / Team TraceX in the UI footer unless told otherwise. |
| C7 | Slide 4 ends mid-sentence: "Major changes require" | Confirm/reject of cross-case links needs a higher role | Read as "require senior approval". |

## 4. Org chart

```
Fable (CEO / Project Lead / CTO) — plans, briefs, reviews lead output, decides
├── Engine Lead ............... Opus    matching tiers, scoring, explanation payload
│   ├── NLP Engineer .......... Sonnet  extraction, normalization, transliteration
│   └── Graph & Data Engineer . Sonnet  Neo4j schema, per-case + unified graph, data kit
├── Backend Lead .............. Sonnet  API, auth, access control, audit log, contracts
├── Officer App Lead .......... Sonnet  officer app
├── Admin App Lead ............ Sonnet  admin panel
├── Design Lead ............... Sonnet  DESIGN_RULES.md, tokens, components, UI review (can block)
├── DevOps & Release Manager .. Sonnet  repo, branches, merges, tags, CI, compose (Haiku for routine hygiene sweeps)
├── Security Reviewer ......... Opus    on-demand gate review: auth, access control, audit, data handling
└── QA Lead ................... Sonnet  runs tester rounds, writes tickets
    └── Independent testers ... Sonnet  brand-new agent per run; persona + running app + goal only
```

Ten standing roles. One role = one agent; work for a role is always sent to that role. Full cards go in ROSTER.md. A harness limit to be honest about: an agent's memory does not survive across sessions, so continuity for a role comes from its role card, STATE.md and the repo, not from the agent remembering.

Review matrix (author ≠ reviewer): Engine Lead reviews NLP and Graph work; Backend Lead reviews engine integration; Engine Lead reviews Backend's scoring/explanation endpoints; app leads review each other; Design Lead reviews every UI change; Security Reviewer gates auth / access / audit / data handling; I review lead summaries and anything contested.

Wall between dev and test: testers get no repo access, no docs, no prior results. Their reports go only to the QA Lead. Devs and the Design Lead see tickets only.

## 5. Work breakdown

Dependencies run top to bottom; items marked ∥ run in parallel.

| # | Task | Owner | Model | Why that model | Depends on |
|---|---|---|---|---|---|
| **P0 Foundation** | | | | | |
| 0.1 | Git repo, branch protection, .gitignore, README, monorepo skeleton | Release Mgr | Sonnet | Mechanical but must be right once | go-ahead |
| 0.2 | AGENT_RULES, PROTOCOLS, CODEBASE_RULES, ROSTER, STATE, DECISIONS | Fable | — | Governance is my job; short files | go-ahead |
| 0.3 | CI (lint, type-check, tests), compose file, one-command run | Release Mgr | Sonnet | Standard work | 0.1 |
| **P1 Specs and contracts** | | | | | |
| 1.1 | Matching spec: tier signals, evidence weights, score formula, bands, conflict handling, undo | Engine Lead | Opus | The core design; errors here are the costliest | 0.2 |
| 1.2 | Data model + OpenAPI contract + explanation payload schema | Backend Lead (Engine Lead reviews) | Sonnet | Well-bounded once 1.1 exists | 1.1 |
| 1.3 | Access-control matrix (role × jurisdiction × action) and audit event list | Backend Lead, Security Reviewer signs off | Sonnet + Opus review | Security-critical, small | 0.2 |
| 1.4 | DESIGN_RULES.md, tokens, component list, screen flows for both apps ∥ | Design Lead | Sonnet | Judgment within clear constraints | 0.2 |
| 1.5 | Synthetic dataset spec with planted ground truth ∥ | Graph & Data Eng | Sonnet | Structured work | 1.1 |
| **P2 Engine vertical slice** (Irfan scenario end to end) | | | | | |
| 2.1 | Data kit generator | Graph & Data Eng | Sonnet | | 1.5 |
| 2.2 | Parsers (CDR, bank) + extraction + normalization, tests first ∥ | NLP Eng | Sonnet | Escalate transliteration edge cases to Opus only on failure | 1.2 |
| 2.3 | Per-case graphs, within-case dedupe, provenance ∥ | Graph & Data Eng | Sonnet | | 1.2 |
| 2.4 | Tier 1 + scoring skeleton + SAME_AS (non-destructive) | Engine Lead | Opus | Sets the pattern the other tiers follow | 2.2, 2.3 |
| **P3 Full engine + backend** | | | | | |
| 3.1 | Tier 2 fuzzy / probabilistic | NLP Eng (Engine Lead reviews) | Sonnet | Spec is explicit by now | 2.4 |
| 3.2 | Tier 3 contextual (shared contacts, shared counterparties, co-location) | Graph & Data Eng (Engine Lead reviews) | Sonnet | Same | 2.4 |
| 3.3 | Composite score, bands, review queue, undo, identity clusters | Engine Lead | Opus | Correctness of the headline feature | 3.1, 3.2 |
| 3.4 | API, auth, access control, access requests, audit log ∥ | Backend Lead | Sonnet | | 1.2, 1.3 |
| 3.5 | Security review of 3.4 | Security Reviewer | Opus | Rule 4 gate | 3.4 |
| **P4 Apps** (start against a mocked contract, in parallel with P3) | | | | | |
| 4.1 | Shared UI package: tokens, components, i18n (EN + HI) | Design Lead + Officer App Lead | Sonnet | | 1.4 |
| 4.2 | Officer app | Officer App Lead | Sonnet | | 4.1, 1.2 |
| 4.3 | Admin panel incl. graph view | Admin App Lead | Sonnet | | 4.1, 1.2 |
| 4.4 | Screenshot review of every screen against DESIGN_RULES | Design Lead | Sonnet | | 4.2, 4.3 |
| **P5 Independent testing and fixes** | | | | | |
| 5.1 | Tester round 1 (5 personas), tickets, fixes | QA Lead → leads | Sonnet | | P3, P4 |
| 5.2 | Round 2 on fixed build (new testers) | QA Lead | Sonnet | | 5.1 |
| 5.3 | Final security + architecture review | Security Reviewer | Opus | | 5.1 |
| **P6 Demo readiness** | | | | | |
| 6.1 | Demo runbook, seed script, architecture overview, API doc current | Release Mgr + Backend Lead | Sonnet | | 5.2 |
| 6.2 | Stretch items if budget allows: "most connected" indicator, manual entity add, optional LLM / Bhashini adapters | relevant lead | Sonnet | | 5.2 |
| 6.3 | Tag `v1.0-demo`, pitch/PPT alignment notes for you | Release Mgr, Fable | — | | 6.1 |

Milestone tags: `m0-foundation`, `m1-specs`, `m2-slice`, `m3-engine`, `m4-apps`, `v1.0-demo`.

## 6. Cost plan

Usage right now: 5-hour window 15%, weekly all-models 5%, weekly Fable 2%. Extra usage has a 0.00 limit, so the windows are hard stops.

- Expected split of agent tokens: about 75% Sonnet, 20% Opus, 5% Haiku. My own share is kept to planning, briefs and review of short reports.
- Opus is used for exactly four things: the matching spec, the scoring core (2.4, 3.3), security review gates, and anything Sonnet has failed at twice.
- Largest spend, in order: officer + admin UI build and screenshot iterations, engine tiers 2 and 3, tester rounds.
- Cut order if limits tighten: (1) all stretch items, (2) Urdu / regional data, keeping English + Hindi, (3) admin panel reduced to review queue + audit log + access requests, (4) Tier 3 reduced to the shared-contacts signal only, (5) tester personas reduced to low-literacy officer + hostile user, (6) graph view polish.
- Never cut: the end-to-end Irfan flow, the explanation panel, the audit log, access control and their tests.

## 7. Engineering standards and governance

Created in P0, versioned in git, read by agents before work:

- **AGENT_RULES.md** — stay in role, touch only owned paths, short report format, escalate instead of guessing, no duplicate work, devs never contact testers, never commit to main.
- **PROTOCOLS.md** — task intake and brief format, spec → tests → build, review and merge, bug ticket lifecycle, escalation (worker → lead → Fable), session handoff, hiring / retiring, release and demo checklist.
- **CODEBASE_RULES.md** — repo layout, naming, style, test conventions, branch names, conventional commits, dependency policy (minimal, pinned), how apps share the contract and UI package.
- **DESIGN_RULES.md** — owned by the Design Lead.
- **ROSTER.md, STATE.md, DECISIONS.md** — roles; done / in progress / next / blockers; every decision and assumption with its reason.

Practice: short-lived feature branches, PR-style review by a different agent, main protected and green, lint + type-check + tests in CI on every change, no secrets or data dumps in the repo, validated inputs at API boundaries, structured logging, least privilege.

Document assumptions adopted as working defaults (each logged in DECISIONS.md): three confidence bands with the stated behaviour; tier signals as in the document's examples; junior officers view links in their own cases, confirm / reject needs a higher role; other-jurisdiction links show "a connection exists" plus a request-access action; wrongly confirmed links are undone by removing the edge, recorded in the audit log, and the rejected pair is not auto-linked again (no score feedback loop in the prototype).

## 8. Design approach

The Design Lead is hired in P1 and owns DESIGN_RULES.md, the tokens and the component set, and reviews every UI change from rendered screenshots. It can block a merge.

Direction I will brief (the Design Lead makes and justifies the actual choices):
- Sober, government-appropriate, law-enforcement tool. Restrained palette where colour carries meaning (link strength, warnings, restricted access), not decoration. High contrast, large type, big tap targets.
- Officer app: one primary action per screen, plain-language labels paired with icons, few steps, obvious feedback, undo for mistakes, English and Hindi from the first screen.
- Explanation panel in plain words first ("Same phone number in both cases", "Names sound alike: Mohd. Irfan / Irfan", "Both called the same 2 numbers"), with a plain strength label; the number and tier detail sit behind "more detail".
- Admin panel may be denser but uses the same components and language.
- Banned: blue-to-purple gradients, glassmorphism, neon glows, unstyled component-library defaults, pastel rounded-card landing look, emoji as icons, hero sections and marketing copy, the warm beige + serif default, a generic design-system dump.
- Design feedback from user testing reaches the Design Lead only as QA tickets.

## 9. Test plan

**Developer tests** (dev side, tests written before code):
- Normalization: unit and property tests for phones, names, accounts, vehicles, dates across scripts.
- Matching: a golden set from the data kit with planted true links and planted traps (same common name, different person; shared family phone). Targets: no false link in the high band; recall measured and reported per tier.
- Scoring: band boundaries, reinforcing vs conflicting evidence, score decomposes exactly into the evidence shown.
- Access control: full role × jurisdiction × action matrix as table-driven tests, including "connection exists but details hidden".
- Audit log: every listed event is written; UPDATE and DELETE fail; hash chain verifies.
- Contract tests between apps and API; Playwright smoke test of the Irfan flow; SAME_AS undo leaves original entities untouched.

**Independent user testing** (QA Lead, brand-new tester per run, tester sees only persona + running app + plain-words goal):
- Personas: low-literacy, lightly trained officer (mandatory); average officer; time-pressed senior officer; admin; careless or hostile user probing access control and cross-jurisdiction visibility.
- Each round covers the explanation panel, the audit log and access control from the persona's point of view.
- Testers report what they tried, expected, saw, and where they got stuck. QA Lead converts to tickets. Two rounds minimum; a third if round 2 finds blockers.

## 10. Session plan

State lives in files; any session resumes from a short handoff brief + STATE.md only. Usage is checked at every phase boundary and before each batch of agents.

| Session | Content | Ends with |
|---|---|---|
| S0 (this one) | Plan, then on go-ahead P0 foundation and governance | tag `m0-foundation`, STATE.md checkpoint |
| S1 | P1 specs and contracts, design rules | `m1-specs` |
| S2 | P2 engine vertical slice | `m2-slice` |
| S3 | P3 full engine + backend + security gate | `m3-engine` |
| S4 | P4 officer app | officer app merged |
| S5 | P4 admin panel + design screenshot review | `m4-apps` |
| S6 | P5 testing rounds and fixes | all blocker tickets closed |
| S7 | P6 demo readiness | `v1.0-demo` |

Before a window runs out: finish or park in-flight work, update STATE.md, commit and push, and tell you exactly what to start next. Near a limit nothing large is started.

## 11. Questions only you can answer

1. Rulings on conflicts C1–C3 (kingpin ranking, LLM extraction, manual data add). My defaults stand if you don't object.
2. GitHub: may I create a private repo `tracex` under the logged-in account and push to it, or do you have a repo / org to use?
3. Will the finals demo machine have internet? If not, Bhashini and any hosted LLM are out of the live demo.
4. Do you have Bhashini API credentials, and do you want an LLM extractor shown at all?
5. Demo languages: English + Hindi (Devanagari) is my default, with Urdu-origin names in Roman script. Anything else mandatory?
6. Date of the finals, and any day I should treat as the hard feature freeze.
