"""The review queue: links awaiting or open to a human decision, ALLOW items only."""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query

from tracex_api.context import OFFICER, Ctx, authed_ctx, endpoint, iso
from tracex_api.db import many
from tracex_api.errors import invalid
from tracex_api.policy import LinkAccess, allowed_actions
from tracex_api.views import as_uuid, link_cases, link_facts, link_summaries, page_slice

router = APIRouter()


@endpoint(router, "GET", "/review-queue", policy=OFFICER, audit_event="REVIEW_QUEUE_VIEWED")
def list_review_queue(
    ctx: Ctx = Depends(authed_ctx),
    state: str = Query("SUGGESTED"),
    entity_type: str | None = Query(None),
    district_id: str | None = Query(None),
    waiting_days_min: int | None = Query(None, ge=1, le=365),
    sort: str = Query("waiting_since"),
    order: str = Query("asc"),
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
) -> dict[str, Any]:
    if state not in ("SUGGESTED", "REJECTED", "UNDONE"):
        raise invalid("state", "invalid_enum")
    if sort not in ("waiting_since", "score", "entity_type"):
        raise invalid("sort", "invalid_enum")
    if order not in ("asc", "desc"):
        raise invalid("order", "invalid_enum")
    if entity_type is not None and entity_type not in (
        "PERSON",
        "ORG",
        "PHONE",
        "ACCOUNT",
        "VEHICLE",
    ):
        raise invalid("entity_type", "invalid_enum")
    if district_id is not None and as_uuid(district_id) is None:
        raise invalid("district_id", "invalid_uuid")
    rows = many(ctx.conn, "SELECT * FROM links WHERE state = %s", (state,))
    since: dict[str, Any] = {}
    for r in many(
        ctx.conn,
        "SELECT link_id, max(at) AS at FROM link_history WHERE to_state = %s GROUP BY link_id",
        (state,),
    ):
        since[str(r["link_id"])] = r["at"]
    items = []
    now = ctx.now()
    for f in link_facts(ctx, rows):
        if f.access is not LinkAccess.ALLOW or f.via_grant:
            continue
        if entity_type and f.row["entity_type"] != entity_type:
            continue
        if district_id and district_id.lower() not in (f.a.district_id, f.b.district_id):
            continue
        waiting = since.get(f.link_id) or f.row["created_at"]
        if waiting_days_min and now - waiting < timedelta(days=waiting_days_min):
            continue
        items.append((f, waiting))
    keys = {
        "waiting_since": lambda t: (t[1], t[0].link_id),
        "score": lambda t: (t[0].row["score"], t[0].link_id),
        "entity_type": lambda t: (t[0].row["entity_type"], t[0].link_id),
    }
    items.sort(key=keys[sort], reverse=order == "desc")
    filters = {
        "state": state, "entity_type": entity_type, "district": district_id,
        "days": waiting_days_min, "sort": sort, "order": order,
    }  # fmt: skip
    chunk, token = page_slice(ctx, items, limit, cursor, filters, "queue")
    summaries = link_summaries(ctx, [f for f, _ in chunk])
    out = []
    for (f, waiting), summary in zip(chunk, summaries, strict=True):
        out.append(
            {
                **summary,
                "waiting_since": iso(waiting),
                "allowed_actions": allowed_actions(ctx.me, f.row["state"], f.a, f.b, False),
            }
        )
    ctx.audit(
        "REVIEW_QUEUE_VIEWED",
        refs=[c for f, _ in chunk for c in link_cases(f)],
        detail={"link_ids": [f.link_id for f, _ in chunk]},
    )
    return {"items": out, "next_cursor": token, "total": len(items)}
