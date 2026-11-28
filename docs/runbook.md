# Runbook

## Setup from a fresh clone

```
cp .env.example .env
docker compose up --build -d --wait
```

The first build takes a few minutes. When it ends, these are running:

- Officer app: http://localhost:4173 (`OFFICER_PORT`). Sign in as `asha`.
- Admin app: http://localhost:4174 (`ADMIN_PORT`). Sign in as `hari`.
- API: http://localhost:8000 (`API_PORT`), for example `/health`.
- Neo4j Browser: http://localhost:7474 (`NEO4J_HTTP_PORT`).

Passwords for the seeded users are the `TRACEX_SEED_PASSWORD_<NAME>` values in `.env` (dev default `dev-only-seed-<name>`).

How the apps reach the API: each app is built inside Docker with `VITE_API_URL=/api` and served by nginx (`docker/app-nginx.conf`). nginx forwards `/api/...` to `http://api:8000/...`. The browser sees one origin per app, so the API sends and needs no CORS header. Do not open an app on any other origin (for example `vite dev` on another port) without a proxy: sign-in will show "No connection".

Port overrides: set any of `API_PORT`, `OFFICER_PORT`, `ADMIN_PORT`, `POSTGRES_PORT`, `NEO4J_HTTP_PORT`, `NEO4J_BOLT_PORT` in `.env`. To run a second copy side by side, also set `COMPOSE_PROJECT_NAME` and use different ports for all six. On Windows with Git Bash, port 8000 is often busy: use `API_PORT=18000`.

A page refresh signs the user out. This is by design (D64): the refresh token is kept in memory only, never in browser storage.

After a change in `apps/` or `packages/`, rebuild the app images: `docker compose up --build -d --wait officer admin`.

## Seed data

## Demo seed

One command loads the synthetic data-kit cases, runs matching and assigns cases to officers. The users and police areas already exist: the `migrate` service creates them.

```
cp .env.example .env            # once
docker compose up -d --wait api
docker compose run --rm seed
```

Use `API_PORT=18000` in `.env` if port 8000 is busy. The seed is a client of the API: it signs in as the admin `hari`, uploads each case with `POST /uploads`, waits for ingest, starts one matching run, then assigns cases through the four-eyes flow (`hari` proposes, the senior `meena` approves). The API writes every audit row for those two users; the seed never touches the database or the audit log.

- Tier: `small` by default (62 planted and 60 noise cases). For the large set add `--tier demo` to the command, for example `docker compose run --rm seed python -m tracex_api.seed_demo --api-url http://api:8000 --data-kit /data-kit --tier demo`. The kit is generated into a temporary folder; nothing generated is committed.
- Idempotent: a second run prints `already seeded` and changes nothing. If a run stopped half way, it reports a partial seed; run `docker compose down -v` and start again.
- Passwords come from `TRACEX_SEED_PASSWORD_HARI` and `TRACEX_SEED_PASSWORD_MEENA` in `.env` (dev defaults are in `.env.example`).
- It runs only when `TRACEX_ENV` is exactly `development`, `local`, `test` or `demo` (no default: unset means refuse, exit code 2) and `TRACEX_ALLOW_DEV_SECRETS` is `1`. It accepts only `http` and `https` API URLs and does not follow redirects.
- The audit log will show `meena` approving every assignment within seconds. These approvals are made by the seed, not by a real senior's review. Do not read them as one in the demo.
- After it runs, `asha` (Rivergate) sees C-101 as assigned and links to Hillcrest or Lakeside cases as restricted stubs. `meena` sees the review queue. Use `GET /links` as `asha` to see the stubs.

## Run the demo scenario

## Explanation panel, audit log and access control

## Nightly audit verify

Schedule this once a night (cron, a systemd timer, or a CI schedule). It needs no new service:

```
docker compose run --rm --no-deps api python -m tracex_api.verify_audit
```

It walks the whole audit chain, checks it against the anchor file, and checks that every APPROVED pending change has a matching `CHANGE_APPROVED` audit row (same decider, same change hash). It prints one JSON line such as `{"result": "OK", ...}` and exits 0. On any problem the result is `BROKEN`, the problem is logged at error level, and the exit code is 1: alert on a non-zero exit. A BROKEN chain also makes the running API answer 503 on every route except `/health`, `/ready` and `POST /audit/verify` until a verify passes. While it is BROKEN, `POST /auth/login` is also 503, so only a senior who already holds a token can call `POST /audit/verify`; otherwise recovery waits for the 60-second check or a restart.

If the anchor file is lost (the `audit-anchor` volume was removed) the log counts as BROKEN once it has more than one row. Restore the volume from backup. Do not delete the file to clear the error.

If `/ready` stays 503 with the alert "engine store is empty but N links are live", the graph store was lost. Restore it or replay the batches, then restart the API. The API does not withdraw any link in that state and does not recover on its own: `/ready` stays 503 until you restart it. While it is in that state the routes still show the links Postgres holds.

The API refuses to start on the `dev-only` placeholder secrets unless `TRACEX_ALLOW_DEV_SECRETS=1`. `.env.example` sets it for local development. `migrate` and `seed` refuse the `dev-only` database and user passwords without it too. Never set it on a shared or real deployment. The API logs a WARNING at startup when the flag lets dev-only values through; if you see it on a real deployment, remove the flag.

## Troubleshooting

## Release
