"""Pending changes: the four-eyes workflow for users, assignments and thresholds."""

import hashlib
import json
import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from psycopg.types.json import Jsonb

from tracex_api import audit
from tracex_api.context import (
    ADMIN_ONLY,
    SENIOR_ONLY,
    SENIOR_OR_ADMIN,
    Ctx,
    authed_ctx,
    endpoint,
    iso,
)
from tracex_api.db import Row, many, need, one
from tracex_api.errors import ApiError, invalid
from tracex_api.policy import ROLES
from tracex_api.views import as_uuid, page_slice

router = APIRouter()
KINDS = (
    "USER_CREATE",
    "USER_ENABLE",
    "USER_DISABLE",
    "USER_ROLE",
    "USER_JURISDICTION",
    "ASSIGNMENT_ADD",
    "ASSIGNMENT_REMOVE",
    "THRESHOLDS",
)
INTERNAL_KEYS = ("coverage_rows", "case_id")
DISTRICT_ROLES = ("JUNIOR", "INVESTIGATOR", "SUPERVISOR")

# Closed allow-lists (D51, D35): the stored, shown and applied value is built only from these keys.
TOP_KEYS_BY_KIND: dict[str, frozenset[str]] = {
    "USER_CREATE": frozenset({"kind", "new_value"}),
    "USER_ENABLE": frozenset({"kind", "subject_user_id"}),
    "USER_DISABLE": frozenset({"kind", "subject_user_id"}),
    "USER_ROLE": frozenset({"kind", "subject_user_id", "new_value"}),
    "USER_JURISDICTION": frozenset({"kind", "subject_user_id", "new_value"}),
    "ASSIGNMENT_ADD": frozenset({"kind", "subject_user_id", "new_value"}),
    "ASSIGNMENT_REMOVE": frozenset({"kind", "subject_user_id", "new_value"}),
    "THRESHOLDS": frozenset({"kind", "new_value"}),
}
NEW_VALUE_KEYS_BY_KIND: dict[str, frozenset[str]] = {
    "USER_CREATE": frozenset({"username", "display_name", "role", "district_id", "coverage"}),
    "USER_ENABLE": frozenset(),
    "USER_DISABLE": frozenset(),
    "USER_ROLE": frozenset({"role"}),
    "USER_JURISDICTION": frozenset({"district_id", "coverage"}),
    "ASSIGNMENT_ADD": frozenset({"case_number"}),
    "ASSIGNMENT_REMOVE": frozenset({"case_number"}),
    "THRESHOLDS": frozenset({"high_min", "medium_min"}),
}
COVERAGE_KEYS = frozenset({"all_states", "state_ids", "district_ids"})


def _unknown(key: str, where: str) -> ApiError:
    """422 for a key outside the allow-list. The contract limits a field name to a-z and
    underscore, so a key that does not fit is reported under the object that holds it."""
    return invalid(key if re.fullmatch(r"[a-z_]{1,64}", key) else where, "unknown_field")


def _closed(obj: dict[str, Any], allowed: frozenset[str], where: str) -> None:
    """Refuse any key outside the allow-list with a field error that names the key."""
    for key in sorted(obj):
        if key not in allowed:
            raise _unknown(key, where)


def canonical_hash(kind: str, subject: str | None, old: Any, new: Any) -> bytes:
    body = json.dumps(
        {"kind": kind, "subject": subject, "old": old, "new": new},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode()).digest()


def _user(ctx: Ctx, user_id: str) -> Row | None:
    key = as_uuid(user_id)
    return one(ctx.conn, "SELECT * FROM users WHERE id = %s", (key,)) if key else None


def _coverage_rows(ctx: Ctx, coverage: Any) -> tuple[list[dict[str, Any]], list[str], bool]:
    """Coverage rows, the districts they touch, and whether it is all-state."""
    if not isinstance(coverage, dict):
        raise invalid("coverage", "required")
    _closed(coverage, COVERAGE_KEYS, "coverage")
    if coverage.get("all_states"):
        return [{"all_states": True}], [], True
    rows: list[dict[str, Any]] = []
    districts: set[str] = set()
    for state_id in coverage.get("state_ids", []):
        found = many(
            ctx.conn,
            "SELECT id FROM districts WHERE state_id = %s",
            (as_uuid(str(state_id)),),
        )
        if not found:
            raise invalid("coverage", "unknown_state")
        rows.append({"state_id": str(state_id)})
        districts.update(str(d["id"]) for d in found)
    for district_id in coverage.get("district_ids", []):
        if (
            one(
                ctx.conn, "SELECT 1 AS x FROM districts WHERE id = %s", (as_uuid(str(district_id)),)
            )
            is None
        ):
            raise invalid("coverage", "unknown_district")
        rows.append({"district_id": str(district_id)})
        districts.add(str(district_id))
    if not rows:
        raise invalid("coverage", "required")
    return rows, sorted(districts), False


