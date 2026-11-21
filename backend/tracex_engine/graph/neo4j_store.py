"""Neo4j adapter of `CaseGraphStore` (docs/specs/engine-graph.md sections 1 and 4).

Entities are `:Entity` nodes with a type label, mentions `:Mention` nodes under `HAS_MENTION`,
places `:Place` nodes, and every edge a relationship of its own type. Writes are `MERGE` on the
deterministic ids followed by a full property replace, inside one transaction per case: the
same graph written twice leaves the database as it was, and relationships this module does not
own (SAME_AS, written by the matcher) are never touched.
"""

from collections.abc import Mapping
from typing import LiteralString

from neo4j import Driver, GraphDatabase, ManagedTransaction

from tracex_engine.graph.model import (
    AttrValue,
    CaseDistrict,
    CaseGraph,
    Edge,
    EdgeType,
    Entity,
    EntityType,
    Mention,
    Place,
    Scalar,
)
from tracex_engine.graph.order import case_sort_key, entity_sort_key

_NODE_CONSTRAINTS: tuple[LiteralString, ...] = (
    "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
    "CREATE CONSTRAINT mention_id_unique IF NOT EXISTS "
    "FOR (m:Mention) REQUIRE m.mention_id IS UNIQUE",
    "CREATE CONSTRAINT place_id_unique IF NOT EXISTS FOR (p:Place) REQUIRE p.place_id IS UNIQUE",
    "CREATE CONSTRAINT case_id_unique IF NOT EXISTS FOR (c:Case) REQUIRE c.case_id IS UNIQUE",
)
_INDEXES: tuple[LiteralString, ...] = (
    "CREATE INDEX entity_type_normalized IF NOT EXISTS FOR (e:Entity) ON (e.type, e.normalized)",
    "CREATE INDEX entity_case IF NOT EXISTS FOR (e:Entity) ON (e.case_id)",
    "CREATE INDEX mention_case IF NOT EXISTS FOR (m:Mention) ON (m.case_id)",
    "CREATE INDEX place_case IF NOT EXISTS FOR (p:Place) ON (p.case_id)",
)

_MENTION_FIELDS = frozenset(
    {
        "mention_id", "entity_id", "case_id", "raw_text", "normalized", "file", "line",
        "confidence", "position",
    }
)  # fmt: skip
_EDGE_FIELDS = frozenset(
    {"edge_id", "case_id", "file", "line", "confidence", "raw_text", "hedged", "position"}
)


def _edge_constraint(type_: EdgeType) -> LiteralString:
    # `type_` is a member of the closed EdgeType enum, never user input.
    return (
        f"CREATE CONSTRAINT {type_.value.lower()}_edge_id IF NOT EXISTS "
        f"FOR ()-[r:{type_.value}]-() REQUIRE r.edge_id IS UNIQUE"
    )


def _edge_write(type_: EdgeType) -> LiteralString:
    target = (
        "(b:Place {place_id: row.target_id})"
        if type_ is EdgeType.SEEN_AT
        else "(b:Entity {entity_id: row.target_id})"
    )
    return (
        "UNWIND $rows AS row MATCH (a:Entity {entity_id: row.source_id}) "
        f"MATCH {target} "
        f"MERGE (a)-[r:{type_.value} {{edge_id: row.edge_id}}]->(b) SET r = row.props"
    )


def _entity_write(type_: EntityType) -> LiteralString:
    label = type_.value.capitalize()
    return (
        "UNWIND $rows AS row MERGE (e:Entity {entity_id: row.entity_id}) "
        f"SET e = row.props SET e:{label}"
    )


_MENTION_WRITE: LiteralString = (
    "UNWIND $rows AS row MATCH (e:Entity {entity_id: row.entity_id}) "
    "MERGE (m:Mention {mention_id: row.mention_id}) SET m = row.props "
    "MERGE (e)-[:HAS_MENTION]->(m)"
)
_PLACE_WRITE: LiteralString = (
    "UNWIND $rows AS row MERGE (p:Place {place_id: row.place_id}) SET p = row.props"
)
_EDGE_TYPES = [t.value for t in EdgeType]


