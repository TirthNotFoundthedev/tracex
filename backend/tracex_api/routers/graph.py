"""Per-viewer graph neighbours, clusters and paths.

Traversal runs over ALLOW links only and stops at the first hidden link: it is never a full
traversal filtered afterwards, so an entity reachable only through a hidden link does not appear
and `truncated` is judged after pruning. A hidden link at a visited entity is an unlabelled stub.
"""

import uuid
from collections import deque
from typing import Any

from fastapi import APIRouter, Depends, Query

from tracex_api.context import OFFICER, Ctx, authed_ctx, endpoint
from tracex_api.policy import LinkAccess
from tracex_api.views import (
    LinkFacts,
    entity_row,
    entity_rows,
    entity_summaries,
    facts_for_links_of,
    link_cases,
    link_summaries,
    stubs_for,
)

router = APIRouter()
ACTIVE = frozenset({"AUTO", "CONFIRMED"})
SHOWN = frozenset({"AUTO", "SUGGESTED", "CONFIRMED"})


def _visible_entity_or_404(ctx: Ctx, entity_id: str) -> Any:
    entity = entity_row(ctx, entity_id)
    if entity is None or not ctx.me.can_view_case(
        str(entity["case_id"]), str(entity["district_id"])
    ):
        raise ctx.not_found(entity_id, resolved=str(entity["id"]) if entity else None)
    return entity


def _other(f: LinkFacts, entity_id: str) -> str:
    a, b = str(f.row["entity_a_id"]), str(f.row["entity_b_id"])
    return b if a == entity_id else a


