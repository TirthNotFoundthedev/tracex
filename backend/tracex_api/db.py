"""Postgres access: connections, role bootstrap and the migration runner.

The API connects as `tracex_api`. Migrations run as `tracex_migrator`, which owns every object;
nothing else uses that role. SQL is plain psycopg with `dict_row`, parameters always bound.
"""

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any, LiteralString

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
MIGRATOR_ROLE = "tracex_migrator"
API_ROLE = "tracex_api"

type Row = dict[str, Any]
type Conn = psycopg.Connection[Row]


def connect(url: str, autocommit: bool = False) -> Conn:
    return psycopg.connect(url, row_factory=dict_row, autocommit=autocommit)


def dyn(text: str) -> sql.SQL:
    """A query assembled from constant fragments (never from request values; those are bound)."""
    return sql.SQL(text)


def need[T](value: T | None) -> T:
    """A value the query must have returned (an INSERT ... RETURNING, a row just written)."""
    if value is None:
        raise RuntimeError("expected a database row")
    return value


def one(conn: Conn, query: LiteralString | sql.SQL, params: Sequence[Any] = ()) -> Row | None:
    return conn.execute(query, params).fetchone()


def many(conn: Conn, query: LiteralString | sql.SQL, params: Sequence[Any] = ()) -> list[Row]:
    return conn.execute(query, params).fetchall()


def bootstrap_roles(admin_url: str, migrator_password: str, api_password: str) -> None:
    """Create the two login roles if they are missing and set their passwords.

    Needs a role with CREATEROLE (the database superuser in compose and in tests)."""
    with connect(admin_url, autocommit=True) as conn:
        for role, password in ((MIGRATOR_ROLE, migrator_password), (API_ROLE, api_password)):
            exists = one(conn, "SELECT 1 AS x FROM pg_roles WHERE rolname = %s", (role,))
            verb = "ALTER" if exists else "CREATE"
            conn.execute(
                sql.SQL("{} ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(
                    sql.SQL(verb), sql.Identifier(role), sql.Literal(password)
                )
            )


def migrate(migrator_url: str) -> list[str]:
    """Apply every migration file not yet recorded, in name order. Returns the names applied."""
    applied: list[str] = []
    with connect(migrator_url, autocommit=True) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        done = {r["name"] for r in many(conn, "SELECT name FROM schema_migrations")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in done:
                continue
            with conn.transaction():
                conn.execute(dyn(path.read_text(encoding="utf-8")))
                conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
            applied.append(path.name)
            logger.info("migration applied", extra={"migration": path.name})
    return applied