class Neo4jCaseGraphStore:
    """`CaseGraphStore` over a Neo4j driver the caller owns (and closes)."""

    def __init__(self, driver: Driver) -> None:
        self._driver = driver

    @classmethod
    def connect(cls, uri: str, user: str, password: str) -> "Neo4jCaseGraphStore":
        return cls(GraphDatabase.driver(uri, auth=(user, password)))

    def close(self) -> None:
        self._driver.close()

    def ensure_schema(self) -> None:
        statements = [
            *_NODE_CONSTRAINTS,
            *_INDEXES,
            *(_edge_constraint(t) for t in EdgeType),
        ]
        with self._driver.session() as session:
            for statement in statements:
                session.run(statement).consume()

    def write_case(self, graph: CaseGraph) -> None:
        with self._driver.session() as session:
            session.execute_write(_write, graph)

    def read_case(self, case_id: str) -> CaseGraph | None:
        with self._driver.session() as session:
            return session.execute_read(_read, case_id)

    def case_ids(self) -> tuple[str, ...]:
        with self._driver.session() as session:
            result = session.run("MATCH (e:Entity) RETURN DISTINCT e.case_id AS case_id")
            return tuple(sorted((r["case_id"] for r in result), key=case_sort_key))

    def find_entities(self, type: EntityType, normalized: str) -> tuple[Entity, ...]:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (e:Entity {type: $type, normalized: $normalized}) RETURN properties(e) AS p",
                type=type.value,
                normalized=normalized,
            )
            found = [_to_entity(r["p"]) for r in result]
        return tuple(sorted(found, key=lambda e: entity_sort_key(e.entity_id)))


def _write(tx: ManagedTransaction, graph: CaseGraph) -> None:
    district = graph.district
    tx.run(
        "MERGE (c:Case {case_id: $case_id}) SET c.district = $normalized, "
        "c.district_display = $display, c.district_file = $file, c.district_line = $line",
        case_id=graph.case_id,
        normalized=district.normalized if district else None,
        display=district.display_value if district else None,
        file=district.file if district else None,
        line=district.line if district else None,
    ).consume()
    for type_ in EntityType:
        rows = [
            {"entity_id": e.entity_id, "props": _entity_props(e)}
            for e in graph.entities
            if e.type is type_
        ]
        if rows:
            tx.run(_entity_write(type_), rows=rows).consume()
    mention_rows = [
        {"mention_id": m.mention_id, "entity_id": m.entity_id, "props": _mention_props(m, i)}
        for i, m in enumerate(graph.mentions)
    ]
    tx.run(_MENTION_WRITE, rows=mention_rows).consume()
    place_rows = [
        {"place_id": p.place_id, "props": _place_props(p, i)} for i, p in enumerate(graph.places)
    ]
    tx.run(_PLACE_WRITE, rows=place_rows).consume()
    for edge_type in EdgeType:
        edge_rows = [
            {
                "edge_id": e.edge_id,
                "source_id": e.source_id,
                "target_id": e.target_id,
                "props": _edge_props(e, i),
            }
            for i, e in enumerate(graph.edges)
            if e.type is edge_type
        ]
        if edge_rows:
            tx.run(_edge_write(edge_type), rows=edge_rows).consume()


def _entity_props(entity: Entity) -> dict[str, object]:
    props: dict[str, object] = {
        "entity_id": entity.entity_id,
        "case_id": entity.case_id,
        "type": entity.type.value,
        "ordinal": entity.ordinal,
        "normalized": entity.normalized,
        "display_value": entity.display_value,
        "confidence": entity.confidence,
        "file": entity.file,
        "line": entity.line,
        "shared_wording": entity.shared_wording,
    }
    if entity.aliases:
        props["aliases"] = list(entity.aliases)
    if entity.ifsc is not None:
        props["ifsc"] = entity.ifsc
    return props


def _mention_props(mention: Mention, position: int) -> dict[str, object]:
    props: dict[str, object] = {
        "mention_id": mention.mention_id,
        "entity_id": mention.entity_id,
        "case_id": mention.case_id,
        "raw_text": mention.raw_text,
        "normalized": mention.normalized,
        "file": mention.file,
        "line": mention.line,
        "confidence": mention.confidence,
        "position": position,
    }
    for key, value in mention.attributes:
        props[key] = list(value) if isinstance(value, tuple) else value
    return props


def _place_props(place: Place, position: int) -> dict[str, object]:
    return {
        "place_id": place.place_id,
        "case_id": place.case_id,
        "normalized": place.normalized,
        "display_value": place.display_value,
        "position": position,
    }


def _edge_props(edge: Edge, position: int) -> dict[str, object]:
    props: dict[str, object] = {
        "edge_id": edge.edge_id,
        "case_id": edge.case_id,
        "file": edge.file,
        "line": edge.line,
        "confidence": edge.confidence,
        "raw_text": edge.raw_text,
        "position": position,
    }
    if edge.hedged is not None:
        props["hedged"] = edge.hedged
    props.update(edge.properties)
    return props


