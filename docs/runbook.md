# Runbook

## Setup from a fresh clone

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

## Troubleshooting

## Release
