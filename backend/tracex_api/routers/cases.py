"""Cases, entities, search and source lines (the "View ..." rows of the permission matrix)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from tracex_api.context import OFFICER, Ctx, authed_ctx, endpoint, iso
from tracex_api.db import Row, many, need, one
from tracex_api.errors import invalid
from tracex_api.policy import MASKED_TYPES, LinkAccess
from tracex_api.views import (
    as_uuid,
    case_ref,
    case_row,
    case_visible,
    counts_as_connection,
    entity_row,
    entity_summaries,
    entity_summary,
    facts_for_links_of,
    grant_far_entity,
    has_full_values,
    link_cases,
    link_summaries,
    page_slice,
    stubs_for,
)

router = APIRouter()
MAX_AUDITED_IDS = 500
MAX_LINES = 200


def visible_case_rows(ctx: Ctx) -> list[Row]:
    me = ctx.me
    rows = many(
        ctx.conn,
        "SELECT c.*, d.name AS district_name FROM cases c JOIN districts d ON d.id = c.district_id "
        "ORDER BY c.case_number, c.id",
    )
    return [r for r in rows if me.can_view_case(str(r["id"]), str(r["district_id"]))]


def case_summary(ctx: Ctx, row: Row, linked: int) -> dict[str, Any]:
    return {
        **case_ref(row),
        "opened_on": str(row["opened_on"]),
        "linked_item_count": linked,
        "is_assigned": str(row["id"]) in ctx.me.assigned_cases,
    }


def linked_counts(ctx: Ctx, case_ids: list[str]) -> dict[str, int]:
    keys = [uuid.UUID(c) for c in case_ids]
    if not keys:
        return {}
    from tracex_api.views import link_facts

    rows = many(
        ctx.conn,
        "SELECT * FROM links WHERE (case_a_id = ANY(%s) OR case_b_id = ANY(%s)) "
        "AND state <> 'WITHDRAWN'",
        (keys, keys),
    )
    counts = dict.fromkeys(case_ids, 0)
    for f in link_facts(ctx, rows):
        if counts_as_connection(f):
            for case in link_cases(f):
                if case in counts:
                    counts[case] += 1
    return counts


@endpoint(router, "GET", "/cases", policy=OFFICER, audit_event="CASE_LISTED")
def list_cases(
    ctx: Ctx = Depends(authed_ctx),
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
    case_number: str | None = Query(None, max_length=64),
    district_id: str | None = Query(None),
) -> dict[str, Any]:
    if district_id is not None and as_uuid(district_id) is None:
        raise invalid("district_id", "invalid_uuid")
    rows = visible_case_rows(ctx)
    if case_number:
        rows = [r for r in rows if r["case_number"].lower().startswith(case_number.lower())]
    if district_id:
        rows = [r for r in rows if str(r["district_id"]) == district_id.lower()]
    filters = {"case_number": case_number, "district_id": district_id}
    chunk, token = page_slice(ctx, rows, limit, cursor, filters, "cases")
    counts = linked_counts(ctx, [str(r["id"]) for r in chunk])
    items = [case_summary(ctx, r, counts[str(r["id"])]) for r in chunk]
    shown = [str(r["id"]) for r in chunk][:MAX_AUDITED_IDS]
    ctx.audit("CASE_LISTED", refs=shown, detail={"case_ids": shown})
    return {"items": items, "next_cursor": token, "total": len(rows)}


@endpoint(
    router, "GET", "/cases/{case_id}/entities", policy=OFFICER, audit_event="CASE_ENTITIES_VIEWED"
)
def list_case_entities(
    case_id: str,
    ctx: Ctx = Depends(authed_ctx),
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
    type: str | None = Query(None),  # noqa: A002 - the contract names the parameter `type`
) -> dict[str, Any]:
    case = case_row(ctx, case_id)
    if case is None or not case_visible(ctx, case):
        raise ctx.not_found(case_id, resolved=str(case["id"]) if case else None)
    if type is not None and type not in ("PERSON", "ORG", "PHONE", "ACCOUNT", "VEHICLE"):
        raise invalid("type", "invalid_enum")
    rows = many(
        ctx.conn,
        "SELECT e.*, c.district_id, c.case_number, c.title FROM entities e "
        "JOIN cases c ON c.id = e.case_id WHERE e.case_id = %s ORDER BY e.type, e.engine_entity_id",
        (case["id"],),
    )
    by_type: dict[str, int] = {}
    for r in rows:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
    if type:
        rows = [r for r in rows if r["type"] == type]
    chunk, token = page_slice(
        ctx, rows, limit, cursor, {"type": type, "case": case_id}, "case_entities"
    )
    items = entity_summaries(ctx, chunk)
    counts = linked_counts(ctx, [str(case["id"])])
    ctx.audit(
        "CASE_ENTITIES_VIEWED",
        refs=[str(case["id"])],
        target_type="CASE",
        target_id=str(case["id"]),
        detail={
            "entity_ids": [i["entity_id"] for i in items][:MAX_AUDITED_IDS],
            "via_grant": False,
        },
    )
    return {
        "case": case_summary(ctx, case, counts[str(case["id"])]),
        "counts_by_type": by_type,
        "items": items,
        "next_cursor": token,
        "total": len(rows),
    }


def provenance_of(ctx: Ctx, entity: Row, only_cited_for: Any | None = None) -> list[dict[str, Any]]:
    rows = many(
        ctx.conn,
        "SELECT m.line, m.document_id, d.doc_type, d.case_id, "
        "(SELECT page FROM document_lines l WHERE l.document_id = m.document_id "
        "AND l.line_no = m.line) AS page "
        "FROM entity_mentions m JOIN documents d ON d.id = m.document_id "
        "WHERE m.entity_id = %s ORDER BY d.file_name, m.line",
        (entity["id"],),
    )
    if only_cited_for is not None:
        cited = many(
            ctx.conn,
            "SELECT document_id, line_from, line_to FROM link_cited_lines WHERE link_id = %s",
            (only_cited_for,),
        )
        rows = [
            r
            for r in rows
            if any(
                c["document_id"] == r["document_id"] and c["line_from"] <= r["line"] <= c["line_to"]
                for c in cited
            )
        ]
    return [
        {
            "case_id": str(r["case_id"]),
            "document_id": str(r["document_id"]),
            "line": r["line"],
            "page": r["page"],
            "document_type": r["doc_type"],
        }
        for r in rows
    ]


@endpoint(router, "GET", "/entities/{entity_id}", policy=OFFICER, audit_event="ENTITY_VIEWED")
def get_entity(entity_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    entity = entity_row(ctx, entity_id)
    if entity is None:
        raise ctx.not_found(entity_id)
    case_id, district = str(entity["case_id"]), str(entity["district_id"])
    grant = None
    if not ctx.me.can_view_case(case_id, district):
        grant = grant_far_entity(ctx, entity_id)
        if grant is None:
            raise ctx.not_found(entity_id, resolved=entity_id)
    summary = entity_summary(ctx, entity)
    masked_facts = entity["type"] in MASKED_TYPES and summary["masked"]
    facts = [] if masked_facts else list(entity["facts"])
    case = case_row(ctx, case_id)
    case = need(case)
    if grant is not None:
        granted = link_summaries(ctx, [_granted_facts(ctx, grant)])
        detail = {
            **summary,
            "case": case_ref(case),
            "facts": facts,
            "provenance": provenance_of(ctx, entity, only_cited_for=grant["link_id"]),
            "links": granted,
            "stubs": [],
            "via_grant": True,
        }
        link = _granted_facts(ctx, grant)
        ctx.audit(
            "ENTITY_VIEWED",
            refs=[case_id, *link_cases(link)],
            target_type="ENTITY",
            target_id=entity_id,
            reason_code="GRANT_ACTIVE",
            detail={"link_ids_shown": [link.link_id], "stub_ids_shown": [], "via_grant": True},
        )
        return detail
    facts_all = facts_for_links_of(ctx, [entity_id])
    allowed = [
        f for f in facts_all if f.access is LinkAccess.ALLOW and f.row["state"] != "WITHDRAWN"
    ][:50]
    stubs = stubs_for(ctx, facts_all)
    shown_stub_links = [f for f in facts_all if f.access is LinkAccess.REDACTED]
    cases_in_play = [case_id] + [c for f in allowed + shown_stub_links for c in link_cases(f)]
    ctx.audit(
        "ENTITY_VIEWED",
        refs=cases_in_play,
        target_type="ENTITY",
        target_id=entity_id,
        detail={
            "link_ids_shown": [f.link_id for f in allowed],
            "stub_ids_shown": [s["stub_id"] for s in stubs],
            "via_grant": False,
        },
    )
    if stubs:
        ctx.audit(
            "STUB_VIEWED",
            refs=cases_in_play,
            detail={
                "stub_ids": [s["stub_id"] for s in stubs],
                "near_entity_ids": sorted({s["near_entity_id"] for s in stubs}),
                "via_grant": False,
            },
        )
    return {
        **summary,
        "case": case_ref(case),
        "facts": facts,
        "provenance": provenance_of(ctx, entity),
        "links": link_summaries(ctx, allowed),
        "stubs": stubs,
        "via_grant": False,
    }


def _granted_facts(ctx: Ctx, grant: Row) -> Any:
    from tracex_api.views import link_facts, link_row

    row = link_row(ctx, str(grant["link_id"]))
    row = need(row)
    return link_facts(ctx, [row])[0]


@endpoint(router, "GET", "/search/entities", policy=OFFICER, audit_event="SEARCH_RUN")
def search_entities(
    ctx: Ctx = Depends(authed_ctx),
    q: str = Query(..., min_length=2, max_length=128),
    type: str | None = Query(None),  # noqa: A002
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
) -> dict[str, Any]:
    if type is not None and type not in ("PERSON", "ORG", "PHONE", "ACCOUNT", "VEHICLE"):
        raise invalid("type", "invalid_enum")
    needle = f"%{q.lower().replace('%', '').replace('_', '')}%"
    rows = many(
        ctx.conn,
        "SELECT e.*, c.district_id, c.case_number, c.title FROM entities e "
        "JOIN cases c ON c.id = e.case_id "
        "WHERE (lower(e.normalized_value) LIKE %s OR lower(e.display_value) LIKE %s) "
        "ORDER BY e.type, e.engine_entity_id",
        (needle, needle),
    )
    matches = []
    for r in rows:
        case_id, district = str(r["case_id"]), str(r["district_id"])
        if type and r["type"] != type:
            continue
        if not ctx.me.can_view_case(case_id, district):
            continue
        if r["type"] in MASKED_TYPES and not has_full_values(ctx, case_id, district):
            continue
        matches.append(r)
    chunk, token = page_slice(ctx, matches, limit, cursor, {"q": q.lower(), "type": type}, "search")
    items = entity_summaries(ctx, chunk)
    ids = [i["entity_id"] for i in items][:MAX_AUDITED_IDS]
    detail: dict[str, Any] = {"entity_ids": ids}
    if type:
        detail["entity_type_filter"] = type
    ctx.audit("SEARCH_RUN", refs=[i["case_id"] for i in items], detail=detail)
    return {"items": items, "next_cursor": token, "total": len(matches)}


@endpoint(
    router,
    "GET",
    "/documents/{document_id}/lines",
    policy=OFFICER,
    audit_event="SOURCE_LINES_VIEWED",
)
def get_source_lines(
    document_id: str,
    ctx: Ctx = Depends(authed_ctx),
    line_from: int = Query(..., ge=1),
    line_to: int = Query(..., ge=1),
) -> dict[str, Any]:
    key = as_uuid(document_id)
    doc = (
        one(
            ctx.conn,
            "SELECT d.*, c.district_id FROM documents d JOIN cases c ON c.id = d.case_id "
            "WHERE d.id = %s",
            (key,),
        )
        if key
        else None
    )
    if doc is None:
        raise ctx.not_found(document_id)
    case_id, district = str(doc["case_id"]), str(doc["district_id"])
    via_grant = False
    if ctx.me.can_view_case(case_id, district):
        if not ctx.me.can_read_source(case_id, district):
            raise ctx.forbidden("DOCUMENT", document_id, [case_id])
    else:
        grant = _grant_for_document(ctx, doc)
        if grant is None:
            raise ctx.not_found(document_id, resolved=document_id)
        if ctx.me.role == "JUNIOR":
            raise ctx.forbidden("DOCUMENT", document_id, [case_id], reason_code="GRANT_ROLE_CAP")
        covered = one(
            ctx.conn,
            "SELECT 1 AS x FROM grant_line_ranges WHERE grant_id = %s AND document_id = %s "
            "AND line_from <= %s AND line_to >= %s",
            (grant["id"], doc["id"], line_from, line_to),
        )
        if covered is None:
            raise ctx.forbidden("DOCUMENT", document_id, [case_id], reason_code="GRANT_RANGE")
        via_grant = True
    if line_to < line_from or line_to - line_from + 1 > MAX_LINES:
        raise invalid("line_to", "out_of_range")
    rows = many(
        ctx.conn,
        "SELECT line_no, page, text FROM document_lines WHERE document_id = %s "
        "AND line_no BETWEEN %s AND %s ORDER BY line_no",
        (doc["id"], line_from, line_to),
    )
    ctx.audit(
        "SOURCE_LINES_VIEWED",
        refs=[case_id],
        target_type="DOCUMENT",
        target_id=document_id,
        reason_code="GRANT_ACTIVE" if via_grant else None,
        detail={"line_from": line_from, "line_to": line_to, "via_grant": via_grant},
    )
    return {
        "document_id": document_id,
        "case_id": case_id,
        "document_type": doc["doc_type"],
        "lines": [{"line": r["line_no"], "page": r["page"], "text": r["text"]} for r in rows],
        "via_grant": via_grant,
    }


def _grant_for_document(ctx: Ctx, doc: Row) -> Row | None:
    """A live grant of the caller on a link that cites this document in its far case."""
    return one(
        ctx.conn,
        "SELECT g.* FROM access_grants g JOIN link_cited_lines c ON c.link_id = g.link_id "
        "WHERE g.holder_id = %s AND g.state = 'ACTIVE' AND g.expires_at > %s "
        "AND g.far_case_id = %s AND c.document_id = %s LIMIT 1",
        (uuid.UUID(ctx.me.user_id), ctx.now(), doc["case_id"], doc["id"]),
    )


__all__ = ["iso", "router"]
