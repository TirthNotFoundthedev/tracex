"""Case graphs: one case's extracted entities, mentions and edges, stored in Neo4j.

`build_case_graph(extract_case(case_id, files))` turns one case's extractor output into a
`CaseGraph`: entity nodes (the writings of one entity inside the case grouped conservatively,
see docs/specs/engine-graph.md section 2), one `Mention` per writing with its raw text, file,
line and confidence, and case-graph edges (OWNS, REGISTERED_TO, MENTIONED_WITH, CALLED,
TRANSFERRED_TO, SEEN_AT), each citing the line it came from. Nothing is merged across cases or
overwritten; cross-case links are SAME_AS edges the matcher writes between entity nodes.

Exposed:
    build_case_graph            CaseRecords -> CaseGraph (pure, deterministic)
    CaseGraph, Entity, Mention, Place, Edge        the graph types
    EntityType, EdgeType                           the enums
    entity_sort_key             sort key giving entity ids in load order (case id numerically)
    CaseGraphStore              ensure_schema, write_case, read_case, case_ids, find_entities
    Neo4jCaseGraphStore         the Neo4j adapter (`connect(uri, user, password)`)
    InMemoryCaseGraphStore      the same interface over a dict
"""

from tracex_engine.graph.builder import build_case_graph
from tracex_engine.graph.model import (
    CaseGraph,
    Edge,
    EdgeType,
    Entity,
    EntityType,
    Mention,
    Place,
)
from tracex_engine.graph.neo4j_store import Neo4jCaseGraphStore
from tracex_engine.graph.order import entity_sort_key
from tracex_engine.graph.store import CaseGraphStore, InMemoryCaseGraphStore

__all__ = [
    "CaseGraph",
    "CaseGraphStore",
    "Edge",
    "EdgeType",
    "Entity",
    "EntityType",
    "InMemoryCaseGraphStore",
    "Mention",
    "Neo4jCaseGraphStore",
    "Place",
    "build_case_graph",
    "entity_sort_key",
]
