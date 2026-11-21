"""Four-eyes enforced by Postgres, probed as `tracex_api` (security review PR #30, item 3)."""

import uuid
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest
from psycopg.types.json import Jsonb

from tests.api.conftest import Api
from tracex_api.db import Conn, need, one

HASH = bytes(range(32))


def user_id(api: Api, username: str) -> uuid.UUID:
    with api.owner() as conn:
        row = need(one(conn, "SELECT id FROM users WHERE username = %s", (username,)))
    value: uuid.UUID = row["id"]
    return value


def propose(conn: Conn, proposer: uuid.UUID, subject: uuid.UUID, **extra: Any) -> uuid.UUID:
    columns = {
        "kind": "USER_ROLE",
        "subject_user_id": subject,
        "new_value": Jsonb({"role": "SUPERVISOR"}),
        "proposer_id": proposer,
        "change_hash": HASH,
        "state": "PENDING",
        "proposed_at": datetime.now(UTC),
        **extra,
    }
    names = ", ".join(columns)
    marks = ", ".join(["%s"] * len(columns))
    row = need(
        one(
            conn,
            f"INSERT INTO pending_changes ({names}) VALUES ({marks}) RETURNING id",  # noqa: S608
            tuple(columns.values()),
        )
    )
    conn.commit()
    value: uuid.UUID = row["id"]
    return value


def test_tracex_api_cannot_insert_an_already_approved_change(api: Api) -> None:
    hari, meena, isha = (user_id(api, n) for n in ("hari", "meena", "isha"))
    with api.api_role() as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            propose(
                conn,
                hari,
                isha,
                state="APPROVED",
                decider_id=meena,
                decided_at=datetime.now(UTC),
                approved_hash=HASH,
            )
        conn.rollback()
        with pytest.raises(psycopg.errors.CheckViolation):
            propose(conn, hari, isha, decider_id=meena)
        conn.rollback()
    with api.owner() as conn:
        assert one(conn, "SELECT 1 AS x FROM pending_changes") is None


def test_apply_change_refuses_a_change_nobody_approved(api: Api) -> None:
    hari, isha = user_id(api, "hari"), user_id(api, "isha")
    with api.api_role() as conn:
        change = propose(conn, hari, isha)
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("SELECT apply_change(%s)", (change,))
        conn.rollback()
    with api.owner() as conn:
        assert need(one(conn, "SELECT role FROM users WHERE id = %s", (isha,)))["role"] == "JUNIOR"


@pytest.mark.parametrize(
    ("decider", "approved_hash"),
    [
        ("hari", HASH),
        ("isha", HASH),
        ("meena", bytes(32)),
    ],
    ids=["proposer-is-not-a-senior", "decider-is-a-junior", "hash-differs-from-proposal"],
)
def test_tracex_api_cannot_approve_without_a_distinct_senior_and_the_proposed_hash(
    api: Api, decider: str, approved_hash: bytes
) -> None:
    hari, isha = user_id(api, "hari"), user_id(api, "isha")
    with api.api_role() as conn:
        change = propose(conn, hari, isha)
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "UPDATE pending_changes SET state = 'APPROVED', decider_id = %s, "
                "decided_at = %s, approved_hash = %s WHERE id = %s",
                (user_id(api, decider), datetime.now(UTC), approved_hash, change),
            )
        conn.rollback()
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("SELECT apply_change(%s)", (change,))
        conn.rollback()


def test_a_valid_approval_applies_and_a_decided_change_cannot_be_flipped(api: Api) -> None:
    hari, meena, isha = (user_id(api, n) for n in ("hari", "meena", "isha"))
    with api.api_role() as conn:
        change = propose(conn, hari, isha)
        conn.execute(
            "UPDATE pending_changes SET state = 'APPROVED', decider_id = %s, decided_at = %s, "
            "approved_hash = %s WHERE id = %s",
            (meena, datetime.now(UTC), HASH, change),
        )
        conn.execute("SELECT apply_change(%s)", (change,))
        conn.commit()
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "UPDATE pending_changes SET state = 'DENIED', approved_hash = NULL WHERE id = %s",
                (change,),
            )
        conn.rollback()
    with api.owner() as conn:
        assert need(one(conn, "SELECT role FROM users WHERE id = %s", (isha,)))["role"] == (
            "SUPERVISOR"
        )
