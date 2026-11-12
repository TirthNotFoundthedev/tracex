"""Builders for engine-result documents used by the scorer self-tests."""

from __future__ import annotations

import copy
from typing import Any

BATCH_ORDER = {"b01": 1, "b02": 2}


def eid(gt_id: str) -> str:
    return f"E|{gt_id}"


def _mention(ref: dict[str, Any]) -> dict[str, Any]:
    return {"case_id": ref["case_id"], "file": ref["file"], "line": ref["line"]}


def engine_entity(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": eid(entity["gt_id"]),
        "type": entity["type"],
        "raw_text": entity["raw_text"],
        "normalized": entity["normalized"],
        "mentions": [_mention(r) for r in entity["mentions"]],
    }


def link_edge(link: dict[str, Any]) -> dict[str, Any]:
    value = link["score"]["value"]
    return {
        "a": eid(link["a"]),
        "b": eid(link["b"]),
        "state": link["state"],
        "band": link["band"],
        "score": 90.0 if value is None else value,
        "gates_failed": copy.deepcopy(link["gates_failed"]),
        "evidence_kinds": list(link["evidence_kinds"]),
        "sources": [_mention(r) for r in link["cited_lines"]],
    }


def perfect_result(
    gt: dict[str, Any],
    batches: tuple[str, ...] = ("b01", "b02"),
    harness: tuple[str, ...] = ("HS-AC13",),
) -> dict[str, Any]:
    """The result a flawless engine returns after the given batches, derived from ground truth."""
    loaded = max(BATCH_ORDER[b] for b in batches)
    entities = [engine_entity(e) for e in gt["entities"] if BATCH_ORDER[e["batch"]] <= loaded]
    present = {e["id"] for e in entities}
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for link in gt["expected_links"]:
        if BATCH_ORDER[link["batch_min"]] > loaded:
            continue
        key = (link["a"], link["b"])
        if key not in latest or link["batch_min"] > latest[key]["batch_min"]:
            latest[key] = link
    edges = [link_edge(link) for link in latest.values()]
    covered = {(e["a"], e["b"]) for e in edges}
    by_id = {e["gt_id"]: e for e in gt["entities"]}
    for group in gt["groups"]:
        if group["scope"] != "cross_case" or group["origin"] != "noise":
            continue
        members = sorted(group["members"])
        for i, first in enumerate(members):
            for second in members[i + 1 :]:
                a, b = eid(first), eid(second)
                if a not in present or b not in present or (a, b) in covered:
                    continue
                refs = [*by_id[first]["mentions"], *by_id[second]["mentions"]]
                edges.append(
                    {
                        "a": a,
                        "b": b,
                        "state": "AUTO",
                        "band": "HIGH",
                        "score": 100,
                        "gates_failed": [],
                        "evidence_kinds": ["ID_EXACT"],
                        "sources": [_mention(r) for r in refs],
                    }
                )
    return {
        "schema_version": "engine-result/1",
        "batches_loaded": list(batches),
        "harness_applied": list(harness),
        "entities": entities,
        "edges": edges,
        "stats": {"oversized_block_count": 0},
    }


def find_edge(result: dict[str, Any], a_gt: str, b_gt: str) -> dict[str, Any]:
    pair = {eid(a_gt), eid(b_gt)}
    for edge in result["edges"]:
        if {edge["a"], edge["b"]} == pair:
            found: dict[str, Any] = edge
            return found
    raise AssertionError(f"no edge for {a_gt} {b_gt}")


def link_by_id(gt: dict[str, Any], link_id: str) -> dict[str, Any]:
    for link in gt["expected_links"]:
        if link["id"] == link_id:
            found: dict[str, Any] = link
            return found
    raise AssertionError(link_id)


def edge_of_link(result: dict[str, Any], gt: dict[str, Any], link_id: str) -> dict[str, Any]:
    link = link_by_id(gt, link_id)
    return find_edge(result, link["a"], link["b"])


def drop_edge_of_link(result: dict[str, Any], gt: dict[str, Any], link_id: str) -> None:
    result["edges"].remove(edge_of_link(result, gt, link_id))


def add_edge(
    result: dict[str, Any],
    a_gt: str,
    b_gt: str,
    state: str,
    band: str = "HIGH",
    score: float = 100,
) -> dict[str, Any]:
    edge: dict[str, Any] = {
        "a": eid(a_gt),
        "b": eid(b_gt),
        "state": state,
        "band": band,
        "score": score,
        "gates_failed": [],
        "evidence_kinds": [],
        "sources": [],
    }
    result["edges"].append(edge)
    return edge
