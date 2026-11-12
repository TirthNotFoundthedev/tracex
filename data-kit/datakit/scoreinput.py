"""Parsing and validation of an engine result document (`schema/engine_result.schema.json`)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

RESULT_SCHEMA_VERSION = "engine-result/1"
ENTITY_TYPES = frozenset({"PERSON", "ORG", "PHONE", "ACCOUNT", "VEHICLE"})
STATES = frozenset({"AUTO", "SUGGESTED", "CONFIRMED", "REJECTED", "UNDONE"})
BANDS = frozenset({"HIGH", "MEDIUM", "LOW"})
BATCH_ORDER = {"b01": 1, "b02": 2}
BATCH_PREFIXES = (["b01"], ["b01", "b02"])

Ref = tuple[str, str, int]


class ScoreInputError(ValueError):
    """The engine result or ground truth cannot be scored: a format problem, not a test failure."""


def gate_key(gate: Any) -> str:
    """Canonical text of one `gates_failed` item: `G1`, or `G6:<template_key>`."""
    if isinstance(gate, str):
        return gate
    return f"{gate['gate']}:{gate['template_key']}"


def ref_of(ref: dict[str, Any]) -> Ref:
    return (str(ref["case_id"]), str(ref["file"]), int(ref["line"]))


@dataclass(frozen=True)
class Edge:
    index: int
    a: str
    b: str
    state: str
    band: str
    score: Decimal
    raw_score: Any
    gates: frozenset[str]
    kinds: frozenset[str]
    sources: frozenset[Ref]


@dataclass(frozen=True)
class EngineResult:
    batches_loaded: int
    harness_applied: frozenset[str]
    entities: dict[str, dict[str, Any]]
    edges: list[Edge]
    oversized_block_count: int | None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ScoreInputError(message)


def _decimal(value: Any, where: str) -> Decimal:
    _require(not isinstance(value, bool), f"{where}: score must be a number, not a boolean")
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ScoreInputError(f"{where}: score {value!r} is not a decimal number") from exc


def _refs(items: Any, where: str) -> frozenset[Ref]:
    _require(isinstance(items, list), f"{where} must be a list")
    found: set[Ref] = set()
    for item in items:
        _require(
            isinstance(item, dict) and {"case_id", "file", "line"} <= set(item),
            f"{where}: each item needs case_id, file and line",
        )
        found.add(ref_of(item))
    return frozenset(found)


def _entity(raw: Any, position: int) -> dict[str, Any]:
    where = f"entities[{position}]"
    _require(isinstance(raw, dict), f"{where} must be an object")
    for key in ("id", "type", "normalized", "mentions"):
        _require(key in raw, f"{where}: missing {key}")
    _require(raw["type"] in ENTITY_TYPES, f"{where}: unknown type {raw['type']!r}")
    _refs(raw["mentions"], f"{where}.mentions")
    if raw["type"] in ("PERSON", "ORG"):
        for ref in raw["mentions"]:
            _require("raw_text" in ref, f"{where}: each PERSON or ORG mention needs raw_text")
    entity: dict[str, Any] = raw
    return entity


def _edge(raw: Any, position: int, entities: dict[str, dict[str, Any]]) -> Edge:
    where = f"edges[{position}]"
    _require(isinstance(raw, dict), f"{where} must be an object")
    for key in ("a", "b", "state", "band", "score", "gates_failed", "evidence_kinds", "sources"):
        _require(key in raw, f"{where}: missing {key}")
    for end in ("a", "b"):
        _require(raw[end] in entities, f"{where}: {end} names unknown entity {raw[end]!r}")
    _require(raw["state"] in STATES, f"{where}: unknown state {raw['state']!r}")
    _require(raw["band"] in BANDS, f"{where}: unknown band {raw['band']!r}")
    _require(isinstance(raw["gates_failed"], list), f"{where}: gates_failed must be a list")
    _require(
        isinstance(raw["evidence_kinds"], list)
        and all(isinstance(k, str) for k in raw["evidence_kinds"]),
        f"{where}: evidence_kinds must be a list of strings",
    )
    for gate in raw["gates_failed"]:
        _require(
            isinstance(gate, str)
            or (isinstance(gate, dict) and {"gate", "template_key"} <= set(gate)),
            f"{where}: gates_failed items are gate ids or {{gate, template_key}}",
        )
    return Edge(
        index=position,
        a=raw["a"],
        b=raw["b"],
        state=raw["state"],
        band=raw["band"],
        score=_decimal(raw["score"], where),
        raw_score=raw["score"],
        gates=frozenset(gate_key(g) for g in raw["gates_failed"]),
        kinds=frozenset(raw["evidence_kinds"]),
        sources=_refs(raw["sources"], f"{where}.sources"),
    )


def parse_result(data: Any) -> EngineResult:
    _require(isinstance(data, dict), "engine result must be a JSON object")
    _require(
        data.get("schema_version") == RESULT_SCHEMA_VERSION,
        f"schema_version must be {RESULT_SCHEMA_VERSION!r}, got {data.get('schema_version')!r}",
    )
    for key in ("batches_loaded", "harness_applied", "entities", "edges"):
        _require(isinstance(data.get(key), list), f"{key} must be a list")
    _require(
        data["batches_loaded"] in BATCH_PREFIXES,
        f"batches_loaded must be ['b01'] or ['b01', 'b02'], got {data['batches_loaded']!r}",
    )
    entities: dict[str, dict[str, Any]] = {}
    for position, raw in enumerate(data["entities"]):
        entity = _entity(raw, position)
        _require(entity["id"] not in entities, f"entities: duplicate id {entity['id']!r}")
        entities[entity["id"]] = entity
    edges = [_edge(raw, position, entities) for position, raw in enumerate(data["edges"])]
    stats = data.get("stats") or {}
    count = stats.get("oversized_block_count")
    _require(
        count is None or isinstance(count, int), "stats.oversized_block_count must be an integer"
    )
    return EngineResult(
        batches_loaded=max((BATCH_ORDER[b] for b in data["batches_loaded"]), default=0),
        harness_applied=frozenset(str(h) for h in data["harness_applied"]),
        entities=entities,
        edges=edges,
        oversized_block_count=count,
    )
