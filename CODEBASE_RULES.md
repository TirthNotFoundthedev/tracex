# CODEBASE_RULES

Owner: Fable with the leads. Enforced by CI and review.

## Layout

```
backend/
  tracex_engine/     ingest, extract, normalize, case graphs, matching, scoring, unified graph
  tracex_api/        FastAPI app, auth, access control, audit, routers
  tests/             mirrors the package layout
apps/officer/        officer app (React + TS + Vite)
apps/admin/          admin panel (React + TS + Vite)
packages/ui/         design tokens, shared components, i18n strings (en, hi)
contracts/           openapi.yaml and JSON schemas; the only interface between apps and API
data-kit/            synthetic data generator and its ground-truth output
docs/                architecture.md, runbook.md, specs/
qa/tickets/          bug tickets (QA Lead only)
.github/workflows/   CI
```

Ownership of each path is on the role cards in ROSTER.md.

## Sharing between apps
- Apps never import from each other or from `backend/`. They share only `packages/ui` and types generated from `contracts/openapi.yaml`.
- The contract changes first, in its own PR, reviewed by the Backend Lead and the affected app lead. Code follows.
- The engine does not import from `tracex_api`. The API imports the engine.

## Python (backend, data-kit)
- Python 3.12, managed with uv; dependencies pinned in `uv.lock`.
- Ruff for lint and format, mypy in strict mode. Full type hints.
- Modules do one thing. Pure functions for normalization, comparison and scoring; I/O at the edges.
- Errors are handled at boundaries (API, file parsing, database). No bare `except`.
- Structured logging (JSON), never `print`. Never log raw personal fields beyond entity IDs.
- No dead code, no commented-out code, no TODO without a ticket number.

## TypeScript (apps, packages/ui)
- Strict TypeScript, ESLint, Prettier. Function components.
- All user-facing text comes from the i18n files, in English and Hindi. No hard-coded strings in components.
- Colours, sizes and spacing come from tokens in `packages/ui`. No raw hex values or pixel sizes in app code.
- Access rules are enforced by the API. The UI may hide things, but never relies on hiding for security.

## Tests
- Backend: pytest. Unit tests beside the behaviour they cover; integration tests under `backend/tests/integration` using the compose services.
- Frontend: Vitest for components and logic, Playwright for end-to-end flows.
- Test names say the behaviour: `test_same_phone_in_two_cases_links_in_high_band`.
- Matching, scoring and access control use table-driven tests. Test data is synthetic and generated or hand-written in the test, never copied from anywhere real.

## Git
- Branches: `feat/<area>-<short>`, `fix/<ticket>-<short>`, `chore/<short>`, `docs/<short>`. Short-lived.
- Conventional commits: `feat(engine): add tier 1 exact matcher`. Small, focused, imperative.
- No direct commits to `main`. PR, review by another agent, green CI, squash merge by the Release Manager.
- Never commit: secrets, `.env`, generated data dumps, build output, database volumes.

## Dependencies
- Add one only when the spec needs it and the standard library or an existing dependency cannot do it. Name it and the reason in the PR.
- Pinned versions. Permissive licences only. Nothing that needs a paid service to run the demo.

## Non-negotiable behaviours
- Entities are never merged or overwritten. Links are SAME_AS edges with score and evidence attached.
- Every entity, edge and piece of evidence keeps provenance: case, source document, line.
- The audit log is append-only. No code path updates or deletes audit rows.
- Every API endpoint that returns case data passes through the access-control check.
