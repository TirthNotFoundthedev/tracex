"""Loading and serialising case data through the policy (R5): no route returns case data
without passing the objects built here.

Everything a caller may see of a case, entity, link or stub is decided in this module from the
principal and the database rows; the routes only choose which objects to show. Hidden things
never reach a serializer: a redacted link becomes a stub, a hidden one does not exist.
"""

import copy
import re
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from tracex_api.context import Ctx, iso
from tracex_api.db import Row, many, need, one
from tracex_api.errors import ApiError
from tracex_api.policy import (
    MASKED_TYPES,
    VISIBLE_LINK_STATES,
    CaseFact,
    LinkAccess,
    allowed_actions,
    decision_block,
    final_block,
    link_access,
    mask_value,
)
from tracex_api.security import CursorError, open_cursor, seal_cursor

DIGITS_10 = re.compile(r"(?<![\d])(?:\+\s?91[\s-]?)?(?:\d{5}[\s-]\d{5}|\d{10})(?![\d])")
DIGITS_LONG = re.compile(r"(?<![\d])\d{11,18}(?![\d])")
STUB_MESSAGE_KEY = "access.stub.connection_exists"


def as_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


# ----------------------------------------------------------------------------------------------
# paging


def canonical_filters(filters: dict[str, Any]) -> str:
    return "|".join(f"{k}={filters[k]}" for k in sorted(filters) if filters[k] is not None)


def page_slice[T](
    ctx: Ctx,
    items: Sequence[T],
    limit: int,
    cursor: str | None,
    filters: dict[str, Any],
    route: str,
) -> tuple[Sequence[T], str | None]:
    """Offset paging inside an authenticated-encrypted cursor bound to reader, route, filters."""
    offset = 0
    bound = f"{ctx.me.user_id}|{route}|{canonical_filters(filters)}"
    if cursor is not None:
        try:
            payload = open_cursor(ctx.state.settings.cursor_key, cursor, ctx.now())
        except CursorError as exc:
            raise ApiError(
                "VALIDATION_FAILED", [{"field": "cursor", "code": "invalid_cursor"}]
            ) from exc
        if payload.get("b") != bound or not isinstance(payload.get("o"), int):
            raise ApiError("VALIDATION_FAILED", [{"field": "cursor", "code": "invalid_cursor"}])
        offset = int(payload["o"])
    chunk = items[offset : offset + limit]
    more = offset + limit < len(items)
    token = (
        seal_cursor(ctx.state.settings.cursor_key, {"b": bound, "o": offset + limit}, ctx.now())
        if more
        else None
    )
    return chunk, token


# ----------------------------------------------------------------------------------------------
# cases and entities


def case_row(ctx: Ctx, case_id: str) -> Row | None:
    key = as_uuid(case_id)
    if key is None:
        return None
    return one(
        ctx.conn,
        "SELECT c.*, d.name AS district_name FROM cases c JOIN districts d ON d.id = c.district_id "
        "WHERE c.id = %s",
        (key,),
    )


