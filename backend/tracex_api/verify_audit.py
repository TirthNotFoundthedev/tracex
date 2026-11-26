"""The nightly audit verify: a command a scheduler runs (cron, a compose `run`, a CI schedule).

    python -m tracex_api.verify_audit [--database-url URL] [--anchor-path PATH]

It reads `DATABASE_URL` and `AUDIT_ANCHOR_PATH` from the environment unless given. It walks the
whole hash chain and checks it against the anchor file (a missing anchor with more than one row
is BROKEN), and it checks every APPROVED `pending_changes` row against its CHANGE_APPROVED audit
row: same change id, same decider, same `change_hash` (architecture section 11, the four-eyes
limit of one database login). It prints one JSON line, writes an AUDIT_VERIFY_RUN row for the
SYSTEM actor, appends a fresh anchor only when everything is clean, and exits 0 (clean) or 1.
Every problem is also logged at error level so a log alert can pick it up.
"""

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from tracex_api import audit
from tracex_api.db import Conn, connect, many

logger = logging.getLogger(__name__)


@dataclass
class Report:
    chain_ok: bool
    first_bad_seq: int | None
    head_seq: int
    head_hash: bytes = b""
    mismatches: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.chain_ok and not self.mismatches


def check_approved_changes(conn: Conn) -> list[str]:
    """One message per APPROVED change whose audit row is missing or does not agree."""
    problems: list[str] = []
    for change in many(
        conn, "SELECT id, decider_id, change_hash FROM pending_changes WHERE state = 'APPROVED'"
    ):
        change_id = str(change["id"])
        rows = many(
            conn,
            "SELECT actor_user_id, detail->>'change_hash' AS change_hash FROM audit_log "
            "WHERE event_type = 'CHANGE_APPROVED' AND outcome = 'SUCCESS' "
            "AND target_type = 'CHANGE' AND target_id = %s",
            (change_id,),
        )
        if not rows:
            problems.append(f"change {change_id} is APPROVED but has no CHANGE_APPROVED audit row")
            continue
        by_decider = [r for r in rows if r["actor_user_id"] == change["decider_id"]]
        if not by_decider:
            problems.append(f"change {change_id}: the audit row names a different decider")
        elif not any(r["change_hash"] == bytes(change["change_hash"]).hex() for r in by_decider):
            problems.append(f"change {change_id}: the audit row has a different change_hash")
    return problems


def run_checks(conn: Conn, anchor_path: Path) -> Report:
    result = audit.verify_checked(conn, anchor_path)
    return Report(
        result.ok,
        result.first_bad_seq,
        result.head_seq,
        result.head_hash,
        check_approved_changes(conn),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the audit log and the approved changes.")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--anchor-path", default=os.environ.get("AUDIT_ANCHOR_PATH"))
    args = parser.parse_args(argv)
    if not args.database_url or not args.anchor_path:
        sys.stderr.write("DATABASE_URL and AUDIT_ANCHOR_PATH are required\n")
        return 2
    anchor_path = Path(args.anchor_path)
    with connect(args.database_url) as conn:
        report = run_checks(conn, anchor_path)
        detail: dict[str, object] = {
            "result": "OK" if report.ok else "BROKEN",
            "range_from": 1,
            "range_to": report.head_seq,
            "head_seq": report.head_seq,
        }
        anchor = audit.read_anchor(anchor_path)
        if anchor:
            detail["anchor_seq"] = int(anchor["seq"])
        if report.first_bad_seq is not None:
            detail["first_bad_seq"] = report.first_bad_seq
        audit.append(
            conn,
            audit.AuditEvent(
                "AUDIT_VERIFY_RUN",
                audit.SYSTEM,
                outcome="SUCCESS" if report.ok else "FAILED",
                target_type="AUDIT",
                target_id="chain",
                detail=detail,
            ),
        )
        conn.commit()
        if report.ok:
            # the row the walk checked, not a head read afterwards
            audit.append_anchor(anchor_path, report.head_seq, report.head_hash)
    if not report.chain_ok:
        logger.error("audit chain is BROKEN at seq %s", report.first_bad_seq)
    for problem in report.mismatches:
        logger.error("approved change mismatch: %s", problem)
    sys.stdout.write(
        json.dumps(
            {
                "result": detail["result"],
                "first_bad_seq": report.first_bad_seq,
                "head_seq": report.head_seq,
                "mismatches": report.mismatches,
            }
        )
        + "\n"
    )
    return 0 if report.ok else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
