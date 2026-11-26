"""The audit log writer, the hash chain, verification and the anchor file.

Spec: docs/specs/api-audit-log.md sections 2 to 5. `append` is the only function in the API that
writes `audit_log` (W5); nothing updates or deletes a row. It runs last before commit under a
transaction-level advisory lock, so `seq` is contiguous and the chain has no fork.
"""

import hashlib
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from tracex_api.audit_events import (
    CASE_KEYS,
    ENTITY_KEYS,
    EVENTS,
    GRANT_KEYS,
    LINK_KEYS,
    REQUEST_KEYS,
    STUB_KEYS,
)
from tracex_api.db import Conn, Row, many, need, one

logger = logging.getLogger(__name__)

ZERO_HASH = bytes(32)
LOCK_KEY = 7_204_001  # pg_advisory_xact_lock key shared by every append
HASHED_COLUMNS = (
    "seq",
    "event_id",
    "occurred_at",
    "event_type",
    "outcome",
    "actor_kind",
    "actor_user_id",
    "actor_role",
    "actor_district_id",
    "reason_code",
    "refs",
    "target_type",
    "target_id",
    "resolved_target",
    "detail",
    "session_id",
    "request_id",
    "client_ip",
    "row_nonce",
    "prev_hash",
)


class AuditError(Exception):
    """The row was refused (unknown event or key, `refs` not covering the case-bearing keys)."""


@dataclass(frozen=True)
class Actor:
    kind: str  # USER, SYSTEM, ANONYMOUS
    user_id: str | None = None
    role: str | None = None
    district_id: str | None = None


SYSTEM = Actor("SYSTEM")
ANONYMOUS = Actor("ANONYMOUS")


@dataclass
class AuditEvent:
    event_type: str
    actor: Actor
    outcome: str = "SUCCESS"
    reason_code: str | None = None
    refs: list[dict[str, str]] = field(default_factory=list)
    target_type: str | None = None
    target_id: str | None = None
    resolved_target: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    request_id: str | None = None
    client_ip: str | None = None


def _canon_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(value, uuid.UUID):
        return str(value).lower()
    if isinstance(value, bytes | memoryview):
        return bytes(value).hex()
    if value is None or isinstance(value, bool | int | float | str | list | dict):
        return value
    return str(value)


def canonical(columns: dict[str, Any]) -> bytes:
    """The hashed form of a row: JSON, sorted keys, no whitespace, UTF-8 (spec section 4)."""
    body = {name: _canon_value(columns[name]) for name in HASHED_COLUMNS}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def row_hash(prev_hash: bytes, columns: dict[str, Any]) -> bytes:
    return hashlib.sha256(prev_hash + canonical(columns)).digest()


