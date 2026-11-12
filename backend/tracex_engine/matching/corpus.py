"""Every loaded case graph, indexed for blocking and evidence (read once per run).

The corpus is read through `CaseGraphStore` (`case_ids`, `read_case`), so it works the same
over Neo4j and the in-memory store. Nothing here changes a graph.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from tracex_engine.graph import (
    CaseGraph,
    CaseGraphStore,
    EdgeType,
    Entity,
    EntityType,
    Mention,
    entity_sort_key,
)
from tracex_engine.scoring import Source

ATTRIBUTION_EDGES = frozenset({EdgeType.OWNS, EdgeType.REGISTERED_TO, EdgeType.MENTIONED_WITH})
COUNTERPARTY_EDGES = frozenset({EdgeType.CALLED, EdgeType.TRANSFERRED_TO})


@dataclass(frozen=True)
class Tie:
    """A person or org tied to an identifier of the same case by one statement or row."""

    party_id: str
    identifier_id: str
    code: str
    confidence: float
    hedged: bool
    source: Source


def source_of(case_id: str, file: str, line: int) -> Source:
    return Source(case_id, file, line)


class Corpus:
    """Entities, mentions, attribution ties and counterparties of every loaded case."""

    def __init__(self, graphs: Iterable[CaseGraph]) -> None:
        self.entities: dict[str, Entity] = {}
        self.mentions: dict[str, list[Mention]] = defaultdict(list)
        self.ties_of_party: dict[str, list[Tie]] = defaultdict(list)
        self.ties_of_identifier: dict[str, list[Tie]] = defaultdict(list)
        self.counterparties: dict[str, set[str]] = defaultdict(set)
        by_value: dict[tuple[EntityType, str], list[str]] = defaultdict(list)
        cases: list[str] = []
        for graph in graphs:
            cases.append(graph.case_id)
            for entity in graph.entities:
                self.entities[entity.entity_id] = entity
                by_value[(entity.type, entity.normalized)].append(entity.entity_id)
            for mention in graph.mentions:
                self.mentions[mention.entity_id].append(mention)
            for edge in graph.edges:
                if edge.type in ATTRIBUTION_EDGES:
                    tie = Tie(
                        edge.source_id,
                        edge.target_id,
                        edge.type.value,
                        edge.confidence,
                        bool(edge.hedged),
                        source_of(edge.case_id, edge.file, edge.line),
                    )
                    self.ties_of_party[tie.party_id].append(tie)
                    self.ties_of_identifier[tie.identifier_id].append(tie)
                elif edge.type in COUNTERPARTY_EDGES:
                    self.counterparties[edge.source_id].add(edge.target_id)
                    self.counterparties[edge.target_id].add(edge.source_id)
        self.case_ids = tuple(cases)
        self.by_value = {k: tuple(sorted(v, key=entity_sort_key)) for k, v in by_value.items()}

    @classmethod
    def load(cls, store: CaseGraphStore) -> "Corpus":
        graphs = (store.read_case(case_id) for case_id in store.case_ids())
        return cls(g for g in graphs if g is not None)

    def of_type(self, *types: EntityType) -> list[Entity]:
        found = [e for e in self.entities.values() if e.type in types]
        return sorted(found, key=lambda e: entity_sort_key(e.entity_id))

    def attribute(self, entity_id: str, key: str) -> set[str]:
        """Every value a mention of the entity stated for `key` (normalized form)."""
        values: set[str] = set()
        for mention in self.mentions[entity_id]:
            for k, v in mention.attributes:
                if k == key and isinstance(v, str) and v:
                    values.add(v)
        return values

    def attribute_sources(self, entity_id: str, key: str) -> tuple[Source, ...]:
        return tuple(
            sorted(
                {
                    source_of(m.case_id, m.file, m.line)
                    for m in self.mentions[entity_id]
                    if any(k == key for k, _ in m.attributes)
                }
            )
        )

    def names(self, entity_id: str) -> set[str]:
        """Normalized main names and aliases over every mention of a person or org."""
        entity = self.entities[entity_id]
        names = {entity.normalized, *entity.aliases}
        names |= {m.normalized for m in self.mentions[entity_id]}
        return {n for n in names if n}

    def sources(self, entity_id: str) -> tuple[Source, ...]:
        """Every line that writes the entity, in order."""
        return tuple(
            sorted({source_of(m.case_id, m.file, m.line) for m in self.mentions[entity_id]})
        )

    def first_source(self, entity_id: str) -> Source:
        entity = self.entities[entity_id]
        return source_of(entity.case_id, entity.file, entity.line)
