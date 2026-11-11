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

The API is at http://localhost:8000 (`/health`), Neo4j Browser at http://localhost:7474.

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
