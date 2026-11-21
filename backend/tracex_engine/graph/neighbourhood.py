"""Identifier neighbourhoods and seen-at pairs over case graphs (engine-matching section 3.2).

Pure reads over `CaseGraph`s; nothing here knows flags, tiers or scores (the caller filters).

    NetworkIndex.neighbourhood(entity_id)   identifiers within 2 hops through `owns`, `called`
                                            and `transferred to`, edge direction ignored; each
                                            with the lines of the edges on the paths to it.
                                            `registered to` and `mentioned alongside` are not
                                            hops. A path may pass through any identifier.
    NetworkIndex.owned(entity_id, type)     identifiers of one type the entity `owns`
    NetworkIndex.seen_at(entity_id)         (place, call date, line) of a phone, from its CDR rows
    match_seen_at(a, b)                     the place-date pairs two lists share, dates +-1 day

Every line returned belongs to the case of the entity it was read for.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from tracex_engine.graph.model import CaseGraph, Edge, EdgeType, EntityType
from tracex_engine.graph.order import file_load_key
from tracex_engine.ingest import SourceRef

HOP_EDGES = frozenset({EdgeType.OWNS, EdgeType.CALLED, EdgeType.TRANSFERRED_TO})
IDENTIFIER_TYPES = frozenset({EntityType.PHONE, EntityType.ACCOUNT, EntityType.VEHICLE})
MAX_HOPS = 2
DAY_TOLERANCE = 1


@dataclass(frozen=True)
class SeenAt:
    """A phone recorded at a place on a date, citing the CDR row."""

    place: str
    day: date
    source: SourceRef


def _line_key(source: SourceRef) -> tuple[tuple[int, int, str], int]:
    return (file_load_key(source.file), source.line)


def sorted_lines(lines: Iterable[SourceRef]) -> tuple[SourceRef, ...]:
    """Distinct lines in load order (file order, then line)."""
    return tuple(sorted(set(lines), key=lambda s: (s.case_id, *_line_key(s))))


def _ref(edge: Edge) -> SourceRef:
    return SourceRef(edge.case_id, edge.file, edge.line)


class NetworkIndex:
    """Adjacency over the hop edges and the seen-at records of every given case graph."""

    def __init__(self, graphs: Iterable[CaseGraph]) -> None:
        self._types: dict[str, EntityType] = {}
        self._hops: dict[str, list[tuple[str, SourceRef]]] = defaultdict(list)
        self._owned: dict[str, list[str]] = defaultdict(list)
        self._seen: dict[str, list[SeenAt]] = defaultdict(list)
        for graph in graphs:
            self._add(graph)

    def _add(self, graph: CaseGraph) -> None:
        for entity in graph.entities:
            self._types[entity.entity_id] = entity.type
        places = {p.place_id: p.normalized for p in graph.places}
        for edge in graph.edges:
            if edge.type in HOP_EDGES:
                ref = _ref(edge)
                self._hops[edge.source_id].append((edge.target_id, ref))
                self._hops[edge.target_id].append((edge.source_id, ref))
            if edge.type is EdgeType.OWNS:
                self._owned[edge.source_id].append(edge.target_id)
            elif edge.type is EdgeType.SEEN_AT:
                day = _call_date(edge)
                place = places.get(edge.target_id)
                if day is not None and place:
                    self._seen[edge.source_id].append(SeenAt(place, day, _ref(edge)))

    def neighbourhood(self, entity_id: str) -> dict[str, tuple[SourceRef, ...]]:
        """Identifier id -> lines of the edges on every path (1 to 2 hops) from the entity."""
        paths: dict[str, set[SourceRef]] = defaultdict(set)
        frontier: dict[str, set[SourceRef]] = {entity_id: set()}
        for _ in range(MAX_HOPS):
            step: dict[str, set[SourceRef]] = defaultdict(set)
            for node, via in frontier.items():
                for other, ref in self._hops.get(node, ()):
                    if other == entity_id:
                        continue
                    step[other] |= via | {ref}
            for node, lines in step.items():
                if self._types.get(node) in IDENTIFIER_TYPES:
                    paths[node] |= lines
            frontier = step
        return {i: sorted_lines(lines) for i, lines in sorted(paths.items())}

    def owned(self, entity_id: str, type_: EntityType) -> tuple[str, ...]:
        """Distinct identifiers of `type_` the entity owns, in the order stated."""
        found = dict.fromkeys(
            i for i in self._owned.get(entity_id, ()) if self._types.get(i) is type_
        )
        return tuple(found)

    def seen_at(self, entity_id: str) -> tuple[SeenAt, ...]:
        return tuple(self._seen.get(entity_id, ()))


def _call_date(edge: Edge) -> date | None:
    for key, value in edge.properties:
        if key == "on" and isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
    return None


def match_seen_at(a: Sequence[SeenAt], b: Sequence[SeenAt]) -> tuple[tuple[SeenAt, SeenAt], ...]:
    """Distinct (place, date) units both lists share, each unit used once, dates +-1 day.

    A unit is one place on one date; it is cited by its earliest row. Per place the units are
    matched greedily in date order, which finds the largest set of one-to-one matches.
    """
    first_a, first_b = _units(a), _units(b)
    matched: list[tuple[SeenAt, SeenAt]] = []
    for place in sorted(first_a.keys() & first_b.keys()):
        days_b = sorted(first_b[place])
        j = 0
        for day_a in sorted(first_a[place]):
            while j < len(days_b) and days_b[j] < day_a - timedelta(days=DAY_TOLERANCE):
                j += 1
            if j < len(days_b) and days_b[j] <= day_a + timedelta(days=DAY_TOLERANCE):
                matched.append((first_a[place][day_a], first_b[place][days_b[j]]))
                j += 1
    return tuple(matched)


def _units(records: Sequence[SeenAt]) -> dict[str, dict[date, SeenAt]]:
    units: dict[str, dict[date, SeenAt]] = defaultdict(dict)
    for record in sorted(records, key=lambda r: (r.place, r.day, _line_key(r.source))):
        units[record.place].setdefault(record.day, record)
    return units
