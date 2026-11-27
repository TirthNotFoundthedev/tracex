"""Stubs, access requests and grants (spec: api-access-control sections 4 and 5)."""

import uuid
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from tracex_api.context import OFFICER, Ctx, authed_ctx, endpoint, iso, load_principal
from tracex_api.db import Row, many, need, one
from tracex_api.engine_bridge import close_grant
from tracex_api.errors import ApiError, invalid
from tracex_api.policy import LinkAccess, link_access
from tracex_api.views import (
    LinkFacts,
    as_uuid,
    link_cases,
    link_facts,
    link_row,
    page_slice,
    stub_out,
    stub_request_state,
)

router = APIRouter()
REQUEST_DAYS = 7
COOLDOWN = timedelta(hours=24)
MAX_PENDING = 10


class CreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stub_id: uuid.UUID
    reason: str = Field(min_length=10, max_length=500)


class ApproveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration_days: int = 30


class DenyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str | None = Field(default=None, min_length=1, max_length=200)


# ---------------------------------------------------------------------------------------------
# helpers


def _authority(ctx: Ctx, district_id: str) -> bool:
    me = ctx.me
    if me.role == "SUPERVISOR":
        return me.district_id == district_id
    if me.role == "SENIOR":
        return me.covers_district(district_id)
    return False


def _user_ref(ctx: Ctx, user_id: Any) -> dict[str, Any]:
    u = one(ctx.conn, "SELECT id, display_name, role FROM users WHERE id = %s", (user_id,))
    u = need(u)
    return {"user_id": str(u["id"]), "display_name": u["display_name"], "role": u["role"]}


def _grant_for_request(ctx: Ctx, request_id: Any) -> Row | None:
    return one(ctx.conn, "SELECT * FROM access_grants WHERE request_id = %s", (request_id,))


def grant_held(g: Row) -> dict[str, Any]:
    return {
        "view": "HELD",
        "grant_id": str(g["id"]),
        "request_id": str(g["request_id"]),
        "status": g["state"],
        "starts_at": iso(g["starts_at"]),
        "expires_at": iso(g["expires_at"]),
        "closed_at": iso(g["closed_at"]),
        "close_cause": g["close_cause"],
        "link_id": str(g["link_id"]),
        "far_entity_id": str(g["far_entity_id"]),
    }


def grant_authority(ctx: Ctx, g: Row) -> dict[str, Any]:
    return {
        "view": "AUTHORITY",
        "grant_id": str(g["id"]),
        "request_id": str(g["request_id"]),
        "status": g["state"],
        "starts_at": iso(g["starts_at"]),
        "expires_at": iso(g["expires_at"]),
        "closed_at": iso(g["closed_at"]),
        "close_cause": g["close_cause"],
        "holder": _user_ref(ctx, g["holder_id"]),
        "far_case_id": str(g["far_case_id"]),
    }


def request_mine(ctx: Ctx, r: Row) -> dict[str, Any]:
    stub = one(ctx.conn, "SELECT * FROM stubs WHERE stub_id = %s", (r["stub_id"],))
    stub = need(stub)
    status, at = stub_request_state(ctx, stub["stub_id"])
    grant = _grant_for_request(ctx, r["id"])
    return {
        "view": "MINE",
        "request_id": str(r["id"]),
        "status": r["state"],
        "requested_at": iso(r["requested_at"]),
        "expires_at": iso(r["expires_at"]),
        "decided_at": iso(r["decided_at"]),
        "decision_note": r["decision_note"],
        "stub": stub_out(stub, status, at),
        "grant": grant_held(grant) if grant else None,
    }


