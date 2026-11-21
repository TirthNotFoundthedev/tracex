"""Reading the audit log under the row-level rule, and verifying the chain.

Spec: docs/specs/api-audit-log.md section 7. A row exists for the reader only if rule (a), (b),
(c) or (d) admits it; everything else is absent: no placeholder, no gap, no count. Filters and
sorting run only over what the reader can see.
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query

from tracex_api import audit
from tracex_api.audit import AuditEvent
from tracex_api.audit_events import EVENTS, SYSTEM_EVENT_PREFIXES, P
from tracex_api.context import SENIOR_ONLY, SUPERVISOR_UP, Ctx, authed_ctx, endpoint, iso
from tracex_api.db import Row, many, one
from tracex_api.errors import ApiError, invalid
from tracex_api.security import CursorError, open_cursor, row_ref, seal_cursor
from tracex_api.views import as_uuid

router = APIRouter()
SORTS = ("occurred_at", "event_type", "outcome")


def _row_cases(row: Row) -> list[str]:
    return [str(r["case_id"]) for r in row["refs"]]


def _is_system_event(event_type: str) -> bool:
    return event_type.startswith(SYSTEM_EVENT_PREFIXES)


def _user_in_coverage(ctx: Ctx, user: Row) -> bool:
    me = ctx.me
    if user["district_id"]:
        return me.covers_district(str(user["district_id"]))
    return me.coverage_all


def _named_inside_coverage(ctx: Ctx, row: Row) -> bool:
    """Rule (d) for a SENIOR: every user and district the row names lies inside coverage."""
    me = ctx.me
    if me.coverage_all:
        return True
    detail = row["detail"]
    users: set[str] = set()
    districts: set[str] = set()
    if row["actor_district_id"]:
        districts.add(str(row["actor_district_id"]))
    if row["target_type"] == "USER" and row["target_id"]:
        users.add(str(row["target_id"]))
    for key in ("subject_id", "claimed_sub"):
        value = detail.get(key)
        if isinstance(value, str) and as_uuid(value):
            users.add(value)
    claimed = detail.get("claimed_username")
    if isinstance(claimed, str) and not claimed.startswith("hmac:"):
        found = one(ctx.conn, "SELECT id FROM users WHERE username = %s", (claimed,))
        if found:
            users.add(str(found["id"]))
    for key in ("old_value", "new_value"):
        value = detail.get(key)
        if isinstance(value, dict) and value.get("district_id"):
            districts.add(str(value["district_id"]))
    if row["event_type"] == "ACCESS_DENIED" or row["target_type"] == "UNRESOLVED":
        return False
    for u in users:
        found_user = one(ctx.conn, "SELECT * FROM users WHERE id = %s", (as_uuid(u),))
        if found_user is not None and not _user_in_coverage(ctx, found_user):
            return False
    return all(me.covers_district(d) for d in districts)


def admitted(ctx: Ctx, row: Row) -> bool:
    me = ctx.me
    if row["actor_user_id"] is not None and str(row["actor_user_id"]) == me.user_id:
        return True
    in_chain = (
        me.role in ("SUPERVISOR", "SENIOR")
        and row["actor_district_id"]
        and me.in_scope(str(row["actor_district_id"]))
    )
    if in_chain:
        return True
    cases = _row_cases(row)
    if cases:
        facts = ctx.case_facts(cases)
        return all(c in facts and me.can_view_case(c, facts[c].district_id) for c in cases)
    if not _is_system_event(row["event_type"]):
        return False
    if me.role == "ADMIN":
        return True
    return me.role == "SENIOR" and _named_inside_coverage(ctx, row)


def serialize(ctx: Ctx, row: Row) -> tuple[dict[str, Any], bool]:
    """The reader's view of an admitted row, and whether any field was dropped."""
    me = ctx.me
    refs = [dict(r) for r in row["refs"]]
    facts = ctx.case_facts([r["case_id"] for r in refs])
    visible = [
        r
        for r in refs
        if r["case_id"] in facts and me.can_view_case(r["case_id"], facts[r["case_id"]].district_id)
    ]
    dropped = len(visible) != len(refs)
    klass = EVENTS[row["event_type"]]
    detail: dict[str, Any] = {}
    for key, value in row["detail"].items():
        k = klass.get(key)
        if k is None or k == P:
            continue
        if dropped and k == "J":
            continue
        if dropped and k == "S" and _key_hidden(ctx, row, key, value):
            continue
        detail[key] = value
    actor: dict[str, Any] = {"kind": row["actor_kind"]}
    if row["actor_user_id"]:
        actor["user_id"] = str(row["actor_user_id"])
    if row["actor_role"]:
        actor["role"] = row["actor_role"]
    if row["actor_district_id"]:
        actor["district_id"] = str(row["actor_district_id"])
    out: dict[str, Any] = {
        "row_ref": row_ref(ctx.state.settings.row_ref_key, str(row["event_id"]), me.user_id),
        "occurred_at": iso(row["occurred_at"]),
        "event_type": row["event_type"],
        "outcome": row["outcome"],
        "actor": actor,
        "refs": [{"case_id": r["case_id"], "district_id": r["district_id"]} for r in visible],
        "detail": detail,
    }
    if row["reason_code"]:
        out["reason_code"] = row["reason_code"]
    joint_target = row["target_type"] in ("LINK", "STUB", "ACCESS_REQUEST", "GRANT")
    side_target = row["target_type"] in ("CASE", "ENTITY", "DOCUMENT")
    if row["target_type"] and not (dropped and (joint_target or side_target)):
        out["target_type"] = row["target_type"]
        out["target_id"] = row["target_id"]
    return out, dropped