def cases_revealed(conn: Conn, event: AuditEvent) -> set[str]:
    """Every case an event's ids reveal: what `refs` must cover (W7)."""
    cases: set[str] = set()

    def ids(key: str) -> list[str]:
        value = event.detail.get(key)
        if value is None:
            return []
        return [str(v) for v in (value if isinstance(value, list) else [value])]

    def uuids(values: list[str]) -> list[uuid.UUID]:
        found = []
        for v in values:
            try:
                found.append(uuid.UUID(v))
            except ValueError:
                continue
        return found

    case_ids = [v for k in CASE_KEYS for v in ids(k)]
    entity_ids = [v for k in ENTITY_KEYS for v in ids(k)]
    link_ids = [v for k in LINK_KEYS for v in ids(k)]
    stub_ids = [v for k in STUB_KEYS for v in ids(k)]
    request_ids = [v for k in REQUEST_KEYS for v in ids(k)]
    grant_ids = [v for k in GRANT_KEYS for v in ids(k)]
    target = event.target_id or ""
    kind = event.target_type
    if kind == "CASE":
        case_ids.append(target)
    elif kind == "ENTITY":
        entity_ids.append(target)
    elif kind == "LINK":
        link_ids.append(target)
    elif kind == "STUB":
        stub_ids.append(target)
    elif kind == "ACCESS_REQUEST":
        request_ids.append(target)
    elif kind == "GRANT":
        grant_ids.append(target)
    elif kind == "DOCUMENT":
        for row in many(
            conn, "SELECT case_id FROM documents WHERE id = ANY(%s)", (uuids([target]),)
        ):
            cases.add(str(row["case_id"]))
    cases.update(str(u) for u in uuids(case_ids))
    link_ends = (
        "SELECT case_a_id, case_b_id FROM links WHERE link_id = ANY(%s)",
        "SELECT l.case_a_id, l.case_b_id FROM stubs s JOIN links l USING (link_id) "
        "WHERE s.stub_id = ANY(%s)",
        "SELECT l.case_a_id, l.case_b_id FROM access_requests r JOIN links l USING (link_id) "
        "WHERE r.id = ANY(%s)",
        "SELECT l.case_a_id, l.case_b_id FROM access_grants g JOIN links l USING (link_id) "
        "WHERE g.id = ANY(%s)",
    )
    for query, values in zip(link_ends, (link_ids, stub_ids, request_ids, grant_ids), strict=True):
        found = uuids(values)
        if found:
            for row in many(conn, query, (found,)):
                cases.update((str(row["case_a_id"]), str(row["case_b_id"])))
    found_entities = uuids(entity_ids)
    if found_entities:
        for row in many(conn, "SELECT case_id FROM entities WHERE id = ANY(%s)", (found_entities,)):
            cases.add(str(row["case_id"]))
    return cases


def append(conn: Conn, event: AuditEvent, *, check: bool = True) -> int:
    """Append one row to the chain on `conn`'s transaction and return its `seq`."""
    allowed = EVENTS.get(event.event_type)
    if allowed is None:
        raise AuditError(f"unknown audit event {event.event_type}")
    unknown = set(event.detail) - set(allowed)
    if unknown:
        raise AuditError(f"detail keys not allowed for {event.event_type}: {sorted(unknown)}")
    if check:
        missing = cases_revealed(conn, event) - {r["case_id"] for r in event.refs}
        if missing:
            raise AuditError("refs do not cover the cases the row reveals")
    conn.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_KEY,))
    last = one(conn, "SELECT seq, row_hash FROM audit_log ORDER BY seq DESC LIMIT 1")
    seq = 1 if last is None else int(last["seq"]) + 1
    prev = ZERO_HASH if last is None else bytes(last["row_hash"])
    now = one(conn, "SELECT clock_timestamp() AS now")
    now = need(now)
    columns: dict[str, Any] = {
        "seq": seq,
        "event_id": uuid.uuid4(),
        "occurred_at": now["now"],
        "event_type": event.event_type,
        "outcome": event.outcome,
        "actor_kind": event.actor.kind,
        "actor_user_id": _uuid_or_none(event.actor.user_id),
        "actor_role": event.actor.role,
        "actor_district_id": _uuid_or_none(event.actor.district_id),
        "reason_code": event.reason_code,
        "refs": event.refs,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "resolved_target": event.resolved_target,
        "detail": event.detail,
        "session_id": _uuid_or_none(event.session_id),
        "request_id": _uuid_or_none(event.request_id),
        "client_ip": event.client_ip,
        "row_nonce": os.urandom(16),
        "prev_hash": prev,
    }
    columns["row_hash"] = row_hash(prev, columns)
    conn.execute(
        "INSERT INTO audit_log (seq, event_id, occurred_at, event_type, outcome, actor_kind, "
        "actor_user_id, actor_role, actor_district_id, reason_code, refs, target_type, target_id, "
        "resolved_target, detail, session_id, request_id, client_ip, row_nonce, prev_hash, "
        "row_hash) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
        "%s::inet, %s, %s, %s)",
        (
            columns["seq"],
            columns["event_id"],
            columns["occurred_at"],
            columns["event_type"],
            columns["outcome"],
            columns["actor_kind"],
            columns["actor_user_id"],
            columns["actor_role"],
            columns["actor_district_id"],
            columns["reason_code"],
            Jsonb(columns["refs"]),
            columns["target_type"],
            columns["target_id"],
            columns["resolved_target"],
            Jsonb(columns["detail"]),
            columns["session_id"],
            columns["request_id"],
            columns["client_ip"],
            columns["row_nonce"],
            columns["prev_hash"],
            columns["row_hash"],
        ),
    )
    return seq


