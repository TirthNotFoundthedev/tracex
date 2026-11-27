"""The nightly audit verify (PR #30 re-review: nightly job and N1)."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.api.conftest import Api
from tests.api.test_audit_anchor_gate import break_anchor, busy
from tests.api.test_four_eyes_db import HASH, propose, user_id
from tracex_api import audit
from tracex_api.verify_audit import check_approved_changes, main, run_checks


def approve_through_the_api(api: Api) -> str:
    """isha is disabled the proper way: hari proposes, meena approves."""
    isha = str(user_id(api, "isha"))
    proposed = api.post(
        "hari", "/pending-changes", {"kind": "USER_DISABLE", "subject_user_id": isha}
    )
    assert proposed.status_code == 201, proposed.text
    change = proposed.json()
    done = api.post(
        "meena",
        f"/pending-changes/{change['change_id']}/approve",
        {"change_hash": change["change_hash"]},
    )
    assert done.status_code == 200, done.text
    return str(change["change_id"])


def approve_in_the_database_only(api: Api, decider: str = "meena", **set_hash: bytes) -> uuid.UUID:
    """The N1 residual: tracex_api can set APPROVED itself; no CHANGE_APPROVED row is written."""
    hari, isha = user_id(api, "hari"), user_id(api, "isha")
    with api.api_role() as conn:
        change = propose(conn, hari, isha)
        conn.execute(
            "UPDATE pending_changes SET state = 'APPROVED', decider_id = %s, decided_at = %s, "
            "approved_hash = %s WHERE id = %s",
            (user_id(api, decider), datetime.now(UTC), set_hash.get("hash", HASH), change),
        )
        conn.commit()
    return change


def test_a_clean_log_with_a_properly_approved_change_passes(api: Api) -> None:
    busy(api)
    approve_through_the_api(api)
    with api.owner() as conn:
        report = run_checks(conn, api.settings.audit_anchor_path)
    assert report.ok and report.mismatches == [] and report.first_bad_seq is None


def test_n1_an_approval_with_no_audit_row_is_reported(api: Api) -> None:
    approve_through_the_api(api)
    forged = approve_in_the_database_only(api)
    with api.owner() as conn:
        problems = check_approved_changes(conn)
        report = run_checks(conn, api.settings.audit_anchor_path)
    assert len(problems) == 1 and str(forged) in problems[0] and "no CHANGE_APPROVED" in problems[0]
    assert report.chain_ok and not report.ok


def test_n1_a_different_decider_or_hash_in_the_audit_row_is_reported(api: Api) -> None:
    change = approve_through_the_api(api)
    with api.superuser() as conn:
        conn.execute("ALTER TABLE pending_changes DISABLE TRIGGER ALL")
        conn.execute(
            "UPDATE pending_changes SET decider_id = (SELECT id FROM users "
            "WHERE username = 'deepak')"
            " WHERE id = %s",
            (uuid.UUID(change),),
        )
        conn.execute("ALTER TABLE pending_changes ENABLE TRIGGER ALL")
    with api.owner() as conn:
        [problem] = check_approved_changes(conn)
    assert change in problem and "decider" in problem
    with api.superuser() as conn:
        conn.execute("ALTER TABLE pending_changes DISABLE TRIGGER ALL")
        conn.execute(
            "UPDATE pending_changes SET decider_id = (SELECT id FROM users WHERE username = "
            "'meena'), change_hash = %s WHERE id = %s",
            (HASH, uuid.UUID(change)),
        )
        conn.execute("ALTER TABLE pending_changes ENABLE TRIGGER ALL")
    with api.owner() as conn:
        [problem] = check_approved_changes(conn)
    assert change in problem and "change_hash" in problem


def test_a_broken_chain_is_reported_with_its_first_bad_row(api: Api) -> None:
    busy(api)
    with api.superuser() as conn:
        conn.execute("ALTER TABLE audit_log DISABLE TRIGGER ALL")
        conn.execute("UPDATE audit_log SET outcome = 'FAILED' WHERE seq = 3")
        conn.execute("ALTER TABLE audit_log ENABLE TRIGGER ALL")
    with api.owner() as conn:
        report = run_checks(conn, api.settings.audit_anchor_path)
    assert not report.chain_ok and report.first_bad_seq == 3 and not report.ok


def command(api: Api, anchor: Path | None = None) -> list[str]:
    return [
        "--database-url",
        api.settings.database_url,
        "--anchor-path",
        str(anchor or api.settings.audit_anchor_path),
    ]


def test_the_command_exits_zero_prints_json_and_writes_a_system_audit_row(
    api: Api, capsys: pytest.CaptureFixture[str]
) -> None:
    busy(api)
    approve_through_the_api(api)
    assert main(command(api)) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["result"] == "OK" and out["mismatches"] == []
    [row] = api.audit_rows("AUDIT_VERIFY_RUN")
    assert row["actor_kind"] == "SYSTEM" and row["detail"]["result"] == "OK"
    with api.owner() as conn:
        assert audit.verify(conn, api.settings.audit_anchor_path) == (True, None)


@pytest.mark.parametrize("problem", ["anchor", "approval"])
def test_the_command_exits_one_on_any_problem(
    api: Api, problem: str, capsys: pytest.CaptureFixture[str]
) -> None:
    busy(api)
    if problem == "anchor":
        break_anchor(api, "missing")
    else:
        approve_in_the_database_only(api)
    assert main(command(api)) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["result"] == "BROKEN"
    assert out["mismatches"] if problem == "approval" else out["first_bad_seq"] == 1
