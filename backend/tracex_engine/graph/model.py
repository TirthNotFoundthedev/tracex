"""Case-graph types. All are immutable and carry provenance (case, file, line)."""

from dataclasses import dataclass
from enum import StrEnum

Scalar = str | int | float | bool
AttrValue = str | bool | tuple[str, ...]


class EntityType(StrEnum):
    PERSON = "PERSON"
    ORG = "ORG"
    PHONE = "PHONE"
    ACCOUNT = "ACCOUNT"
    VEHICLE = "VEHICLE"


class EdgeType(StrEnum):
    OWNS = "OWNS"
    REGISTERED_TO = "REGISTERED_TO"
    MENTIONED_WITH = "MENTIONED_WITH"
    CALLED = "CALLED"
    TRANSFERRED_TO = "TRANSFERRED_TO"
    SEEN_AT = "SEEN_AT"


@dataclass(frozen=True)
class Entity:
    """One real thing inside one case, standing for one or more mentions.

    `normalized`, `display_value`, `file` and `line` come from the first mention; `confidence`
    is the highest mention confidence; `aliases` are the normalized aliases any mention stated.
    """

    entity_id: str
    case_id: str
    type: EntityType
    ordinal: int
    normalized: str
    display_value: str
    confidence: float
    file: str
    line: int
    aliases: tuple[str, ...] = ()
    ifsc: str | None = None
    shared_wording: bool = False


@dataclass(frozen=True)
class Mention:
    """One writing of an entity, as the extractor read it.

    `attributes` are sorted key/value pairs of what that writing stated: for a person `role`,
    `age`, `dob`, `gender`, `locality`, `district`, `relative_relation`, `relative_name`,
    `aliases`; for an identifier `ifsc` and `shared_wording`. A value read from text keeps its
    written form under the same key with a `_raw` suffix.
    """

    mention_id: str
    entity_id: str
    case_id: str
    raw_text: str
    normalized: str
    file: str
    line: int
    confidence: float
    attributes: tuple[tuple[str, AttrValue], ...] = ()


@dataclass(frozen=True)
class Place:
    """A tower place named in one case's call records. Evidence only, never linked."""

    place_id: str
    case_id: str
    normalized: str
    display_value: str


@dataclass(frozen=True)
class Edge:
    """One relationship from one statement or row; `raw_text` is that statement or row.

    `source_id` is an entity id; `target_id` is an entity id, or a place id for SEEN_AT.
    `hedged` is set on attribution edges only.
    """

    edge_id: str
    case_id: str
    type: EdgeType
    source_id: str
    target_id: str
    file: str
    line: int
    confidence: float
    raw_text: str
    hedged: bool | None = None
    properties: tuple[tuple[str, Scalar], ...] = ()


@dataclass(frozen=True)
class CaseDistrict:
    """The district a case's FIR header states, with the line it was read from."""

    normalized: str
    display_value: str
    file: str
    line: int


@dataclass(frozen=True)
class CaseGraph:
    """The graph of one case: entities by ordinal, mentions and edges in load order."""

    case_id: str
    entities: tuple[Entity, ...]
    mentions: tuple[Mention, ...]
    places: tuple[Place, ...]
    edges: tuple[Edge, ...]
    district: CaseDistrict | None = None