def _uuid_or_none(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value else None


def _row_columns(row: Row) -> dict[str, Any]:
    columns = {name: row[name] for name in HASHED_COLUMNS}
    if columns["client_ip"] is not None:
        columns["client_ip"] = str(columns["client_ip"])
    return columns


def read_anchor(path: Path) -> dict[str, Any] | None:
    """The last well-formed anchor line, or None when the file is missing or empty."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            anchor: dict[str, Any] = json.loads(line)
        except ValueError:
            continue
        if isinstance(anchor.get("seq"), int) and isinstance(anchor.get("row_hash"), str):
            return anchor
    return None


def write_anchor(conn: Conn, path: Path) -> None:
    """Append `{seq, row_hash, at}` for the current head. The file is only ever appended to."""
    head = one(conn, "SELECT seq, row_hash FROM audit_log ORDER BY seq DESC LIMIT 1")
    if head is None:
        return
    line = json.dumps(
        {
            "seq": int(head["seq"]),
            "row_hash": bytes(head["row_hash"]).hex(),
            "at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, (line + "\n").encode())
    finally:
        os.close(fd)


def verify(conn: Conn, anchor_path: Path, tail: int | None = None) -> tuple[bool, int | None]:
    """Check steps 1 to 4 of spec section 4. Returns (ok, first_bad_seq).

    `tail` limits the walk to the last N rows (startup); the row before the window supplies the
    expected `prev_hash`."""
    start = 1
    expected_prev = ZERO_HASH
    if tail is not None:
        head = one(conn, "SELECT max(seq) AS m FROM audit_log")
        top = int(head["m"]) if head and head["m"] is not None else 0
        start = max(1, top - tail + 1)
        if start > 1:
            before = one(conn, "SELECT row_hash FROM audit_log WHERE seq = %s", (start - 1,))
            if before is None:
                return False, start - 1
            expected_prev = bytes(before["row_hash"])
    expected_seq = start
    last_seq = start - 1
    last_hash = expected_prev
    with conn.cursor(name="audit_verify") as cursor:
        cursor.execute("SELECT * FROM audit_log WHERE seq >= %s ORDER BY seq", (start,))
        for row in cursor:
            seq = int(row["seq"])
            if seq != expected_seq:
                return False, expected_seq
            if bytes(row["prev_hash"]) != last_hash:
                return False, seq
            if row_hash(last_hash, _row_columns(row)) != bytes(row["row_hash"]):
                return False, seq
            last_hash = bytes(row["row_hash"])
            last_seq = seq
            expected_seq += 1
    anchor = read_anchor(anchor_path)
    if anchor is None and last_seq > 1:
        # No anchor with more than one row: the file was lost or emptied. Only a log that holds
        # just AUDIT_CHAIN_STARTED may lack one (the API writes the first anchor at startup).
        return False, 1
    if anchor is not None:
        if last_seq < anchor["seq"]:
            return False, int(anchor["seq"])
        if start <= anchor["seq"]:
            anchored = one(conn, "SELECT row_hash FROM audit_log WHERE seq = %s", (anchor["seq"],))
            if anchored is None or bytes(anchored["row_hash"]).hex() != anchor["row_hash"]:
                return False, int(anchor["seq"])
    return True, None