def approver_stub(ctx: Ctx, r: Row) -> dict[str, Any]:
    """The approver's own stub for the link, with `near_entity_id` on the far-case side. The
    requester's stub id and entity are never shown."""
    mine = one(
        ctx.conn,
        "SELECT * FROM stubs WHERE holder_user_id = %s AND link_id = %s",
        (uuid.UUID(ctx.me.user_id), r["link_id"]),
    )
    if mine is None:
        link = link_row(ctx, str(r["link_id"]))
        link = need(link)
        far_entity = (
            link["entity_a_id"] if link["case_a_id"] == r["far_case_id"] else link["entity_b_id"]
        )
        mine = one(
            ctx.conn,
            "INSERT INTO stubs (holder_user_id, link_id, near_entity_id) VALUES (%s, %s, %s) "
            "RETURNING *",
            (uuid.UUID(ctx.me.user_id), r["link_id"], far_entity),
        )
    mine = need(mine)
    return stub_out(mine, "NONE", None)


def _case_number(ctx: Ctx, case_id: Any) -> str:
    row = one(ctx.conn, "SELECT case_number FROM cases WHERE id = %s", (case_id,))
    if row is None:  # the far case row exists as long as the request does
        raise LookupError("far case missing")
    return str(row["case_number"])


def request_to_decide(ctx: Ctx, r: Row) -> dict[str, Any]:
    grant = _grant_for_request(ctx, r["id"])
    return {
        "view": "TO_DECIDE",
        "request_id": str(r["id"]),
        "status": r["state"],
        "requested_at": iso(r["requested_at"]),
        "expires_at": iso(r["expires_at"]),
        "decided_at": iso(r["decided_at"]),
        "reason": r["reason"],
        "requester": _user_ref(ctx, r["requester_id"]),
        "far_case_id": str(r["far_case_id"]),
        "far_case_number": _case_number(ctx, r["far_case_id"]),
        "stub": approver_stub(ctx, r),
        "grant": grant_authority(ctx, grant) if grant else None,
    }


def _request_by_id(ctx: Ctx, request_id: str) -> Row | None:
    key = as_uuid(request_id)
    if key is None:
        return None
    return one(ctx.conn, "SELECT * FROM access_requests WHERE id = %s", (key,))


def _district_of(ctx: Ctx, case_id: Any) -> str:
    facts = ctx.case_facts([str(case_id)])
    return facts[str(case_id)].district_id


def _visible_request(ctx: Ctx, r: Row | None) -> str | None:
    """'REQUESTER', 'AUTHORITY' or None when the request does not exist for the caller."""
    if r is None:
        return None
    if str(r["requester_id"]) == ctx.me.user_id:
        return "REQUESTER"
    if _authority(ctx, _district_of(ctx, r["far_case_id"])):
        return "AUTHORITY"
    return None


def _audit_request_view(ctx: Ctx, rows: list[Row], views: list[dict[str, Any]]) -> None:
    cases: list[str] = []
    for r in rows:
        cases += [str(r["near_case_id"]), str(r["far_case_id"])]
    stub_ids = [v["stub"]["stub_id"] for v in views]
    ctx.audit(
        "ACCESS_REQUEST_VIEWED",
        refs=cases,
        detail={
            "request_ids": [v["request_id"] for v in views],
            "stub_ids": stub_ids,
            "near_entity_ids": sorted({v["stub"]["near_entity_id"] for v in views}),
        },
    )


# ---------------------------------------------------------------------------------------------
# stubs


