# Tester round 1: run sheet

For the QA Lead and Fable only. Never give this file to a tester.

- Main SHA the stack runs: to be filled at round start (fixes TIR-91 to TIR-94 merge first).
- Compose project name: `tracex-qa`
- Seed: demo seed, small tier (122 cases), from a clean state (`down -v` first).

## Ports (this machine)

| Part | Port |
|---|---|
| API | 18000 |
| Postgres | 15432 |
| Neo4j HTTP / Bolt | 17474 / 17687 |
| Officer app | 24173 |
| Admin app | 24174 |

Port 8000 is taken here, so `.env` sets `API_PORT=18000` and the other ports above. `.env` is ignored by git.

## URLs

- Officer app: http://localhost:24173/
- Admin app: http://localhost:24174/
- API health: http://localhost:18000/health

## Logins (synthetic; password is `dev-only-seed-<user>`)

| Persona | App | User |
|---|---|---|
| Low-literacy junior officer | Officer | `asha` |
| Average investigator | Officer | `bharat` |
| Time-pressed senior officer | Admin | `deepak` |
| Admin | Admin | `hari` |
| Careless or hostile user | Officer, then Admin | `jatin` |

Other seeded users for checks: `charu` (supervisor, opens the admin app), `meena` (senior).

## How the apps are served

The API sends no cross-origin headers, so a browser app on another port cannot call it. The apps are built with `VITE_API_URL=/api` and served by a small static server that sends `/api/*` to the API. The server file is `serve.mjs` in a folder outside the repo (`~/.tracex-qa/`), not part of this PR. Build step (Git Bash needs `MSYS_NO_PATHCONV=1`, or `/api` turns into a file path):

```
npm ci
cd apps/officer && VITE_API_URL=/api npx vite build   # copy dist to ~/.tracex-qa/officer
cd apps/admin   && VITE_API_URL=/api npx vite build   # copy dist to ~/.tracex-qa/admin
node serve.mjs officer 24173 18000
node serve.mjs admin 24174 18000
```

## Start from clean

```
cp .env.example .env   # then set the ports above and COMPOSE_PROJECT_NAME=tracex-qa
docker compose down -v
docker compose up -d --build --wait api
docker compose run --rm seed
```

## Stop

```
docker compose down -v            # with COMPOSE_PROJECT_NAME=tracex-qa; removes only this project
# stop the two `node serve.mjs` processes (ports 24173 and 24174)
```

Do not touch containers of other projects.

## After the round

Tester actions change the data (decisions, requests, new users). Restart from clean before another round.