def case_ref(row: Row, with_title: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {
        "case_id": str(row["id"]),
        "case_number": row["case_number"],
        "district_id": str(row["district_id"]),
    }
    if with_title:
        out["title"] = row["title"]
    return out


def case_visible(ctx: Ctx, row: Row) -> bool:
    return ctx.me.can_view_case(str(row["id"]), str(row["district_id"]))


def entity_row(ctx: Ctx, entity_id: str) -> Row | None:
    key = as_uuid(entity_id)
    if key is None:
        return None
    return one(
        ctx.conn,
        "SELECT e.*, c.district_id, c.case_number, c.title FROM entities e "
        "JOIN cases c ON c.id = e.case_id WHERE e.id = %s",
        (key,),
    )


def entity_rows(ctx: Ctx, ids: Iterable[Any]) -> dict[str, Row]:
    keys = list(set(ids))
    if not keys:
        return {}
    rows = many(
        ctx.conn,
        "SELECT e.*, c.district_id, c.case_number, c.title FROM entities e "
        "JOIN cases c ON c.id = e.case_id WHERE e.id = ANY(%s)",
        (keys,),
    )
    return {str(r["id"]): r for r in rows}


def grant_far_entity(ctx: Ctx, entity_id: str) -> Row | None:
    """A live grant of the caller whose far entity is this one."""
    return one(
        ctx.conn,
        "SELECT * FROM access_grants WHERE holder_id = %s AND far_entity_id = %s "
        "AND state = 'ACTIVE' AND expires_at > %s",
        (uuid.UUID(ctx.me.user_id), uuid.UUID(entity_id), ctx.now()),
    )


def has_full_values(ctx: Ctx, case_id: str, district_id: str, via_grant: bool = False) -> bool:
    """PHONE and ACCOUNT values show in full only to who may read the case's source lines."""
    if ctx.me.can_read_source(case_id, district_id):
        return True
    return via_grant and ctx.me.role != "JUNIOR"


@dataclass
class LinkFacts:
    row: Row
    a: CaseFact
    b: CaseFact
    access: LinkAccess
    via_grant: bool

    @property
    def link_id(self) -> str:
        return str(self.row["link_id"])


def link_facts(ctx: Ctx, rows: Sequence[Row]) -> list[LinkFacts]:
    cases = ctx.case_facts(
        [str(r["case_a_id"]) for r in rows] + [str(r["case_b_id"]) for r in rows]
    )
    out = []
    for r in rows:
        a, b = cases[str(r["case_a_id"])], cases[str(r["case_b_id"])]
        access = link_access(ctx.me, str(r["link_id"]), r["state"], a, b)
        both = ctx.me.can_view_case(a.case_id, a.district_id) and ctx.me.can_view_case(
            b.case_id, b.district_id
        )
        out.append(LinkFacts(r, a, b, access, access is LinkAccess.ALLOW and not both))
    return out


def link_row(ctx: Ctx, link_id: str) -> Row | None:
    key = as_uuid(link_id)
    if key is None:
        return None
    return one(ctx.conn, "SELECT * FROM links WHERE link_id = %s", (key,))


def facts_for_links_of(ctx: Ctx, entity_ids: Sequence[str]) -> list[LinkFacts]:
    keys = [uuid.UUID(e) for e in entity_ids]
    rows = many(
        ctx.conn,
        "SELECT * FROM links WHERE (entity_a_id = ANY(%s) OR entity_b_id = ANY(%s)) "
        "AND state <> 'WITHDRAWN' ORDER BY updated_at DESC, link_id",
        (keys, keys),
    )
    return link_facts(ctx, rows)


def counts_as_connection(f: LinkFacts) -> bool:
    return f.access is LinkAccess.ALLOW and f.row["state"] in VISIBLE_LINK_STATES


def entity_summaries(ctx: Ctx, rows: Sequence[Row]) -> list[dict[str, Any]]:
    """EntitySummary for entities the caller may see in full (own case or jurisdiction), or the
    far entity of a grant (restricted to the granted link)."""
    ids = [str(r["id"]) for r in rows]
    stats: dict[str, dict[str, Any]] = {
        i: {"count": 0, "hidden": False, "review": False} for i in ids
    }
    for f in facts_for_links_of(ctx, ids):
        for end in (str(f.row["entity_a_id"]), str(f.row["entity_b_id"])):
            if end not in stats:
                continue
            if counts_as_connection(f):
                stats[end]["count"] += 1
                if f.row["state"] == "SUGGESTED":
                    stats[end]["review"] = True
            elif f.access is LinkAccess.REDACTED:
                stats[end]["hidden"] = True
    out = []
    for r in rows:
        eid = str(r["id"])
        case_id, district = str(r["case_id"]), str(r["district_id"])
        grant = None if ctx.me.can_view_case(case_id, district) else grant_far_entity(ctx, eid)
        full = has_full_values(ctx, case_id, district, via_grant=grant is not None)
        masked = r["type"] in MASKED_TYPES and not full
        entry: dict[str, Any] = {
            "entity_id": eid,
            "case_id": case_id,
            "type": r["type"],
            "display_value": mask_value(r["type"], r["display_value"])
            if masked
            else r["display_value"],
            "masked": masked,
            "link_count": 1 if grant else stats[eid]["count"],
            "has_hidden_connection": False if grant else stats[eid]["hidden"],
            "needs_review": False if grant else stats[eid]["review"],
            "via_grant": grant is not None,
        }
        out.append(entry)
    return out


def entity_summary(ctx: Ctx, row: Row) -> dict[str, Any]:
    return entity_summaries(ctx, [row])[0]


# ----------------------------------------------------------------------------------------------
# stubs


def stub_request_state(ctx: Ctx, stub_id: Any) -> tuple[str, str | None]:
    latest = one(
        ctx.conn,
        "SELECT state, requested_at FROM access_requests WHERE stub_id = %s "
        "ORDER BY requested_at DESC LIMIT 1",
        (stub_id,),
    )
    if latest is None or latest["state"] in ("WITHDRAWN", "APPROVED"):
        return "NONE", None
    status = {"PENDING": "PENDING", "DENIED": "DENIED", "EXPIRED": "EXPIRED"}[latest["state"]]
    return status, iso(latest["requested_at"])


def stub_for(ctx: Ctx, f: LinkFacts) -> dict[str, Any]:
    """The stub of a REDACTED link for the caller: bound to (caller, link), created on first
    sight. `near_entity_id` is the caller's own side."""
    near = near_entity(ctx, f)
    holder = uuid.UUID(ctx.me.user_id)
    row = one(
        ctx.conn,
        "SELECT * FROM stubs WHERE holder_user_id = %s AND link_id = %s",
        (holder, f.row["link_id"]),
    )
    if row is None:
        row = one(
            ctx.conn,
            "INSERT INTO stubs (holder_user_id, link_id, near_entity_id) VALUES (%s, %s, %s) "
            "RETURNING *",
            (holder, f.row["link_id"], near),
        )
    row = need(row)
    status, at = stub_request_state(ctx, row["stub_id"])
    return stub_out(row, status, at)


def stub_out(row: Row, status: str, requested_at: str | None) -> dict[str, Any]:
    return {
        "redacted": True,
        "stub_id": str(row["stub_id"]),
        "near_entity_id": str(row["near_entity_id"]),
        "connection_exists": True,
        "access_request": {"status": status, "requested_at": requested_at},
        "message_key": STUB_MESSAGE_KEY,
    }


def near_entity(ctx: Ctx, f: LinkFacts) -> uuid.UUID:
    """The end of the link on the caller's visible side (the first visible end)."""
    if ctx.me.can_view_case(f.a.case_id, f.a.district_id):
        return f.row["entity_a_id"]  # type: ignore[no-any-return]
    return f.row["entity_b_id"]  # type: ignore[no-any-return]


def stubs_for(ctx: Ctx, facts: Iterable[LinkFacts]) -> list[dict[str, Any]]:
    stubs = [stub_for(ctx, f) for f in facts if f.access is LinkAccess.REDACTED]
    return sorted(stubs, key=lambda s: s["stub_id"])


# ----------------------------------------------------------------------------------------------
# links and explanations


def link_cases(f: LinkFacts) -> list[str]:
    return [f.a.case_id, f.b.case_id]


def overlay_history(ctx: Ctx, link_id: Any) -> list[Row]:
    return many(ctx.conn, "SELECT * FROM link_history WHERE link_id = %s ORDER BY id", (link_id,))


ENGINE_REASON_CODES = frozenset({"DEMOTED", "PROMOTED", "WITHDRAWN"})


def explanation_payload(ctx: Ctx, f: LinkFacts) -> dict[str, Any]:
    """The stored payload with the read-time overlay (architecture section 6): state and history
    from Postgres, engine ids replaced by API ids, document ids by `documents.id`, the optional
    `page`, `document_type` and `case_number` of each source added, then masking."""
    payload: dict[str, Any] = copy.deepcopy(f.row["explanation"])
    row = f.row
    entities = {
        e["engine_entity_id"]: str(e["id"])
        for e in many(
            ctx.conn,
            "SELECT id, engine_entity_id FROM entities WHERE id = ANY(%s)",
            ([row["entity_a_id"], row["entity_b_id"]],),
        )
    }
    cases = {
        c["engine_case_id"]: c
        for c in many(
            ctx.conn,
            "SELECT id, engine_case_id, case_number FROM cases WHERE id = ANY(%s)",
            ([row["case_a_id"], row["case_b_id"]],),
        )
    }
    documents = {
        (d["engine_case_id"], d["file_name"]): d
        for d in many(
            ctx.conn,
            "SELECT d.id, d.file_name, d.doc_type, c.engine_case_id FROM documents d "
            "JOIN cases c ON c.id = d.case_id WHERE d.case_id = ANY(%s)",
            ([row["case_a_id"], row["case_b_id"]],),
        )
    }

    def fix_source(source: dict[str, Any]) -> None:
        engine_case = source["case_id"]
        doc = documents.get((engine_case, source["document_id"]))
        case = cases.get(engine_case)
        if doc is not None:
            line = one(
                ctx.conn,
                "SELECT page FROM document_lines WHERE document_id = %s AND line_no = %s",
                (doc["id"], source["line"]),
            )
            source["document_id"] = str(doc["id"])
            source["document_type"] = doc["doc_type"]
            if line is not None and line["page"] is not None:
                source["page"] = line["page"]
        if case is not None:
            source["case_id"] = str(case["id"])
            source["case_number"] = case["case_number"]

    for record in payload.get("records", []):
        record["entity_id"] = entities.get(record["entity_id"], record["entity_id"])
        fix_source(record["source"])
        record["case_id"] = (
            str(cases[record["case_id"]]["id"]) if record["case_id"] in cases else record["case_id"]
        )
    for tier in payload.get("support", []):
        for item in tier.get("items", []):
            for source in item.get("sources", []):
                fix_source(source)
    for item in payload.get("against", []):
        for source in item.get("sources", []):
            fix_source(source)
    payload["state"] = row["state"]
    payload["history"] = [
        {
            "from": h["from_state"],
            "to": h["to_state"],
            "at": iso(h["at"]),
            "reason_code": h["reason_code"]
            if h["actor_kind"] == "ENGINE" and h["reason_code"] in ENGINE_REASON_CODES
            else None,
        }
        for h in overlay_history(ctx, row["link_id"])
    ]
    mask_payload(ctx, f, payload)
    return payload


def needs_masking(ctx: Ctx, f: LinkFacts) -> bool:
    """A link's values are masked unless the caller may read the full values of every end."""
    if f.row["entity_type"] not in MASKED_TYPES and f.row["entity_type"] != "PERSON":
        return False
    for end in (f.a, f.b):
        grant_far = f.via_grant and end.case_id == _far_case(ctx, f)
        if not has_full_values(ctx, end.case_id, end.district_id, via_grant=grant_far):
            return True
    return False


def _far_case(ctx: Ctx, f: LinkFacts) -> str | None:
    grant = one(
        ctx.conn,
        "SELECT far_case_id FROM access_grants WHERE holder_id = %s AND link_id = %s "
        "AND state = 'ACTIVE'",
        (uuid.UUID(ctx.me.user_id), f.row["link_id"]),
    )
    return str(grant["far_case_id"]) if grant else None


def mask_text(text: str) -> str:
    text = DIGITS_10.sub(lambda m: mask_value("PHONE", m.group()), text)
    return DIGITS_LONG.sub(lambda m: mask_value("ACCOUNT", m.group()), text)


def _mask_params(value: Any) -> Any:
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, list):
        return [_mask_params(v) for v in value]
    if isinstance(value, dict):
        return {k: _mask_params(v) for k, v in value.items()}
    return value