def _audit_graph(
    ctx: Ctx,
    entity: Any,
    ids: list[str],
    facts: list[LinkFacts],
    stubs: list[dict[str, Any]],
    stub_cases: list[str],
) -> None:
    cases = [str(entity["case_id"]), *[c for f in facts for c in link_cases(f)], *stub_cases]
    ctx.audit(
        "GRAPH_VIEWED",
        refs=cases,
        target_type="ENTITY",
        target_id=str(entity["id"]),
        detail={
            "entity_ids": ids[:500],
            "link_ids": [f.link_id for f in facts],
            "stub_ids": [s["stub_id"] for s in stubs],
            "via_grant": False,
        },
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


@endpoint(router, "GET", "/entities/{entity_id}/graph", policy=OFFICER, audit_event="GRAPH_VIEWED")
def get_graph(
    entity_id: str,
    ctx: Ctx = Depends(authed_ctx),
    depth: int = Query(1, ge=1, le=3),
    limit: int = Query(150, ge=1, le=150),
) -> dict[str, Any]:
    center = _visible_entity_or_404(ctx, entity_id)
    center_id = str(center["id"])
    distance = {center_id: 0}
    edges: dict[str, LinkFacts] = {}
    hidden: dict[str, LinkFacts] = {}
    queue = deque([center_id])
    truncated = False
    while queue:
        current = queue.popleft()
        if distance[current] >= depth:
            continue
        for f in facts_for_links_of(ctx, [current]):
            if f.access is LinkAccess.REDACTED:
                hidden[f.link_id] = f
                continue
            if f.access is not LinkAccess.ALLOW or f.via_grant or f.row["state"] not in SHOWN:
                continue
            other = _other(f, current)
            if other not in distance:
                if len(distance) >= limit:
                    truncated = True
                    continue
                distance[other] = distance[current] + 1
                queue.append(other)
            edges[f.link_id] = f
    entities = entity_rows(ctx, [uuid.UUID(i) for i in distance])
    summaries = {s["entity_id"]: s for s in entity_summaries(ctx, list(entities.values()))}
    degree = dict.fromkeys(distance, 0)
    for f in edges.values():
        for end in (str(f.row["entity_a_id"]), str(f.row["entity_b_id"])):
            if end in degree:
                degree[end] += 1
    nodes = [
        {"entity": summaries[i], "degree": degree[i], "distance": d}
        for i, d in sorted(distance.items(), key=lambda kv: (kv[1], kv[0]))
    ]
    stub_facts = [f for f in hidden.values() if _near_in(distance, f, ctx)]
    stubs = stubs_for(ctx, stub_facts)
    _audit_graph(
        ctx,
        center,
        list(distance),
        list(edges.values()),
        stubs,
        [c for f in stub_facts for c in link_cases(f)],
    )
    return {
        "center_entity_id": center_id,
        "nodes": nodes,
        "edges": [
            {
                "link_id": f.link_id,
                "state": f.row["state"],
                "band": f.row["band"],
                "from_entity_id": str(f.row["entity_a_id"]),
                "to_entity_id": str(f.row["entity_b_id"]),
            }
            for f in edges.values()
            if str(f.row["entity_a_id"]) in distance and str(f.row["entity_b_id"]) in distance
        ],
        "stubs": stubs,
        "truncated": truncated,
    }


def _near_in(distance: dict[str, int], f: LinkFacts, ctx: Ctx) -> bool:
    a, b = str(f.row["entity_a_id"]), str(f.row["entity_b_id"])
    visible_end = a if ctx.me.can_view_case(f.a.case_id, f.a.district_id) else b
    return visible_end in distance


@endpoint(
    router, "GET", "/entities/{entity_id}/cluster", policy=OFFICER, audit_event="GRAPH_VIEWED"
)
def get_cluster(entity_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    center = _visible_entity_or_404(ctx, entity_id)
    center_id = str(center["id"])
    members = {center_id}
    links: dict[str, LinkFacts] = {}
    hidden: dict[str, LinkFacts] = {}
    queue = deque([center_id])
    while queue:
        current = queue.popleft()
        for f in facts_for_links_of(ctx, [current]):
            if f.row["entity_type"] != center["type"]:
                continue
            if f.access is LinkAccess.REDACTED and f.row["state"] in ACTIVE:
                hidden[f.link_id] = f
                continue
            if f.access is not LinkAccess.ALLOW or f.via_grant or f.row["state"] not in ACTIVE:
                continue
            links[f.link_id] = f
            other = _other(f, current)
            if other not in members:
                members.add(other)
                queue.append(other)
    entities = entity_rows(ctx, [uuid.UUID(m) for m in members])
    member_summaries = entity_summaries(ctx, list(entities.values()))
    degree = dict.fromkeys(members, 0)
    for f in links.values():
        degree[str(f.row["entity_a_id"])] += 1
        degree[str(f.row["entity_b_id"])] += 1
    best = max(degree.items(), key=lambda kv: (kv[1], kv[0]))[0] if len(members) > 1 else None
    stub_facts = [f for f in hidden.values() if _near_in(dict.fromkeys(members, 0), f, ctx)]
    stubs = stubs_for(ctx, stub_facts)
    _audit_graph(
        ctx,
        center,
        sorted(members),
        list(links.values()),
        stubs,
        [c for f in stub_facts for c in link_cases(f)],
    )
    return {
        "cluster_id": str(uuid.uuid4()),
        "entity_type": center["type"],
        "members": member_summaries,
        "links": link_summaries(ctx, list(links.values())),
        "stubs": stubs,
        "most_connected_entity_id": best,
    }


@endpoint(router, "GET", "/entities/{entity_id}/paths", policy=OFFICER, audit_event="GRAPH_VIEWED")
def get_paths(
    entity_id: str,
    ctx: Ctx = Depends(authed_ctx),
    max_hops: int = Query(3, ge=1, le=4),
    limit: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    origin = _visible_entity_or_404(ctx, entity_id)
    origin_id = str(origin["id"])
    paths: list[list[tuple[str, LinkFacts]]] = []
    hidden_ends: list[tuple[list[tuple[str, LinkFacts]], LinkFacts]] = []

    def walk(current: str, trail: list[tuple[str, LinkFacts]], seen: set[str]) -> None:
        if len(trail) >= max_hops or len(paths) + len(hidden_ends) >= limit:
            return
        for f in facts_for_links_of(ctx, [current]):
            if f.row["state"] not in ACTIVE and f.access is not LinkAccess.REDACTED:
                continue
            if f.access is LinkAccess.REDACTED and f.row["state"] in ACTIVE | {"SUGGESTED"}:
                hidden_ends.append((trail, f))
                continue
            if f.access is not LinkAccess.ALLOW or f.via_grant or f.row["state"] not in ACTIVE:
                continue
            other = _other(f, current)
            if other in seen:
                continue
            step = [*trail, (other, f)]
            paths.append(step)
            walk(other, step, seen | {other})

    walk(origin_id, [], {origin_id})
    ids = {origin_id} | {e for p in paths for e, _ in p}
    entities = entity_rows(ctx, [uuid.UUID(i) for i in ids])
    summaries = {s["entity_id"]: s for s in entity_summaries(ctx, list(entities.values()))}
    all_facts = [f for p in paths for _, f in p]
    out = []
    for p in paths:
        link_sums = link_summaries(ctx, [f for _, f in p])
        segments: list[dict[str, Any]] = [
            {"kind": "VISIBLE", "link": link_sums[i], "entity": summaries[e]}
            for i, (e, _) in enumerate(p)
        ]
        out.append({"path_id": str(uuid.uuid4()), "segments": segments})
    stub_facts = [f for _, f in hidden_ends]
    stub_by_link = {s["stub_id"]: s for s in stubs_for(ctx, stub_facts)}
    for trail, f in hidden_ends:
        stub = stubs_for(ctx, [f])[0]
        stub_by_link.pop(stub["stub_id"], None)
        segments = []
        if trail:
            link_sums = link_summaries(ctx, [lf for _, lf in trail])
            segments = [
                {"kind": "VISIBLE", "link": link_sums[i], "entity": summaries[e]}
                for i, (e, _) in enumerate(trail)
            ]
        segments.append({"kind": "STUB", "stub": stub})
        out.append({"path_id": str(uuid.uuid4()), "segments": segments})
    stubs = stubs_for(ctx, stub_facts)
    _audit_graph(
        ctx, origin, sorted(ids), all_facts, stubs, [c for f in stub_facts for c in link_cases(f)]
    )
    return {"origin_entity_id": origin_id, "paths": out[:limit]}
