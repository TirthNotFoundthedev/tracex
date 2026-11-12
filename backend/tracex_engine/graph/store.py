"""The store interface the matcher reads and writes through, and an in-memory adapter."""

from typing import Protocol

from tracex_engine.graph.model import CaseGraph, Entity, EntityType
from tracex_engine.graph.order import case_sort_key, entity_sort_key


class CaseGraphStore(Protocol):
    """Where case graphs live. Writes are upserts; nothing is ever merged or deleted."""

    def ensure_schema(self) -> None:
        """Create the constraints and indexes the lookups need; safe to call again."""
        ...

    def write_case(self, graph: CaseGraph) -> None:
        """Store the case's nodes and edges. Writing the same graph again changes nothing."""
        ...

    def read_case(self, case_id: str) -> CaseGraph | None:
        """The case's graph as built, or None when the case was never written."""
        ...

    def case_ids(self) -> tuple[str, ...]:
        """Every stored case id in numeric case order."""
        ...

    def find_entities(self, type: EntityType, normalized: str) -> tuple[Entity, ...]:
        """Entities of every case with this type and normalized value, in entity id order."""
        ...


class InMemoryCaseGraphStore:
    """Keeps graphs in a dict; same behaviour as the Neo4j store, for tests and small runs."""

    def __init__(self) -> None:
        self._graphs: dict[str, CaseGraph] = {}

    def ensure_schema(self) -> None:
        return None

    def write_case(self, graph: CaseGraph) -> None:
        self._graphs[graph.case_id] = graph

    def read_case(self, case_id: str) -> CaseGraph | None:
        return self._graphs.get(case_id)

    def case_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._graphs, key=case_sort_key))

    def find_entities(self, type: EntityType, normalized: str) -> tuple[Entity, ...]:
        found = [
            e
            for graph in self._graphs.values()
            for e in graph.entities
            if e.type is type and e.normalized == normalized
        ]
        return tuple(sorted(found, key=lambda e: entity_sort_key(e.entity_id)))