def _key_hidden(ctx: Ctx, row: Row, key: str, value: Any) -> bool:
    probe = AuditEvent(row["event_type"], audit.SYSTEM, detail={key: value})
    cases = audit.cases_revealed(ctx.conn, probe)
    if not cases:
        return False
    facts = ctx.case_facts(sorted(cases))
    return any(c not in facts or not ctx.me.can_view_case(c, facts[c].district_id) for c in cases)


def _sort_key(sort: str, out: dict[str, Any]) -> tuple[str, str]:
    return (str(out[sort]), out["row_ref"])


@endpoint(router, "GET", "/audit", policy=SUPERVISOR_UP, audit_event="AUDIT_VIEWED")
def list_audit(
    ctx: Ctx = Depends(authed_ctx),
    event_type: str | None = Query(None),
    outcome: str | None = Query(None),
    actor_user_id: str | None = Query(None),
    case_id: str | None = Query(None),
    target_id: str | None = Query(None),
    occurred_from: datetime | None = Query(None),
    occurred_to: datetime | None = Query(None),
    sort: str = Query("occurred_at"),
    order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
) -> dict[str, Any]:
    if sort not in SORTS:
        raise invalid("sort", "invalid_enum")
    if order not in ("asc", "desc"):
        raise invalid("order", "invalid_enum")
    if outcome is not None and outcome not in ("SUCCESS", "DENIED", "FAILED"):
        raise invalid("outcome", "invalid_enum")
    filters = {
        "event_type": event_type, "outcome": outcome, "actor_user_id": actor_user_id,
        "case_id": case_id, "target_id": target_id,
        "occurred_from": occurred_from.isoformat() if occurred_from else None,
        "occurred_to": occurred_to.isoformat() if occurred_to else None,
        "sort": sort, "order": order,
    }  # fmt: skip
    bound = f"{ctx.me.user_id}|{sorted((k, str(v)) for k, v in filters.items() if v is not None)}"
    position: list[str] | None = None
    if cursor is not None:
        try:
            payload = open_cursor(ctx.state.settings.cursor_key, cursor, ctx.now())
        except CursorError as exc:
            raise ApiError(
                "VALIDATION_FAILED", [{"field": "cursor", "code": "invalid_cursor"}]
            ) from exc
        if payload.get("b") != bound or not isinstance(payload.get("p"), list):
            raise ApiError("VALIDATION_FAILED", [{"field": "cursor", "code": "invalid_cursor"}])
        position = [str(x) for x in payload["p"]]
    seqs = {}
    candidates = []
    for row in many(ctx.conn, "SELECT * FROM audit_log ORDER BY seq"):
        if not admitted(ctx, row):
            continue
        out, dropped = serialize(ctx, row)
        if event_type and out["event_type"] != event_type:
            continue
        if outcome and out["outcome"] != outcome:
            continue
        if actor_user_id and out["actor"].get("user_id") != actor_user_id.lower():
            continue
        if case_id and case_id.lower() not in [r["case_id"] for r in out["refs"]]:
            continue
        if target_id and out.get("target_id") != target_id:
            continue
        if occurred_from and row["occurred_at"] < occurred_from:
            continue
        if occurred_to and row["occurred_at"] > occurred_to:
            continue
        seqs[out["row_ref"]] = (int(row["seq"]), dropped)
        candidates.append(out)
    candidates.sort(key=lambda o: _sort_key(sort, o), reverse=order == "desc")
    if position is not None:
        key = (position[0], position[1])
        if order == "desc":
            candidates = [o for o in candidates if _sort_key(sort, o) < key]
        else:
            candidates = [o for o in candidates if _sort_key(sort, o) > key]
    page = candidates[:limit]
    token = None
    if len(candidates) > limit:
        last = page[-1]
        token = seal_cursor(
            ctx.state.settings.cursor_key,
            {"b": bound, "p": [str(last[sort]), last["row_ref"]]},
            ctx.now(),
        )
    shown = [seqs[o["row_ref"]] for o in page]
    detail: dict[str, Any] = {
        "filter_keys": sorted(
            k for k, v in filters.items() if v is not None and k not in ("sort", "order")
        ),
        "result_count": len(page),
        "redacted": any(d for _, d in shown),
    }
    if shown:
        detail["seq_from"] = min(s for s, _ in shown)
        detail["seq_to"] = max(s for s, _ in shown)
    ctx.audit("AUDIT_VIEWED", target_type="AUDIT", target_id="log", detail=detail)
    return {"items": page, "next_cursor": token, "result_count": len(page)}


@endpoint(router, "POST", "/audit/verify", policy=SENIOR_ONLY, audit_event="AUDIT_VERIFY_RUN")
def verify_chain(ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    path = ctx.state.settings.audit_anchor_path
    ok, bad = audit.verify(ctx.conn, path)
    head = one(ctx.conn, "SELECT max(seq) AS m FROM audit_log")
    anchor = audit.read_anchor(path)
    detail: dict[str, Any] = {
        "result": "OK" if ok else "BROKEN",
        "range_from": 1,
        "range_to": int(head["m"]) if head and head["m"] is not None else 0,
        "head_seq": int(head["m"]) if head and head["m"] is not None else 0,
    }
    if anchor:
        detail["anchor_seq"] = int(anchor["seq"])
    if bad is not None:
        detail["first_bad_seq"] = bad
    ctx.audit("AUDIT_VERIFY_RUN", target_type="AUDIT", target_id="chain", detail=detail)
    if ok:
        ctx.commit()
        audit.write_anchor(ctx.conn, path)
        return {"result": "OK"}
    return {"result": "BROKEN", "first_bad_seq": bad}


__all__ = ["router", "uuid"]
