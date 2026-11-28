# Tester round 1: run sheet

For the QA Lead and Fable only. Never give this file to a tester.

- Main SHA the stack runs: to be filled at round start (fixes TIR-91 to TIR-94 merge first).
- Compose project name: `tracex-qa`
- Seed: demo seed, small tier (122 cases), from a clean state (`down -v` first).

## Ports (this machine)

| Part              | Port                  |
| ----------------- | --------------------- |
| API               | 18000                 |
| Postgres          | 5432 (default)        |
| Neo4j HTTP / Bolt | 7474 / 7687 (default) |
| Officer app       | 4173                  |
| Admin app         | 4174                  |

Port 8000 is taken here, so `.env` sets `API_PORT=18000`. The other ports are the defaults and were free when checked. `.env` is ignored by git.

## URLs

- Officer app: http://localhost:4173/
- Admin app: http://localhost:4174/
- API health: http://localhost:18000/health

## Logins (synthetic; password is `dev-only-seed-<user>`)

| Persona                     | App                 | User     |
| --------------------------- | ------------------- | -------- |
| Low-literacy junior officer | Officer             | `asha`   |
| Average investigator        | Officer             | `bharat` |
| Time-pressed senior officer | Admin               | `deepak` |
| Admin                       | Admin               | `hari`   |
| Careless or hostile user    | Officer, then Admin | `jatin`  |

Other seeded users for checks: `charu` (supervisor, opens the admin app), `meena` (senior).

## How the apps are served

Compose serves both apps (nginx containers) and forwards `/api` to the API. No extra server is needed. Details are in `docs/runbook.md`.

## Start from clean

```
cp .env.example .env   # then set API_PORT=18000 and COMPOSE_PROJECT_NAME=tracex-qa
docker compose down -v
docker compose up --build -d --wait
docker compose run --rm seed
```

A clean restart takes about 4 minutes (measured: down 11 s, up with build 79 s, seed 129 s, before the apps were added to compose).

## Stop

```
docker compose down -v   # with COMPOSE_PROJECT_NAME=tracex-qa; removes only this project
```

Do not touch containers of other projects.

## After the round

Tester actions change the data (decisions, requests, new users). Restart from clean before another round.
