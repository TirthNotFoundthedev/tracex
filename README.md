# TraceX

TraceX is a cross-case entity-resolution tool for police investigators. It links people, phones, accounts and other entities that appear in more than one case, and shows the evidence behind every link.

## Prerequisites

- Docker with Compose v2
- [uv](https://docs.astral.sh/uv/) (installs Python 3.12 on demand)
- Node.js 22 and npm 10+

## Run

```
cp .env.example .env
docker compose up --build
```

This starts the API and both apps:

| What            | URL (default)         | Port variable in `.env` |
| --------------- | --------------------- | ----------------------- |
| Officer app     | http://localhost:4173 | `OFFICER_PORT`          |
| Admin app       | http://localhost:4174 | `ADMIN_PORT`            |
| API (`/health`) | http://localhost:8000 | `API_PORT`              |
| Neo4j Browser   | http://localhost:7474 | `NEO4J_HTTP_PORT`       |

Each app is served by its own small nginx container, which also forwards `/api` to the API. The browser talks to one address only, so the API needs no CORS setting. Sign in with a seeded user: the officer app with `asha`, the admin app with `hari`. Passwords are `TRACEX_SEED_PASSWORD_<NAME>` in `.env` (dev default `dev-only-seed-<name>`). Run the demo seed (see `docs/runbook.md`) to add cases.

If a port is busy on your machine, change it in `.env` before `docker compose up`.

## Test

Backend:

```
cd backend
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
```

Frontend (from the repo root):

```
npm ci
npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
```

## Layout

See `CODEBASE_RULES.md`. Operations notes are in `docs/runbook.md`.
