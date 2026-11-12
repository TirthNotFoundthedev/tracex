"""Neo4j adapter of `LinkStore`: SAME_AS relationships between two untouched `:Entity` nodes.

The relationship runs from `entity_a_id` to `entity_b_id`; nothing is written onto the entity
nodes. Structured properties (gates, evidence, history) are stored as JSON strings and scores as
decimal strings, so a read gives back exactly the edge that was written. Case-graph writes never
touch SAME_AS relationships, so edges survive a case rewrite.
"""

import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, LiteralString

from neo4j import Driver, GraphDatabase, ManagedTransaction

from tracex_engine.graph import EntityType, entity_sort_key
from tracex_engine.matching.link_store import LinkConflictError
from tracex_engine.matching.model import HistoryEntry, LinkState, SameAsEdge
from tracex_engine.scoring import Band, FailedGate

_CONSTRAINT: LiteralString = (
    "CREATE CONSTRAINT same_as_link_id IF NOT EXISTS "
    "FOR ()-[r:SAME_AS]-() REQUIRE r.link_id IS UNIQUE"
)
_ALL: LiteralString = "MATCH (:Entity)-[r:SAME_AS]->(:Entity) RETURN properties(r) AS p"
_ONE: LiteralString = (
    "MATCH (:Entity)-[r:SAME_AS {link_id: $link_id}]->(:Entity) RETURN properties(r) AS p"
)
_ON_PAIR: LiteralString = (
    "MATCH (a:Entity {entity_id: $a})-[r:SAME_AS]-(b:Entity {entity_id: $b}) "
    "RETURN r.link_id AS link_id"
)
_PUT: LiteralString = (
    "MATCH (a:Entity {entity_id: $a}), (b:Entity {entity_id: $b}) "
    "MERGE (a)-[r:SAME_AS {link_id: $link_id}]->(b) SET r = $props RETURN count(r) AS n"
)
_REMOVE: LiteralString = "MATCH (:Entity)-[r:SAME_AS {link_id: $link_id}]->(:Entity) DELETE r"


class Neo4jLinkStore:
    """`LinkStore` over a Neo4j driver the caller owns (and closes)."""

    def __init__(self, driver: Driver) -> None:
        self._driver = driver

    @classmethod
    def connect(cls, uri: str, user: str, password: str) -> "Neo4jLinkStore":
        return cls(GraphDatabase.driver(uri, auth=(user, password)))

    def close(self) -> None:
        self._driver.close()

    def ensure_schema(self) -> None:
        with self._driver.session() as session:
            session.run(_CONSTRAINT).consume()

    def edges(self) -> tuple[SameAsEdge, ...]:
        with self._driver.session() as session:
            found = [_to_edge(r["p"]) for r in session.run(_ALL)]
        return tuple(
            sorted(
                found,
                key=lambda e: (entity_sort_key(e.entity_a_id), entity_sort_key(e.entity_b_id)),
            )
        )

    def get(self, link_id: str) -> SameAsEdge | None:
        with self._driver.session() as session:
            record = session.run(_ONE, link_id=link_id).single()
        return _to_edge(record["p"]) if record else None

    def put(self, edge: SameAsEdge) -> None:
        with self._driver.session() as session:
            session.execute_write(_put, edge)

    def remove(self, link_id: str) -> None:
        with self._driver.session() as session:
            session.run(_REMOVE, link_id=link_id).consume()


def _put(tx: ManagedTransaction, edge: SameAsEdge) -> None:
    holders = [r["link_id"] for r in tx.run(_ON_PAIR, a=edge.entity_a_id, b=edge.entity_b_id)]
    if any(h != edge.link_id for h in holders):
        raise LinkConflictError("pair already linked")
    old = tx.run(_ONE, link_id=edge.link_id).single()
    if old and (old["p"]["entity_a_id"], old["p"]["entity_b_id"]) != edge.pair:
        raise LinkConflictError("a link id never moves to another pair")
    written = tx.run(
        _PUT, a=edge.entity_a_id, b=edge.entity_b_id, link_id=edge.link_id, props=_props(edge)
    ).single()
    if not written or written["n"] != 1:
        raise LinkConflictError("both entities must exist before they are linked")


def _props(edge: SameAsEdge) -> dict[str, Any]:
    return {
        "link_id": edge.link_id,
        "entity_a_id": edge.entity_a_id,
        "entity_b_id": edge.entity_b_id,
        "entity_type": edge.entity_type.value,
        "case_a": edge.case_a,
        "case_b": edge.case_b,
        "state": edge.state.value,
        "score": str(edge.score),
        "band": edge.band.value,
        "gates": json.dumps([[g.gate, g.template_key] for g in edge.gates_failed]),
        "evidence": json.dumps(edge.evidence, sort_keys=True, ensure_ascii=False),
        "ruleset_version": edge.ruleset_version,
        "thresholds_version": edge.thresholds_version,
        "high_min": str(edge.high_min),
        "medium_min": str(edge.medium_min),
        "match_run_id": edge.match_run_id,
        "created_at": edge.created_at,
        "updated_at": edge.updated_at,
        "history": json.dumps(
            [
                [
                    h.from_state.value if h.from_state else None,
                    h.to_state.value if h.to_state else None,
                    h.actor,
                    h.at,
                    h.reason_code,
                    h.reason_text,
                    h.decision_id,
                ]
                for h in edge.history
            ],
            ensure_ascii=False,
        ),
    }


def _state(value: str | None) -> LinkState | None:
    return LinkState(value) if value else None


def _to_edge(p: Mapping[str, Any]) -> SameAsEdge:
    return SameAsEdge(
        link_id=str(p["link_id"]),
        entity_a_id=str(p["entity_a_id"]),
        entity_b_id=str(p["entity_b_id"]),
        entity_type=EntityType(str(p["entity_type"])),
        case_a=str(p["case_a"]),
        case_b=str(p["case_b"]),
        state=LinkState(str(p["state"])),
        score=Decimal(str(p["score"])),
        band=Band(str(p["band"])),
        gates_failed=tuple(FailedGate(g, k) for g, k in json.loads(str(p["gates"]))),
        evidence=json.loads(str(p["evidence"])),
        ruleset_version=str(p["ruleset_version"]),
        thresholds_version=int(p["thresholds_version"]),
        high_min=Decimal(str(p["high_min"])),
        medium_min=Decimal(str(p["medium_min"])),
        match_run_id=str(p["match_run_id"]),
        created_at=str(p["created_at"]),
        updated_at=str(p["updated_at"]),
        history=tuple(
            HistoryEntry(_state(f), _state(t), a, at, rc, rt, d)
            for f, t, a, at, rc, rt, d in json.loads(str(p["history"]))
        ),
    )
