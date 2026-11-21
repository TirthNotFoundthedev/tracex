"""Links, explanations and human decisions (confirm, reject, undo, reopen)."""

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from tracex_api.context import OFFICER, Ctx, authed_ctx, endpoint
from tracex_api.db import many, need, one
from tracex_api.engine_bridge import close_grants_if_needed, run_in_progress, send_decision
from tracex_api.errors import ApiError, invalid
from tracex_api.policy import DECISIONS, LinkAccess, decision_block
from tracex_api.views import (
    LinkFacts,
    as_uuid,
    entity_row,
    explanation_payload,
    facts_for_links_of,
    hidden_or_404,
    link_cases,
    link_detail,
    link_facts,
    link_summaries,
    one_link_facts,
    page_slice,
    stubs_for,
)

router = APIRouter()
LINK_STATES = ("AUTO", "SUGGESTED", "CONFIRMED", "REJECTED", "UNDONE")
DECISION_EVENTS = {
    "CONFIRM": "LINK_CONFIRMED",
    "REJECT": "LINK_REJECTED",
    "UNDO": "LINK_UNDONE",
    "REOPEN": "LINK_REOPENED",
}
ENTITY_TYPES = ("PERSON", "ORG", "PHONE", "ACCOUNT", "VEHICLE")


class ConfirmBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_state: str | None = None


class ReasonBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=1000)
    expected_state: str | None = None


@endpoint(router, "GET", "/links", policy=OFFICER, audit_event="LINKS_LISTED")
def list_links(
    ctx: Ctx = Depends(authed_ctx),
    entity_id: str | None = Query(None),
    state: str | None = Query(None),
    entity_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
) -> dict[str, Any]:
    if state is not None and state not in LINK_STATES:
        raise invalid("state", "invalid_enum")
    if entity_type is not None and entity_type not in ENTITY_TYPES:
        raise invalid("entity_type", "invalid_enum")
    if entity_id is not None:
        entity = entity_row(ctx, entity_id)
        if entity is None or not ctx.me.can_view_case(
            str(entity["case_id"]), str(entity["district_id"])
        ):
            raise ctx.not_found(entity_id, resolved=str(entity["id"]) if entity else None)
        facts = facts_for_links_of(ctx, [entity_id])
    else:
        rows = many(
            ctx.conn,
            "SELECT * FROM links WHERE state <> 'WITHDRAWN' ORDER BY updated_at DESC, link_id",
        )
        facts = link_facts(ctx, rows)
    stub_facts = [f for f in facts if f.access is LinkAccess.REDACTED]
    visible = [f for f in facts if f.access is LinkAccess.ALLOW]
    wanted = {state} if state else {"AUTO", "SUGGESTED", "CONFIRMED"}
    visible = [f for f in visible if f.row["state"] in wanted]
    if entity_type:
        visible = [f for f in visible if f.row["entity_type"] == entity_type]
    chunk, token = page_slice(
        ctx,
        visible,
        limit,
        cursor,
        {"state": state, "entity_type": entity_type, "entity": entity_id},
        "links",
    )
    stubs = stubs_for(ctx, stub_facts)
    cases = [c for f in list(chunk) + stub_facts for c in link_cases(f)]
    ctx.audit(
        "LINKS_LISTED",
        refs=cases,
        detail={"link_ids": [f.link_id for f in chunk], "stub_ids": [s["stub_id"] for s in stubs]},
    )
    if stubs:
        ctx.audit(
            "STUB_VIEWED",
            refs=cases,
            detail={
                "stub_ids": [s["stub_id"] for s in stubs],
                "near_entity_ids": sorted({s["near_entity_id"] for s in stubs}),
                "via_grant": False,
            },
        )
    return {
        "items": link_summaries(ctx, list(chunk)),
        "stubs": stubs,
        "next_cursor": token,
        "total": len(visible),
    }