@endpoint(router, "GET", "/stubs/{stub_id}", policy=OFFICER, audit_event="STUB_VIEWED")
def get_stub(stub_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    key = as_uuid(stub_id)
    row = (
        one(
            ctx.conn,
            "SELECT * FROM stubs WHERE stub_id = %s AND holder_user_id = %s",
            (key, uuid.UUID(ctx.me.user_id)),
        )
        if key
        else None
    )
    f = None
    if row is not None:
        link = link_row(ctx, str(row["link_id"]))
        f = link_facts(ctx, [link])[0] if link else None
    if row is None or f is None or f.access is not LinkAccess.REDACTED:
        raise ctx.not_found(stub_id, resolved=stub_id if row else None)
    status, at = stub_request_state(ctx, row["stub_id"])
    near_case = ctx.case_facts([str(f.row["case_a_id"]), str(f.row["case_b_id"])])
    del near_case
    ctx.audit(
        "STUB_VIEWED",
        refs=link_cases(f),
        detail={
            "stub_ids": [str(row["stub_id"])],
            "near_entity_ids": [str(row["near_entity_id"])],
            "via_grant": False,
        },
    )
    return stub_out(row, status, at)


# ---------------------------------------------------------------------------------------------
# access requests


@endpoint(
    router,
    "POST",
    "/access-requests",
    policy=OFFICER,
    audit_event="ACCESS_REQUEST_CREATED",
    status_code=201,
)
def create_access_request(ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    import json

    try:
        raw = json.loads(getattr(ctx.request.state, "body", b"") or b"{}")
    except ValueError:
        raw = {}
    supplied = str(raw.get("stub_id", "")) if isinstance(raw, dict) else ""
    key = as_uuid(supplied)
    stub = (
        one(
            ctx.conn,
            "SELECT * FROM stubs WHERE stub_id = %s AND holder_user_id = %s",
            (key, uuid.UUID(ctx.me.user_id)),
        )
        if key
        else None
    )
    link = link_row(ctx, str(stub["link_id"])) if stub else None
    f = link_facts(ctx, [link])[0] if link else None
    if stub is None or f is None or f.access is not LinkAccess.REDACTED:
        raise ctx.not_found(supplied, resolved=supplied if stub else None)
    body = ctx.body(CreateBody)
    near_case, far_case = _near_far(ctx, f)
    pending = one(
        ctx.conn,
        "SELECT count(*) AS n FROM access_requests WHERE requester_id = %s AND state = 'PENDING'",
        (uuid.UUID(ctx.me.user_id),),
    )
    if pending and int(pending["n"]) >= MAX_PENDING:
        raise ApiError("REQUEST_LIMIT")
    if one(
        ctx.conn,
        "SELECT 1 AS x FROM access_requests WHERE stub_id = %s AND state = 'PENDING'",
        (stub["stub_id"],),
    ):
        raise ApiError("REQUEST_LIMIT")
    denied = one(
        ctx.conn,
        "SELECT decided_at FROM access_requests WHERE stub_id = %s AND state = 'DENIED' "
        "ORDER BY decided_at DESC LIMIT 1",
        (stub["stub_id"],),
    )
    if denied and ctx.now() - denied["decided_at"] < COOLDOWN:
        raise ApiError("REQUEST_COOLDOWN")
    now = ctx.now()
    created = one(
        ctx.conn,
        "INSERT INTO access_requests (requester_id, stub_id, link_id, near_case_id, far_case_id, "
        "reason, state, requested_at, expires_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, 'PENDING', %s, %s) "
        "RETURNING *",
        (
            uuid.UUID(ctx.me.user_id),
            stub["stub_id"],
            stub["link_id"],
            uuid.UUID(near_case),
            uuid.UUID(far_case),
            body.reason,
            now,
            now + timedelta(days=REQUEST_DAYS),
        ),
    )
    created = need(created)
    ctx.audit(
        "ACCESS_REQUEST_CREATED",
        refs=[near_case, far_case],
        target_type="ACCESS_REQUEST",
        target_id=str(created["id"]),
        detail={"stub_id": str(stub["stub_id"])},
    )
    return request_mine(ctx, created)


def _near_far(ctx: Ctx, f: LinkFacts) -> tuple[str, str]:
    if ctx.me.can_view_case(f.a.case_id, f.a.district_id):
        return f.a.case_id, f.b.case_id
    return f.b.case_id, f.a.case_id


@endpoint(router, "GET", "/access-requests", policy=OFFICER, audit_event="ACCESS_REQUEST_VIEWED")
def list_access_requests(
    ctx: Ctx = Depends(authed_ctx),
    scope: str = Query("mine"),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
) -> dict[str, Any]:
    if scope not in ("mine", "to_decide"):
        raise invalid("scope", "invalid_enum")
    if status is not None and status not in (
        "PENDING",
        "APPROVED",
        "DENIED",
        "WITHDRAWN",
        "EXPIRED",
    ):
        raise invalid("status", "invalid_enum")
    me = ctx.me
    if scope == "to_decide" and not me.at_least("SUPERVISOR"):
        raise ctx.forbidden(None, None)
    rows = many(ctx.conn, "SELECT * FROM access_requests ORDER BY requested_at DESC, id")
    if scope == "mine":
        rows = [r for r in rows if str(r["requester_id"]) == me.user_id]
    else:
        rows = [
            r
            for r in rows
            if str(r["requester_id"]) != me.user_id
            and _authority(ctx, _district_of(ctx, r["far_case_id"]))
        ]
    if status:
        rows = [r for r in rows if r["state"] == status]
    chunk, token = page_slice(
        ctx, rows, limit, cursor, {"scope": scope, "status": status}, "requests"
    )
    views = [request_mine(ctx, r) if scope == "mine" else request_to_decide(ctx, r) for r in chunk]
    _audit_request_view(ctx, list(chunk), views)
    return {"items": views, "next_cursor": token, "total": len(rows)}


@endpoint(
    router,
    "GET",
    "/access-requests/{request_id}",
    policy=OFFICER,
    audit_event="ACCESS_REQUEST_VIEWED",
)
def get_access_request(request_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    r = _request_by_id(ctx, request_id)
    who = _visible_request(ctx, r)
    if r is None or who is None:
        raise ctx.not_found(request_id, resolved=request_id if r else None)
    view = request_mine(ctx, r) if who == "REQUESTER" else request_to_decide(ctx, r)
    _audit_request_view(ctx, [r], [view])
    return view


@endpoint(
    router,
    "POST",
    "/access-requests/{request_id}/withdraw",
    policy=OFFICER,
    audit_event="ACCESS_REQUEST_WITHDRAWN",
)
def withdraw_access_request(request_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    r = _request_by_id(ctx, request_id)
    if r is None or str(r["requester_id"]) != ctx.me.user_id:
        raise ctx.not_found(request_id, resolved=request_id if r else None)
    if r["state"] != "PENDING":
        raise ApiError("NOT_PENDING")
    ctx.conn.execute("UPDATE access_requests SET state = 'WITHDRAWN' WHERE id = %s", (r["id"],))
    ctx.audit(
        "ACCESS_REQUEST_WITHDRAWN",
        refs=[str(r["near_case_id"]), str(r["far_case_id"])],
        target_type="ACCESS_REQUEST",
        target_id=str(r["id"]),
        detail={"stub_id": str(r["stub_id"])},
    )
    fresh = _request_by_id(ctx, request_id)
    fresh = need(fresh)
    return request_mine(ctx, fresh)


def _decidable(ctx: Ctx, request_id: str) -> Row:
    """Visible to the caller, not their own, with authority: else 404 or 403 in R2 order."""
    r = _request_by_id(ctx, request_id)
    who = _visible_request(ctx, r)
    if r is None or who is None:
        raise ctx.not_found(request_id, resolved=request_id if r else None)
    cases = [str(r["near_case_id"]), str(r["far_case_id"])]
    if who == "REQUESTER" or not ctx.me.at_least("SUPERVISOR"):
        raise ctx.forbidden("ACCESS_REQUEST", str(r["id"]), cases)
    return r


def _still_redacted_for(ctx: Ctx, requester: Row, link: Row) -> bool:
    """The request was made when the link was a stub for the requester; approve only if it still
    is (the requester is active and still sees exactly their own side)."""
    if not requester["active"]:
        return False
    principal = load_principal(ctx, requester, "")
    a, b = ctx.case_facts([str(link["case_a_id"]), str(link["case_b_id"])]).values()
    return link_access(principal, str(link["link_id"]), link["state"], a, b) is LinkAccess.REDACTED


@endpoint(
    router,
    "POST",
    "/access-requests/{request_id}/approve",
    policy=OFFICER,
    audit_event="ACCESS_REQUEST_APPROVED",
)
def approve_access_request(request_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    r = _decidable(ctx, request_id)
    if r["state"] != "PENDING":
        raise ApiError("NOT_PENDING")
    body = ctx.body(ApproveBody)
    if body.duration_days not in (7, 30, 90):
        raise invalid("duration_days", "invalid_enum")
    link = link_row(ctx, str(r["link_id"]))
    link = need(link)
    if link["state"] not in ("AUTO", "SUGGESTED", "CONFIRMED"):
        raise ApiError("INVALID_TRANSITION")
    requester = one(ctx.conn, "SELECT * FROM users WHERE id = %s", (r["requester_id"],))
    requester = need(requester)
    if not _still_redacted_for(ctx, requester, link):
        raise ApiError("INVALID_TRANSITION")
    far_entity = (
        link["entity_a_id"] if link["case_a_id"] == r["far_case_id"] else link["entity_b_id"]
    )
    now = ctx.now()
    grant = one(
        ctx.conn,
        "INSERT INTO access_grants (request_id, holder_id, link_id, far_entity_id, far_case_id, "
        "state, starts_at, expires_at, role_at_grant) "
        "VALUES (%s, %s, %s, %s, %s, 'ACTIVE', %s, %s, %s) "
        "RETURNING *",
        (
            r["id"], r["requester_id"], r["link_id"], far_entity, r["far_case_id"],
            now, now + timedelta(days=body.duration_days), requester["role"],
        ),
    )  # fmt: skip
    grant = need(grant)
    if requester["role"] != "JUNIOR":
        ctx.conn.execute(
            "INSERT INTO grant_line_ranges (grant_id, document_id, line_from, line_to) "
            "SELECT %s, c.document_id, c.line_from, c.line_to FROM link_cited_lines c "
            "JOIN documents d ON d.id = c.document_id WHERE c.link_id = %s AND d.case_id = %s",
            (grant["id"], r["link_id"], r["far_case_id"]),
        )
    ctx.conn.execute(
        "UPDATE access_requests SET state = 'APPROVED', decided_by = %s, decided_at = %s "
        "WHERE id = %s",
        (uuid.UUID(ctx.me.user_id), now, r["id"]),
    )
    ctx.audit(
        "ACCESS_REQUEST_APPROVED",
        refs=[str(r["near_case_id"]), str(r["far_case_id"])],
        target_type="ACCESS_REQUEST",
        target_id=str(r["id"]),
        detail={"grant_id": str(grant["id"]), "expires_at": iso(grant["expires_at"])},
    )
    fresh = _request_by_id(ctx, request_id)
    fresh = need(fresh)
    return request_to_decide(ctx, fresh)


@endpoint(
    router,
    "POST",
    "/access-requests/{request_id}/deny",
    policy=OFFICER,
    audit_event="ACCESS_REQUEST_REJECTED",
)
def deny_access_request(request_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    r = _decidable(ctx, request_id)
    if r["state"] != "PENDING":
        raise ApiError("NOT_PENDING")
    body = ctx.body(DenyBody)
    ctx.conn.execute(
        "UPDATE access_requests SET state = 'DENIED', decided_by = %s, decided_at = %s, "
        "decision_note = %s WHERE id = %s",
        (uuid.UUID(ctx.me.user_id), ctx.now(), body.note, r["id"]),
    )
    ctx.audit(
        "ACCESS_REQUEST_REJECTED",
        refs=[str(r["near_case_id"]), str(r["far_case_id"])],
        target_type="ACCESS_REQUEST",
        target_id=str(r["id"]),
    )
    fresh = _request_by_id(ctx, request_id)
    fresh = need(fresh)
    return request_to_decide(ctx, fresh)


# ---------------------------------------------------------------------------------------------
# grants


def _grant_by_id(ctx: Ctx, grant_id: str) -> Row | None:
    key = as_uuid(grant_id)
    return one(ctx.conn, "SELECT * FROM access_grants WHERE id = %s", (key,)) if key else None


def _grant_ends(ctx: Ctx, g: Row) -> list[str]:
    link = link_row(ctx, str(g["link_id"]))
    link = need(link)
    return [str(link["case_a_id"]), str(link["case_b_id"])]


def _grant_role(ctx: Ctx, g: Row | None) -> str | None:
    if g is None:
        return None
    if str(g["holder_id"]) == ctx.me.user_id:
        return "HOLDER"
    if _authority(ctx, _district_of(ctx, g["far_case_id"])):
        return "AUTHORITY"
    return None


@endpoint(router, "GET", "/grants", policy=OFFICER, audit_event="GRANT_VIEWED")
def list_grants(
    ctx: Ctx = Depends(authed_ctx),
    scope: str = Query("held"),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
) -> dict[str, Any]:
    if scope not in ("held", "authority"):
        raise invalid("scope", "invalid_enum")
    if status is not None and status not in ("ACTIVE", "EXPIRED", "REVOKED"):
        raise invalid("status", "invalid_enum")
    if scope == "authority" and not ctx.me.at_least("SUPERVISOR"):
        raise ctx.forbidden(None, None)
    rows = many(ctx.conn, "SELECT * FROM access_grants ORDER BY starts_at DESC, id")
    if scope == "held":
        rows = [g for g in rows if str(g["holder_id"]) == ctx.me.user_id]
    else:
        rows = [
            g for g in rows
            if str(g["holder_id"]) != ctx.me.user_id
            and _authority(ctx, _district_of(ctx, g["far_case_id"]))
        ]  # fmt: skip
    if status:
        rows = [g for g in rows if g["state"] == status]
    chunk, token = page_slice(
        ctx, rows, limit, cursor, {"scope": scope, "status": status}, "grants"
    )
    items = [grant_held(g) if scope == "held" else grant_authority(ctx, g) for g in chunk]
    ctx.audit(
        "GRANT_VIEWED",
        refs=[c for g in chunk for c in _grant_ends(ctx, g)],
        detail={
            "grant_ids": [str(g["id"]) for g in chunk],
            "link_ids": [str(g["link_id"]) for g in chunk],
        },
    )
    return {"items": items, "next_cursor": token, "total": len(rows)}


@endpoint(router, "GET", "/grants/{grant_id}", policy=OFFICER, audit_event="GRANT_VIEWED")
def get_grant(grant_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    g = _grant_by_id(ctx, grant_id)
    who = _grant_role(ctx, g)
    if g is None or who is None:
        raise ctx.not_found(grant_id, resolved=grant_id if g else None)
    ctx.audit(
        "GRANT_VIEWED",
        refs=_grant_ends(ctx, g),
        detail={"grant_ids": [str(g["id"])], "link_ids": [str(g["link_id"])]},
    )
    return grant_held(g) if who == "HOLDER" else grant_authority(ctx, g)


@endpoint(
    router, "POST", "/grants/{grant_id}/revoke", policy=OFFICER, audit_event="ACCESS_GRANT_REVOKED"
)
def revoke_grant(grant_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    g = _grant_by_id(ctx, grant_id)
    who = _grant_role(ctx, g)
    if g is None or who is None:
        raise ctx.not_found(grant_id, resolved=grant_id if g else None)
    ends = _grant_ends(ctx, g)
    if who == "HOLDER" or not ctx.me.at_least("SUPERVISOR"):
        raise ctx.forbidden("GRANT", str(g["id"]), ends)
    if g["state"] != "ACTIVE":
        raise ApiError("NOT_PENDING")
    close_grant(ctx, g["id"], "MANUAL", str(g["link_id"]), ends[0], ends[1], "ACCESS_GRANT_REVOKED")
    fresh = _grant_by_id(ctx, grant_id)
    fresh = need(fresh)
    return grant_authority(ctx, fresh)
