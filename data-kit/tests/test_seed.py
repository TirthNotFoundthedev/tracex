"""G-14: seeded users and case assignments; CLI."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from tests.conftest import KIT_ROOT

ROLES = {"JUNIOR", "INVESTIGATOR", "SUPERVISOR", "SENIOR", "ADMIN"}


def _users() -> list[dict[str, Any]]:
    data = json.loads((KIT_ROOT / "seed" / "users.json").read_text("utf-8"))
    users: list[dict[str, Any]] = data["users"]
    return users


def test_users_match_the_access_spec_seed() -> None:
    users = {u["username"]: u for u in _users()}
    assert set(users) == {
        "asha", "isha", "jatin", "kiran", "omkar", "bharat", "esha", "gita",
        "charu", "farid", "lata", "deepak", "meena", "hari",
    }  # fmt: skip
    assert {u["role"] for u in users.values()} <= ROLES
    assert users["asha"]["assigned_cases"] == ["C-101"]
    assert users["bharat"]["assigned_cases"] == ["C-101", "C-102"]
    assert users["omkar"]["active"] is False
    assert sum(1 for u in users.values() if not u["active"]) == 1
    assert users["deepak"]["states"] == ["Northvale"] and not users["deepak"]["all_states"]
    assert users["meena"]["all_states"] is True
    assert [u["username"] for u in users.values() if u["all_states"]] == ["meena"]
    hari = users["hari"]
    assert hari["role"] == "ADMIN" and hari["districts"] == [] and hari["states"] == []


def test_users_hold_no_password_and_unique_password_env() -> None:
    raw = (KIT_ROOT / "seed" / "users.json").read_text("utf-8")
    assert "password\"" not in raw
    envs = [u["password_env"] for u in _users()]
    assert len(envs) == len(set(envs))
    for user in _users():
        assert user["password_env"] == f"TRACEX_SEED_PASSWORD_{user['username'].upper()}"


def test_assignments_reference_existing_cases(small_dir: Path) -> None:
    existing = {p.name for p in (small_dir / "batches").glob("*/cases/*")}
    with (KIT_ROOT / "seed" / "case_assignments.csv").open(encoding="utf-8", newline="") as h:
        rows = list(csv.DictReader(h))
    assert rows
    assert {r["case_id"] for r in rows} <= existing
    users = {u["username"]: u for u in _users()}
    for user in users.values():
        for case_id in user["assigned_cases"]:
            assert {"username": user["username"], "case_id": case_id} in rows
    noise_by_user: dict[str, int] = {}
    for row in rows:
        if int(row["case_id"][3:]) >= 50:
            noise_by_user[row["username"]] = noise_by_user.get(row["username"], 0) + 1
    active = {n for n, u in users.items() if u["active"] and u["role"] != "ADMIN"}
    for name in active:
        user = users[name]
        if user["role"] == "SENIOR":
            continue
        assert noise_by_user.get(name) == 3, name


def test_seed_files_are_reproducible_from_the_generator() -> None:
    from datakit.seed import case_assignments_csv

    expected = case_assignments_csv(20260401)
    assert (KIT_ROOT / "seed" / "case_assignments.csv").read_text("utf-8") == expected


def test_cli_generates_the_small_tier(tmp_path: Path) -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "datakit", "generate", "--tier", "small", "--out", str(tmp_path)],
        cwd=KIT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "manifest.json").is_file()
