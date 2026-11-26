# Runbook

## Setup from a fresh clone

## Seed data

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
