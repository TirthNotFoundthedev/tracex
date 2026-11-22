"""Seed the synthetic jurisdictions and users (docs/specs/data-kit.md section 9).

Runs with the migrator or admin connection, never the API role: users, coverage and case
assignments have no direct INSERT for `tracex_api`. Passwords come from the environment
(`TRACEX_SEED_PASSWORD_<USERNAME>`); none is committed. Case assignments are applied by
`assign_cases` once the cases exist (they are created by upload).

    python -m tracex_api.seed [--seed-dir data-kit/seed]     (needs DATABASE_ADMIN_URL)
"""

import argparse
import csv
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tracex_api.db import Conn, connect, many, need, one
from tracex_api.security import hash_password


def load_seed(seed_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[tuple[str, str]]]:
    jurisdictions = json.loads((seed_dir / "jurisdictions.json").read_text(encoding="utf-8"))
    users = json.loads((seed_dir / "users.json").read_text(encoding="utf-8"))["users"]
    with (seed_dir / "case_assignments.csv").open(encoding="utf-8", newline="") as handle:
        extra = [(r["username"], r["case_id"]) for r in csv.DictReader(handle)]
    named = [(u["username"], case) for u in users for case in u.get("assigned_cases", [])]
    return jurisdictions, users, named + extra


def seed_jurisdictions(conn: Conn, jurisdictions: Mapping[str, Any]) -> None:
    for state in jurisdictions["states"]:
        row = one(
            conn,
            "INSERT INTO states (name) VALUES (%s) ON CONFLICT (name) DO UPDATE "
            "SET name = EXCLUDED.name RETURNING id",
            (state["name"],),
        )
        row = need(row)
        for district in state["districts"]:
            conn.execute(
                "INSERT INTO districts (state_id, name, code) VALUES (%s, %s, %s) "
                "ON CONFLICT (state_id, name) DO NOTHING",
                (row["id"], district["name"], district["id_digit"]),
            )


def seed_users(conn: Conn, users: list[dict[str, Any]], passwords: Mapping[str, str]) -> list[str]:
    """Insert users and their coverage; returns the usernames created."""
    created = []
    for spec in users:
        if one(conn, "SELECT 1 AS x FROM users WHERE username = %s", (spec["username"],)):
            continue
        district_id = None
        if spec["role"] not in ("SENIOR", "ADMIN"):
            district = one(
                conn, "SELECT id FROM districts WHERE name = %s", (spec["districts"][0],)
            )
            district = need(district)
            district_id = district["id"]
        password = passwords.get(spec["username"])
        user = one(
            conn,
            "INSERT INTO users (username, display_name, role, district_id, active, password_hash) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (
                spec["username"],
                spec["display_name"],
                spec["role"],
                district_id,
                spec["active"],
                hash_password(password) if password else None,
            ),
        )
        user = need(user)
        if spec["role"] == "SENIOR":
            if spec.get("all_states"):
                conn.execute(
                    "INSERT INTO user_coverage (user_id, all_states) VALUES (%s, true)",
                    (user["id"],),
                )
            for state in spec.get("states", []):
                conn.execute(
                    "INSERT INTO user_coverage (user_id, state_id) "
                    "SELECT %s, id FROM states WHERE name = %s",
                    (user["id"], state),
                )
            for district in spec.get("districts", []):
                conn.execute(
                    "INSERT INTO user_coverage (user_id, district_id) "
                    "SELECT %s, id FROM districts WHERE name = %s",
                    (user["id"], district),
                )
        created.append(spec["username"])
    return created


def assign_cases(conn: Conn, pairs: list[tuple[str, str]]) -> int:
    """Assign users to cases that exist (matched by case number); others are skipped."""
    count = 0
    for username, case_number in pairs:
        row = one(
            conn,
            "SELECT c.id AS case_id, u.id AS user_id FROM cases c, users u "
            "WHERE c.case_number = %s AND u.username = %s "
            "ORDER BY (c.district_id = u.district_id) DESC LIMIT 1",
            (case_number, username),
        )
        if row is None:
            continue
        conn.execute(
            "INSERT INTO case_assignments (case_id, user_id) VALUES (%s, %s) "
            "ON CONFLICT (case_id, user_id) DO NOTHING",
            (row["case_id"], row["user_id"]),
        )
        count += 1
    return count


def passwords_from_env(users: list[dict[str, Any]], env: Mapping[str, str]) -> dict[str, str]:
    found = {}
    for spec in users:
        value = env.get(spec["password_env"], "")
        if not value:
            raise SystemExit(f"{spec['password_env']} is not set")
        found[spec["username"]] = value
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the synthetic jurisdictions and users.")
    parser.add_argument("--seed-dir", type=Path, default=Path("data-kit/seed"))
    args = parser.parse_args(argv)
    jurisdictions, users, pairs = load_seed(args.seed_dir)
    admin_url = os.environ.get("DATABASE_ADMIN_URL")
    if not admin_url:
        raise SystemExit("DATABASE_ADMIN_URL is required")
    passwords = passwords_from_env(users, os.environ)
    with connect(admin_url) as conn:
        seed_jurisdictions(conn, jurisdictions)
        seed_users(conn, users, passwords)
        assign_cases(conn, pairs)
        conn.commit()
        total = many(conn, "SELECT count(*) AS n FROM users")[0]["n"]
    sys.stdout.write(f"seeded; {total} users\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