def _read(tx: ManagedTransaction, case_id: str) -> CaseGraph | None:
    entity_rows = tx.run(
        "MATCH (e:Entity {case_id: $case_id}) RETURN properties(e) AS p ORDER BY e.ordinal",
        case_id=case_id,
    )
    entities = tuple(_to_entity(r["p"]) for r in entity_rows)
    if not entities:
        return None
    mention_rows = tx.run(
        "MATCH (m:Mention {case_id: $case_id}) RETURN properties(m) AS p ORDER BY m.position",
        case_id=case_id,
    )
    place_rows = tx.run(
        "MATCH (p:Place {case_id: $case_id}) RETURN properties(p) AS p ORDER BY p.position",
        case_id=case_id,
    )
    edge_rows = tx.run(
        "MATCH (a:Entity {case_id: $case_id})-[r]->(b) "
        "WHERE type(r) IN $types AND r.case_id = $case_id "
        "RETURN type(r) AS type, a.entity_id AS source_id, "
        "coalesce(b.entity_id, b.place_id) AS target_id, properties(r) AS p "
        "ORDER BY r.position",
        case_id=case_id,
        types=_EDGE_TYPES,
    )
    case_row = tx.run(
        "MATCH (c:Case {case_id: $case_id}) RETURN properties(c) AS p", case_id=case_id
    ).single()
    return CaseGraph(
        case_id=case_id,
        district=_to_district(case_row["p"]) if case_row else None,
        entities=entities,
        mentions=tuple(_to_mention(r["p"]) for r in mention_rows),
        places=tuple(_to_place(r["p"]) for r in place_rows),
        edges=tuple(_to_edge(r["type"], r["source_id"], r["target_id"], r["p"]) for r in edge_rows),
    )


def _to_district(props: Mapping[str, object]) -> CaseDistrict | None:
    normalized = props.get("district")
    if normalized is None:
        return None
    return CaseDistrict(
        normalized=str(normalized),
        display_value=str(props["district_display"]),
        file=str(props["district_file"]),
        line=int(str(props["district_line"])),
    )


def _to_entity(props: Mapping[str, object]) -> Entity:
    ifsc = props.get("ifsc")
    aliases = props.get("aliases")
    return Entity(
        entity_id=str(props["entity_id"]),
        case_id=str(props["case_id"]),
        type=EntityType(str(props["type"])),
        ordinal=int(str(props["ordinal"])),
        normalized=str(props["normalized"]),
        display_value=str(props["display_value"]),
        confidence=float(str(props["confidence"])),
        file=str(props["file"]),
        line=int(str(props["line"])),
        aliases=tuple(str(a) for a in aliases) if isinstance(aliases, list) else (),
        ifsc=str(ifsc) if ifsc is not None else None,
        shared_wording=bool(props["shared_wording"]),
    )


def _to_mention(props: Mapping[str, object]) -> Mention:
    attributes: list[tuple[str, AttrValue]] = []
    for key, value in props.items():
        if key in _MENTION_FIELDS:
            continue
        if isinstance(value, list):
            attributes.append((key, tuple(str(v) for v in value)))
        elif isinstance(value, bool | str):
            attributes.append((key, value))
    return Mention(
        mention_id=str(props["mention_id"]),
        entity_id=str(props["entity_id"]),
        case_id=str(props["case_id"]),
        raw_text=str(props["raw_text"]),
        normalized=str(props["normalized"]),
        file=str(props["file"]),
        line=int(str(props["line"])),
        confidence=float(str(props["confidence"])),
        attributes=tuple(sorted(attributes)),
    )


def _to_place(props: Mapping[str, object]) -> Place:
    return Place(
        place_id=str(props["place_id"]),
        case_id=str(props["case_id"]),
        normalized=str(props["normalized"]),
        display_value=str(props["display_value"]),
    )


def _to_edge(type_: str, source_id: str, target_id: str, props: Mapping[str, object]) -> Edge:
    hedged = props.get("hedged")
    extra: list[tuple[str, Scalar]] = [
        (k, v)
        for k, v in props.items()
        if k not in _EDGE_FIELDS and isinstance(v, str | int | float | bool)
    ]
    return Edge(
        edge_id=str(props["edge_id"]),
        case_id=str(props["case_id"]),
        type=EdgeType(type_),
        source_id=source_id,
        target_id=target_id,
        file=str(props["file"]),
        line=int(str(props["line"])),
        confidence=float(str(props["confidence"])),
        raw_text=str(props["raw_text"]),
        hedged=bool(hedged) if hedged is not None else None,
        properties=tuple(sorted(extra)),
    )
