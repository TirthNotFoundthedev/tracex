"""Prepare the database: create the two login roles, run the migrations, start the audit chain.

    python -m tracex_api.migrate

Needs `DATABASE_ADMIN_URL` (a role with CREATEROLE, the database owner in compose),
`TRACEX_MIGRATOR_DB_PASSWORD` and `TRACEX_API_DB_PASSWORD`. Safe to run again. The seed
(`python -m tracex_api.seed`) runs after it.
"""

import os
import sys

import psycopg.conninfo
from psycopg import sql

from tracex_api import audit
from tracex_api.db import API_ROLE, MIGRATOR_ROLE, bootstrap_roles, connect, migrate, need, one


def role_url(admin_url: str, role: str, password: str) -> str:
    parts = psycopg.conninfo.conninfo_to_dict(admin_url)
    parts["user"], parts["password"] = role, password
    return psycopg.conninfo.make_conninfo("", **parts)


def start_chain(migrator_url: str) -> bool:
    """Write AUDIT_CHAIN_STARTED once, when the log is empty."""
    with connect(migrator_url) as conn:
        if one(conn, "SELECT 1 AS x FROM audit_log LIMIT 1") is not None:
            return False
        audit.append(
            conn,
            audit.AuditEvent("AUDIT_CHAIN_STARTED", audit.SYSTEM, detail={"schema_version": 1}),
        )
        conn.commit()
    return True


def main() -> int:
    needed = ("DATABASE_ADMIN_URL", "TRACEX_MIGRATOR_DB_PASSWORD", "TRACEX_API_DB_PASSWORD")
    missing = [name for name in needed if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"missing environment variables: {', '.join(missing)}")
    admin_url = os.environ["DATABASE_ADMIN_URL"]
    bootstrap_roles(
        admin_url, os.environ["TRACEX_MIGRATOR_DB_PASSWORD"], os.environ["TRACEX_API_DB_PASSWORD"]
    )
    with connect(admin_url, autocommit=True) as conn:
        name = need(one(conn, "SELECT current_database() AS name"))
        conn.execute(
            sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                sql.Identifier(name["name"]), sql.Identifier(MIGRATOR_ROLE)
            )
        )
    migrator_url = role_url(admin_url, MIGRATOR_ROLE, os.environ["TRACEX_MIGRATOR_DB_PASSWORD"])
    applied = migrate(migrator_url)
    started = start_chain(migrator_url)
    sys.stdout.write(
        f"roles ready ({MIGRATOR_ROLE}, {API_ROLE}); migrations applied: {len(applied)}; "
        f"chain started: {started}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