def mask_payload(ctx: Ctx, f: LinkFacts, payload: dict[str, Any]) -> bool:
    """Replace phone and account values in the places they appear (records, evidence params)
    when the caller may not see them in full. Returns True when anything was masked."""
    if not needs_masking(ctx, f):
        return False
    before = repr(payload)
    for record in payload.get("records", []):
        if f.row["entity_type"] in MASKED_TYPES:
            record["raw_text"] = mask_value(f.row["entity_type"], record["normalized"])
            record["normalized"] = mask_value(f.row["entity_type"], record["normalized"])
        else:
            record["raw_text"] = mask_text(record["raw_text"])
            record["normalized"] = mask_text(record["normalized"])
    for tier in payload.get("support", []):
        for item in tier.get("items", []):
            item["params"] = _mask_params(item.get("params", {}))
    for item in payload.get("against", []):
        item["params"] = _mask_params(item.get("params", {}))
    return repr(payload) != before


def main_reason(ctx: Ctx, f: LinkFacts, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    stored = f.row["explanation"]
    best: dict[str, Any] | None = None
    for tier in stored.get("support", []):
        for item in tier.get("items", []):
            if best is None or item["contribution"] > best["contribution"]:
                best = item
    if best is None:
        return {"template_key": "match.evidence.id_exact", "params": {}}
    reason: dict[str, Any] = {
        "template_key": best["template_key"],
        "params": copy.deepcopy(best.get("params", {})),
    }
    if needs_masking(ctx, f):
        reason["params"] = _mask_params(reason["params"])
        reason["masked"] = True
    return reason


def link_summary(
    ctx: Ctx,
    f: LinkFacts,
    entities: dict[str, Row],
    summaries: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    row = f.row
    ends = []
    for entity_key, case_fact in ((row["entity_a_id"], f.a), (row["entity_b_id"], f.b)):
        e = entities[str(entity_key)]
        summary = (summaries or {}).get(str(entity_key)) or entity_summary(ctx, e)
        ends.append(
            {
                "entity": summary,
                "case": case_ref(case_row_for(ctx, case_fact.case_id), with_title=False),
            }
        )
    return {
        "link_id": f.link_id,
        "entity_type": row["entity_type"],
        "state": row["state"],
        "band": row["band"],
        "score": float(row["score"]),
        "ends": ends,
        "main_reason": main_reason(ctx, f),
        "updated_at": iso(row["updated_at"]),
    }


_CASE_CACHE_ATTR = "_case_rows"


def case_row_for(ctx: Ctx, case_id: str) -> Row:
    cache: dict[str, Row] = ctx.__dict__.setdefault(_CASE_CACHE_ATTR, {})
    if case_id not in cache:
        row = case_row(ctx, case_id)
        row = need(row)
        cache[case_id] = row
    return cache[case_id]


def link_summaries(ctx: Ctx, facts: Sequence[LinkFacts]) -> list[dict[str, Any]]:
    """LinkSummary for each ALLOW link, with end entities summarised for the caller."""
    ids = {k for f in facts for k in (f.row["entity_a_id"], f.row["entity_b_id"])}
    entities = entity_rows(ctx, ids)
    summaries = {
        str(r["id"]): s
        for r, s in zip(
            entities.values(), entity_summaries(ctx, list(entities.values())), strict=True
        )
    }
    return [link_summary(ctx, f, entities, summaries) for f in facts]


def decision_view(ctx: Ctx, f: LinkFacts) -> tuple[list[str], str | None]:
    actions = allowed_actions(ctx.me, f.row["state"], f.a, f.b, f.via_grant)
    if actions:
        return actions, None
    for action in ("CONFIRM", "UNDO", "REOPEN", "REJECT"):
        block = decision_block(ctx.me, action, f.a, f.b, f.via_grant)
        if block:
            return [], block
    return [], final_block(f.row["state"]) or "STATE_FINAL"


def link_detail(ctx: Ctx, f: LinkFacts) -> dict[str, Any]:
    summary = link_summaries(ctx, [f])[0]
    actions, block = decision_view(ctx, f)
    history = []
    for h in overlay_history(ctx, f.row["link_id"]):
        entry: dict[str, Any] = {"from": h["from_state"], "to": h["to_state"], "at": iso(h["at"])}
        if f.via_grant:
            entry["reason_code"] = h["reason_code"]
        else:
            entry.update(
                actor_kind=h["actor_kind"],
                actor_user_id=str(h["actor_user_id"]) if h["actor_user_id"] else None,
                reason_code=h["reason_code"],
                reason_text=h["reason_text"],
            )
        history.append(entry)
    return {
        **summary,
        "thresholds_version": f.row["thresholds_version"],
        "ruleset_version": f.row["ruleset_version"],
        "created_at": iso(f.row["created_at"]),
        "history": history,
        "allowed_actions": actions,
        "decision_block": block,
        "via_grant": f.via_grant,
    }


def hidden_or_404(
    ctx: Ctx, supplied: str, f: LinkFacts | None, resolved: str | None = None
) -> LinkFacts:
    """A link the caller may see in full, else the same 404 whatever the reason (R2)."""
    if f is None or f.access is not LinkAccess.ALLOW:
        raise ctx.not_found(supplied, resolved=resolved)
    return f


def one_link_facts(ctx: Ctx, link_id: str) -> LinkFacts | None:
    row = link_row(ctx, link_id)
    return link_facts(ctx, [row])[0] if row else None


def date_text(value: datetime | Any) -> str:
    return str(value)