@endpoint(router, "GET", "/links/{link_id}", policy=OFFICER, audit_event="LINK_VIEWED")
def get_link(link_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    f = one_link_facts(ctx, link_id)
    f = hidden_or_404(ctx, link_id, f, resolved=link_id if f else None)
    ctx.audit(
        "LINK_VIEWED",
        refs=link_cases(f),
        target_type="LINK",
        target_id=f.link_id,
        reason_code="GRANT_ACTIVE" if f.via_grant else None,
        detail={"via_grant": f.via_grant},
    )
    return link_detail(ctx, f)


@endpoint(
    router, "GET", "/links/{link_id}/explanation", policy=OFFICER, audit_event="EXPLANATION_VIEWED"
)
def get_explanation(link_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    f = one_link_facts(ctx, link_id)
    f = hidden_or_404(ctx, link_id, f, resolved=link_id if f else None)
    payload = explanation_payload(ctx, f)
    ctx.audit(
        "EXPLANATION_VIEWED",
        refs=link_cases(f),
        target_type="LINK",
        target_id=f.link_id,
        reason_code="GRANT_ACTIVE" if f.via_grant else None,
        detail={"via_grant": f.via_grant},
    )
    return payload


def _decide(ctx: Ctx, link_id: str, action: str) -> dict[str, Any]:
    f = one_link_facts(ctx, link_id)
    f = hidden_or_404(ctx, link_id, f, resolved=link_id if f else None)
    cases = link_cases(f)
    block = decision_block(ctx.me, action, f.a, f.b, f.via_grant)
    if block:
        raise ctx.forbidden(
            "LINK",
            f.link_id,
            cases,
            reason_code="GRANT_ACTIVE" if block == "GRANT_READ_ONLY" else "MATRIX_DENY",
        )
    _, starts, target = DECISIONS[action]
    try:
        raw = json.loads(getattr(ctx.request.state, "body", b"") or b"{}")
    except ValueError:
        raw = {}
    expected = raw.get("expected_state") if isinstance(raw, dict) else None
    state_now = f.row["state"]
    if state_now not in starts:
        raise ApiError("INVALID_TRANSITION")
    if isinstance(expected, str) and expected != state_now:
        raise ApiError("STATE_MISMATCH")
    body = ctx.body(ConfirmBody if action == "CONFIRM" else ReasonBody)
    reason = getattr(body, "reason", None)
    if run_in_progress(ctx.conn):
        raise ApiError("RUN_IN_PROGRESS")
    locked = one(ctx.conn, "SELECT * FROM links WHERE link_id = %s FOR UPDATE", (f.row["link_id"],))
    locked = need(locked)
    if locked["state"] != state_now:
        raise ApiError("STATE_MISMATCH")
    decision_id = uuid.uuid4()
    now = ctx.now()
    ctx.conn.execute(
        "UPDATE links SET state = %s, updated_at = %s WHERE link_id = %s",
        (target, now, locked["link_id"]),
    )
    ctx.conn.execute(
        "INSERT INTO link_history (link_id, from_state, to_state, actor_kind, actor_user_id, at, "
        "reason_text, decision_id) VALUES (%s, %s, %s, 'USER', %s, %s, %s, %s)",
        (locked["link_id"], state_now, target, uuid.UUID(ctx.me.user_id), now, reason, decision_id),
    )
    ctx.conn.execute(
        "INSERT INTO decision_outbox (decision_id, link_id, expected_from, to_state, "
        "actor_user_id, "
        "reason_text) VALUES (%s, %s, %s, %s, %s, %s)",
        (decision_id, locked["link_id"], state_now, target, uuid.UUID(ctx.me.user_id), reason),
    )
    close_grants_if_needed(ctx, f.link_id, target, f.a.case_id, f.b.case_id)
    ctx.audit(
        DECISION_EVENTS[action],
        refs=cases,
        target_type="LINK",
        target_id=f.link_id,
        detail={"previous_state": state_now, "new_state": target},
    )
    ctx.commit()
    send_decision(ctx.state, ctx.conn, str(decision_id))
    fresh = one_link_facts(ctx, link_id)
    fresh = need(fresh)
    return link_detail(ctx, fresh)


@endpoint(router, "POST", "/links/{link_id}/confirm", policy=OFFICER, audit_event="LINK_CONFIRMED")
def confirm_link(link_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    return _decide(ctx, link_id, "CONFIRM")


@endpoint(router, "POST", "/links/{link_id}/reject", policy=OFFICER, audit_event="LINK_REJECTED")
def reject_link(link_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    return _decide(ctx, link_id, "REJECT")


@endpoint(router, "POST", "/links/{link_id}/undo", policy=OFFICER, audit_event="LINK_UNDONE")
def undo_link(link_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    return _decide(ctx, link_id, "UNDO")


@endpoint(router, "POST", "/links/{link_id}/reopen", policy=OFFICER, audit_event="LINK_REOPENED")
def reopen_link(link_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    return _decide(ctx, link_id, "REOPEN")


__all__ = ["LinkFacts", "as_uuid", "router"]