def _coverage_of(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The coverage the approver sees, rebuilt from the rows that will be applied."""
    if rows == [{"all_states": True}]:
        return {"all_states": True, "state_ids": [], "district_ids": []}
    return {
        "state_ids": [r["state_id"] for r in rows if "state_id" in r],
        "district_ids": [r["district_id"] for r in rows if "district_id" in r],
    }


def _user_districts(ctx: Ctx, user: Row) -> list[str]:
    if user["district_id"]:
        return [str(user["district_id"])]
    rows = many(ctx.conn, "SELECT * FROM user_coverage WHERE user_id = %s", (user["id"],))
    out: set[str] = set()
    for r in rows:
        if r["district_id"]:
            out.add(str(r["district_id"]))
        if r["state_id"]:
            out.update(
                str(d["id"])
                for d in many(
                    ctx.conn, "SELECT id FROM districts WHERE state_id = %s", (r["state_id"],)
                )
            )
    return sorted(out)


def _user_all_states(ctx: Ctx, user: Row) -> bool:
    return any(
        r["all_states"]
        for r in many(
            ctx.conn, "SELECT all_states FROM user_coverage WHERE user_id = %s", (user["id"],)
        )
    )


def _current_value(ctx: Ctx, kind: str, subject: Row | None, new: dict[str, Any]) -> Any:
    if kind == "THRESHOLDS":
        row = one(
            ctx.conn, "SELECT * FROM threshold_versions ORDER BY thresholds_version DESC LIMIT 1"
        )
        row = need(row)
        return {"high_min": float(row["high_min"]), "medium_min": float(row["medium_min"])}
    if subject is None:
        return None
    if kind in ("USER_ENABLE", "USER_DISABLE"):
        return {"active": subject["active"]}
    if kind == "USER_ROLE":
        return {"role": subject["role"]}
    if kind == "USER_JURISDICTION":
        return {"district_id": str(subject["district_id"]) if subject["district_id"] else None}
    if kind in ("ASSIGNMENT_ADD", "ASSIGNMENT_REMOVE"):
        row = one(
            ctx.conn,
            "SELECT active FROM case_assignments WHERE case_id = %s AND user_id = %s",
            (as_uuid(str(new.get("case_id"))), subject["id"]),
        )
        return {"assigned": bool(row and row["active"])}
    return None


def change_out(ctx: Ctx, c: Row) -> dict[str, Any]:
    def ref(user_id: Any) -> dict[str, Any] | None:
        if user_id is None:
            return None
        u = one(ctx.conn, "SELECT id, display_name, role FROM users WHERE id = %s", (user_id,))
        u = need(u)
        return {"user_id": str(u["id"]), "display_name": u["display_name"], "role": u["role"]}

    return {
        "change_id": str(c["id"]),
        "kind": c["kind"],
        "state": c["state"],
        "subject": ref(c["subject_user_id"]),
        "old_value": c["old_value"],
        "new_value": {k: v for k, v in c["new_value"].items() if k not in INTERNAL_KEYS},
        "proposer": ref(c["proposer_id"]),
        "decider": ref(c["decider_id"]),
        "change_hash": bytes(c["change_hash"]).hex(),
        "proposed_at": iso(c["proposed_at"]),
        "decided_at": iso(c["decided_at"]),
    }


def _case_of(c: Row) -> str | None:
    value = c["new_value"].get("case_id")
    return str(value) if value else None


def approver_sees(ctx: Ctx, c: Row) -> bool:
    me = ctx.me
    if me.role == "ADMIN":
        return str(c["proposer_id"]) == me.user_id
    if me.role != "SENIOR":
        return False
    if c["needs_all_states"]:
        return me.coverage_all
    return all(me.covers_district(str(d)) for d in c["subject_district_ids"])


def _change(ctx: Ctx, change_id: str) -> Row | None:
    key = as_uuid(change_id)
    return one(ctx.conn, "SELECT * FROM pending_changes WHERE id = %s", (key,)) if key else None


def _audit_view(ctx: Ctx, rows: list[Row]) -> None:
    cases = [c for c in (_case_of(r) for r in rows) if c]
    ctx.audit(
        "CHANGE_VIEWED",
        refs=cases,
        detail={
            "change_ids": [str(r["id"]) for r in rows],
            **({"case_ids": cases} if cases else {}),
        },
    )


@endpoint(
    router,
    "POST",
    "/pending-changes",
    policy=ADMIN_ONLY,
    audit_event="CHANGE_PROPOSED",
    status_code=201,
)
def propose_change(ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    try:
        raw = json.loads(getattr(ctx.request.state, "body", b"") or b"{}")
    except ValueError:
        raise invalid("body", "malformed") from None
    if not isinstance(raw, dict) or raw.get("kind") not in KINDS:
        raise invalid("kind", "invalid_enum")
    kind: str = raw["kind"]
    _closed(raw, TOP_KEYS_BY_KIND[kind], "body")
    given = raw.get("new_value")
    if given is None:
        given = {}
    if not isinstance(given, dict):
        raise invalid("new_value", "invalid")
    _closed(given, NEW_VALUE_KEYS_BY_KIND[kind], "new_value")
    new: dict[str, Any] = dict(given)
    subject: Row | None = None
    if kind not in ("USER_CREATE", "THRESHOLDS"):
        subject = _user(ctx, str(raw.get("subject_user_id", "")))
        if subject is None:
            raise invalid("subject_user_id", "unknown_user")
    if (
        kind in ("USER_CREATE", "USER_JURISDICTION")
        and new.get("district_id")
        and new.get("coverage")
    ):
        raise invalid("new_value", "district_and_coverage")
    districts: list[str] = []
    needs_all = False
    if kind == "USER_CREATE":
        username = new.get("username")
        if (
            not isinstance(username, str)
            or not username
            or one(ctx.conn, "SELECT 1 AS x FROM users WHERE username = %s", (username.lower(),))
        ):
            raise invalid("username", "invalid")
        role = new.get("role")
        display_name = new.get("display_name")
        if role not in ROLES or not isinstance(display_name, str) or not display_name:
            raise invalid("role", "invalid_enum")
        base = {"username": username, "display_name": display_name, "role": role}
        if role in DISTRICT_ROLES:
            if "coverage" in new:
                raise _unknown("coverage", "new_value")
            if (
                not new.get("district_id")
                or one(
                    ctx.conn,
                    "SELECT 1 AS x FROM districts WHERE id = %s",
                    (as_uuid(str(new["district_id"])),),
                )
                is None
            ):
                raise invalid("district_id", "unknown_district")
            districts = [str(new["district_id"])]
            new = {**base, "district_id": str(new["district_id"])}
        elif role == "SENIOR":
            if "district_id" in new:
                raise _unknown("district_id", "new_value")
            rows, districts, all_states = _coverage_rows(ctx, new.get("coverage"))
            new = {**base, "coverage": _coverage_of(rows), "coverage_rows": rows}
            needs_all = all_states
        else:
            for extra in ("district_id", "coverage"):
                if extra in new:
                    raise _unknown(extra, "new_value")
            new = base
            needs_all = True
    elif kind in ("USER_ENABLE", "USER_DISABLE"):
        subject = need(subject)
        new = {}
        if subject["active"] is (kind == "USER_ENABLE"):
            raise invalid("kind", "no_change")
        districts = _user_districts(ctx, subject)
        needs_all = subject["role"] == "ADMIN" or _user_all_states(ctx, subject)
    elif kind == "USER_ROLE":
        subject = need(subject)
        role = new.get("role")
        if role not in ROLES or role == subject["role"]:
            raise invalid("role", "invalid")
        if role in DISTRICT_ROLES and not subject["district_id"]:
            raise invalid("role", "needs_district")
        new = {"role": role}
        districts = _user_districts(ctx, subject)
        needs_all = bool({role, subject["role"]} & {"SENIOR", "ADMIN"})
    elif kind == "USER_JURISDICTION":
        subject = need(subject)
        if subject["role"] in DISTRICT_ROLES:
            if "coverage" in new:
                raise _unknown("coverage", "new_value")
            district = as_uuid(str(new.get("district_id", "")))
            if (
                district is None
                or one(ctx.conn, "SELECT 1 AS x FROM districts WHERE id = %s", (district,)) is None
            ):
                raise invalid("district_id", "unknown_district")
            districts = sorted({str(subject["district_id"]), str(district)})
            new = {"district_id": str(district)}
        elif subject["role"] == "SENIOR":
            if "district_id" in new:
                raise _unknown("district_id", "new_value")
            rows, new_districts, all_states = _coverage_rows(ctx, new.get("coverage"))
            new = {"coverage": _coverage_of(rows), "coverage_rows": rows}
            districts = sorted(set(_user_districts(ctx, subject)) | set(new_districts))
            needs_all = all_states or _user_all_states(ctx, subject)
        else:
            raise invalid("kind", "not_applicable")
    elif kind in ("ASSIGNMENT_ADD", "ASSIGNMENT_REMOVE"):
        subject = need(subject)
        number = new.get("case_number")
        if not isinstance(number, str):
            raise invalid("case_number", "invalid")
        case = one(
            ctx.conn,
            "SELECT * FROM cases WHERE case_number = %s ORDER BY (district_id = %s) DESC LIMIT 1",
            (number, subject["district_id"]),
        )
        if not number or case is None:
            raise invalid("case_number", "invalid")
        new = {"case_number": number, "case_id": str(case["id"])}
        districts = sorted({str(d) for d in (subject["district_id"], case["district_id"]) if d})
        needs_all = subject["role"] in ("ADMIN",) or _user_all_states(ctx, subject)
    else:
        high, medium = new.get("high_min"), new.get("medium_min")
        if (
            not isinstance(high, int | float)
            or not isinstance(medium, int | float)
            or isinstance(high, bool)
            or isinstance(medium, bool)
            or not 70 <= high <= 100
            or not 30 <= medium <= high - 10
        ):
            raise invalid("new_value", "out_of_range")
        new = {"high_min": float(high), "medium_min": float(medium)}
        needs_all = True
    old = _current_value(ctx, kind, subject, new)
    digest = canonical_hash(kind, str(subject["id"]) if subject else None, old, new)
    row = one(
        ctx.conn,
        "INSERT INTO pending_changes (kind, subject_user_id, old_value, new_value, proposer_id, "
        "change_hash, state, proposed_at, subject_district_ids, needs_all_states) "
        "VALUES (%s, %s, %s, %s, %s, %s, 'PENDING', %s, %s, %s) RETURNING *",
        (
            kind, subject["id"] if subject else None,
            Jsonb(old) if old is not None else None, Jsonb(new),
            uuid.UUID(ctx.me.user_id), digest, ctx.now(),
            [uuid.UUID(d) for d in districts], needs_all,
        ),
    )  # fmt: skip
    row = need(row)
    case_ref_id = _case_of(row)
    detail: dict[str, Any] = {
        "kind": kind,
        "change_hash": digest.hex(),
        "old_value": old,
        "new_value": {k: v for k, v in new.items() if k not in ("coverage_rows", "case_number")},
    }
    if subject:
        detail["subject_id"] = str(subject["id"])
    ctx.audit(
        "CHANGE_PROPOSED",
        refs=[case_ref_id] if case_ref_id else [],
        target_type="CHANGE",
        target_id=str(row["id"]),
        detail=detail,
    )
    return change_out(ctx, row)


@endpoint(router, "GET", "/pending-changes", policy=SENIOR_OR_ADMIN, audit_event="CHANGE_VIEWED")
def list_changes(
    ctx: Ctx = Depends(authed_ctx),
    state: str | None = Query(None),
    kind: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
) -> dict[str, Any]:
    if state is not None and state not in ("PENDING", "APPROVED", "DENIED"):
        raise invalid("state", "invalid_enum")
    if kind is not None and kind not in KINDS:
        raise invalid("kind", "invalid_enum")
    rows = [
        c
        for c in many(ctx.conn, "SELECT * FROM pending_changes ORDER BY proposed_at DESC, id")
        if approver_sees(ctx, c)
    ]
    if state:
        rows = [c for c in rows if c["state"] == state]
    if kind:
        rows = [c for c in rows if c["kind"] == kind]
    chunk, token = page_slice(ctx, rows, limit, cursor, {"state": state, "kind": kind}, "changes")
    _audit_view(ctx, list(chunk))
    return {"items": [change_out(ctx, c) for c in chunk], "next_cursor": token, "total": len(rows)}


@endpoint(
    router,
    "GET",
    "/pending-changes/{change_id}",
    policy=SENIOR_OR_ADMIN,
    audit_event="CHANGE_VIEWED",
)
def get_change(change_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    c = _change(ctx, change_id)
    if c is None or not approver_sees(ctx, c):
        raise ctx.not_found(change_id, resolved=change_id if c else None)
    _audit_view(ctx, [c])
    return change_out(ctx, c)


def _decidable(ctx: Ctx, change_id: str) -> Row:
    c = _change(ctx, change_id)
    if c is None or not approver_sees(ctx, c):
        raise ctx.not_found(change_id, resolved=change_id if c else None)
    case = _case_of(c)
    if c["subject_user_id"] and str(c["subject_user_id"]) == ctx.me.user_id:
        raise ctx.forbidden("CHANGE", str(c["id"]), [case] if case else [])
    return c


def _would_orphan(ctx: Ctx, c: Row) -> bool:
    """Disabling, demoting or re-homing the last SENIOR able to approve a district."""
    if (
        c["kind"] not in ("USER_DISABLE", "USER_ROLE", "USER_JURISDICTION")
        or not c["subject_user_id"]
    ):
        return False
    subject = one(ctx.conn, "SELECT * FROM users WHERE id = %s", (c["subject_user_id"],))
    if subject is None or subject["role"] != "SENIOR":
        return False
    if c["kind"] == "USER_ROLE" and c["new_value"].get("role") == "SENIOR":
        return False
    others = list(
        many(
            ctx.conn,
            "SELECT * FROM users WHERE role = 'SENIOR' AND active AND id <> %s",
            (subject["id"],),
        )
    )
    covered: set[str] = set()
    all_states = False
    for u in others:
        all_states = all_states or _user_all_states(ctx, u)
        covered.update(_user_districts(ctx, u))
    if all_states:
        return False
    needed = set(_user_districts(ctx, subject))
    if _user_all_states(ctx, subject):
        return True
    return not needed <= covered


def _close_holder_grants(ctx: Ctx, user_id: Any) -> None:
    for g in many(
        ctx.conn,
        "SELECT g.id, l.case_a_id, l.case_b_id FROM access_grants g JOIN links l USING (link_id) "
        "WHERE g.holder_id = %s AND g.state = 'ACTIVE'",
        (user_id,),
    ):
        ctx.conn.execute(
            "UPDATE access_grants SET state = 'REVOKED', closed_at = %s, "
            "close_cause = 'ROLE_CHANGE' "
            "WHERE id = %s",
            (ctx.now(), g["id"]),
        )
        ctx.audit(
            "ACCESS_GRANT_CLOSED",
            actor=audit.SYSTEM,
            refs=[str(g["case_a_id"]), str(g["case_b_id"])],
            target_type="GRANT",
            target_id=str(g["id"]),
            detail={"cause": "ROLE_CHANGE"},
        )
    ctx.conn.execute(
        "UPDATE sessions SET revoked_at = %s, revoke_reason = 'AUTHZ_CHANGED' "
        "WHERE user_id = %s AND revoked_at IS NULL",
        (ctx.now(), user_id),
    )


@endpoint(
    router,
    "POST",
    "/pending-changes/{change_id}/approve",
    policy=SENIOR_ONLY,
    audit_event="CHANGE_APPROVED",
)
def approve_change(change_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    c = _decidable(ctx, change_id)
    if c["state"] != "PENDING":
        raise ApiError("NOT_PENDING")
    try:
        raw = json.loads(getattr(ctx.request.state, "body", b"") or b"{}")
    except ValueError:
        raw = {}
    presented = raw.get("change_hash") if isinstance(raw, dict) else None
    if not isinstance(presented, str) or len(presented) != 64:
        raise invalid("change_hash", "invalid")
    if presented != bytes(c["change_hash"]).hex():
        raise ApiError("CHANGE_HASH_STALE")
    subject = (
        one(ctx.conn, "SELECT * FROM users WHERE id = %s", (c["subject_user_id"],))
        if c["subject_user_id"]
        else None
    )
    if (
        c["old_value"] is not None
        and _current_value(ctx, c["kind"], subject, c["new_value"]) != c["old_value"]
    ):
        raise ApiError("OLD_VALUE_CHANGED")
    if _would_orphan(ctx, c):
        raise ApiError("LAST_APPROVER")
    ctx.conn.execute(
        "UPDATE pending_changes SET state = 'APPROVED', decider_id = %s, decided_at = %s, "
        "approved_hash = %s WHERE id = %s",
        (uuid.UUID(ctx.me.user_id), ctx.now(), c["change_hash"], c["id"]),
    )
    ctx.conn.execute("SELECT apply_change(%s)", (c["id"],))
    case = _case_of(c)
    base = {
        "kind": c["kind"],
        "change_hash": bytes(c["change_hash"]).hex(),
        "old_value": c["old_value"],
        "new_value": {
            k: v for k, v in c["new_value"].items() if k not in ("coverage_rows", "case_number")
        },
    }
    if c["subject_user_id"]:
        base["subject_id"] = str(c["subject_user_id"])
    ctx.audit(
        "CHANGE_APPROVED",
        refs=[case] if case else [],
        target_type="CHANGE",
        target_id=str(c["id"]),
        detail=base,
    )
    _after_apply(ctx, c, subject)
    done = _change(ctx, change_id)
    done = need(done)
    return change_out(ctx, done)


def _after_apply(ctx: Ctx, c: Row, subject: Row | None) -> None:
    kind = c["kind"]
    if kind == "USER_CREATE":
        created = one(
            ctx.conn, "SELECT * FROM users WHERE username = %s", (c["new_value"]["username"],)
        )
        if created:
            ctx.audit(
                "USER_CREATED",
                target_type="USER",
                target_id=str(created["id"]),
                detail={
                    "role": created["role"],
                    **(
                        {"district_id": str(created["district_id"])}
                        if created["district_id"]
                        else {}
                    ),
                },
            )
        return
    if subject is None:
        return
    fresh = one(ctx.conn, "SELECT * FROM users WHERE id = %s", (subject["id"],))
    fresh = need(fresh)
    detail: dict[str, Any] = {"role": fresh["role"]}
    if fresh["district_id"]:
        detail["district_id"] = str(fresh["district_id"])
    if kind in ("USER_ENABLE", "USER_DISABLE"):
        ctx.audit(
            "USER_ENABLED" if kind == "USER_ENABLE" else "USER_DISABLED",
            target_type="USER",
            target_id=str(subject["id"]),
            detail=detail,
        )
    if kind in ("ASSIGNMENT_ADD", "ASSIGNMENT_REMOVE"):
        case = _case_of(c)
        ctx.audit(
            "ASSIGNMENT_CHANGED",
            refs=[case] if case else [],
            target_type="USER",
            target_id=str(subject["id"]),
            detail={"case_id": case, "added": kind == "ASSIGNMENT_ADD"},
        )
    if kind != "THRESHOLDS":
        _close_holder_grants(ctx, subject["id"])


@endpoint(
    router,
    "POST",
    "/pending-changes/{change_id}/deny",
    policy=SENIOR_ONLY,
    audit_event="CHANGE_DENIED",
)
def deny_change(change_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    c = _decidable(ctx, change_id)
    if c["state"] != "PENDING":
        raise ApiError("NOT_PENDING")
    ctx.conn.execute(
        "UPDATE pending_changes SET state = 'DENIED', decider_id = %s, decided_at = %s "
        "WHERE id = %s",
        (uuid.UUID(ctx.me.user_id), ctx.now(), c["id"]),
    )
    case = _case_of(c)
    detail: dict[str, Any] = {"kind": c["kind"], "change_hash": bytes(c["change_hash"]).hex()}
    if c["subject_user_id"]:
        detail["subject_id"] = str(c["subject_user_id"])
    ctx.audit(
        "CHANGE_DENIED",
        refs=[case] if case else [],
        target_type="CHANGE",
        target_id=str(c["id"]),
        detail=detail,
    )
    done = _change(ctx, change_id)
    done = need(done)
    return change_out(ctx, done)
