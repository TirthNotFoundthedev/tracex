"""2-hop identifier neighbourhoods and seen-at place-date pairs (matching spec section 3.2)."""

from datetime import date

from tracex_engine.graph import (
    CaseGraph,
    Edge,
    EdgeType,
    Entity,
    EntityType,
    NetworkIndex,
    Place,
    SeenAt,
    match_seen_at,
)
from tracex_engine.ingest import SourceRef

CASE = "C-101"


def entity(ordinal: int, type_: EntityType, normalized: str) -> Entity:
    return Entity(f"{CASE}:{ordinal}", CASE, type_, ordinal, normalized, normalized, 0.9, "x", 1)


class GraphBuilder:
    """A hand-made case graph: named entities and edges pinned to lines of cdr.csv."""

    def __init__(self) -> None:
        self.entities: dict[str, Entity] = {}
        self.edges: list[Edge] = []
        self.places: dict[str, Place] = {}

    def add(self, type_: EntityType, name: str) -> str:
        found = self.entities.get(name)
        if found is None:
            found = entity(len(self.entities), type_, name)
            self.entities[name] = found
        return found.entity_id

    def edge(
        self,
        type_: EdgeType,
        source: str,
        target: str,
        line: int,
        file: str = "cdr.csv",
        props: tuple[tuple[str, str], ...] = (),
    ) -> None:
        self.edges.append(
            Edge(
                f"e{len(self.edges)}", CASE, type_, source, target, file, line, 0.9, "", None, props
            )
        )

    def seen(self, phone: str, place: str, day: str, line: int) -> None:
        place_id = f"{CASE}:place:{place}"
        self.places[place_id] = Place(place_id, CASE, place, place)
        self.edge(EdgeType.SEEN_AT, phone, place_id, line, props=(("on", day),))

    def graph(self) -> CaseGraph:
        return CaseGraph(
            CASE, tuple(self.entities.values()), (), tuple(self.places.values()), tuple(self.edges)
        )


def refs(*lines: tuple[str, int]) -> tuple[SourceRef, ...]:
    return tuple(SourceRef(CASE, f, n) for f, n in lines)


def hood(builder: GraphBuilder, name: str) -> dict[str, tuple[SourceRef, ...]]:
    ids = {e.entity_id: e.normalized for e in builder.entities.values()}
    found = NetworkIndex([builder.graph()]).neighbourhood(builder.entities[name].entity_id)
    return {ids[i]: lines for i, lines in found.items()}


def test_an_owner_reaches_its_identifier_and_the_counterparties_of_it_in_two_hops() -> None:
    g = GraphBuilder()
    person = g.add(EntityType.PERSON, "irfan")
    mine, other = g.add(EntityType.PHONE, "9000000001"), g.add(EntityType.PHONE, "9000000002")
    g.edge(EdgeType.OWNS, person, mine, 3, "notes.txt")
    g.edge(EdgeType.CALLED, other, mine, 33)

    assert hood(g, "irfan") == {
        "9000000001": refs(("notes.txt", 3)),
        "9000000002": refs(("notes.txt", 3), ("cdr.csv", 33)),
    }


def test_edge_direction_is_ignored_in_both_hops() -> None:
    g = GraphBuilder()
    person = g.add(EntityType.PERSON, "irfan")
    account = g.add(EntityType.ACCOUNT, "5010000000001")
    paid, payer = g.add(EntityType.PHONE, "9000000003"), g.add(EntityType.PHONE, "9000000004")
    g.edge(EdgeType.OWNS, account, person, 12, "fir.txt")
    g.edge(EdgeType.TRANSFERRED_TO, account, paid, 4, "bank.csv")
    g.edge(EdgeType.TRANSFERRED_TO, payer, account, 5, "bank.csv")

    assert set(hood(g, "irfan")) == {"5010000000001", "9000000003", "9000000004"}


def test_a_third_hop_is_not_reached() -> None:
    g = GraphBuilder()
    person = g.add(EntityType.PERSON, "irfan")
    a, b, c = (g.add(EntityType.PHONE, f"900000000{n}") for n in (1, 2, 3))
    g.edge(EdgeType.OWNS, person, a, 3, "notes.txt")
    g.edge(EdgeType.CALLED, a, b, 10)
    g.edge(EdgeType.CALLED, b, c, 11)

    assert set(hood(g, "irfan")) == {"9000000001", "9000000002"}


def test_registered_to_and_mentioned_alongside_are_not_hops() -> None:
    g = GraphBuilder()
    person = g.add(EntityType.PERSON, "kamla devi")
    a, b = g.add(EntityType.PHONE, "9000000001"), g.add(EntityType.PHONE, "9000000002")
    g.edge(EdgeType.REGISTERED_TO, person, a, 2, "sdr.csv")
    g.edge(EdgeType.MENTIONED_WITH, person, b, 5, "fir.txt")
    g.edge(EdgeType.CALLED, a, b, 7)

    assert hood(g, "kamla devi") == {}


def test_two_paths_to_one_identifier_cite_every_line_on_them() -> None:
    g = GraphBuilder()
    person = g.add(EntityType.PERSON, "irfan")
    a, b = g.add(EntityType.PHONE, "9000000001"), g.add(EntityType.PHONE, "9000000002")
    far = g.add(EntityType.PHONE, "9000000009")
    g.edge(EdgeType.OWNS, person, a, 3, "notes.txt")
    g.edge(EdgeType.OWNS, person, b, 4, "notes.txt")
    g.edge(EdgeType.CALLED, far, a, 20)
    g.edge(EdgeType.CALLED, b, far, 21)

    assert hood(g, "irfan")["9000000009"] == refs(
        ("notes.txt", 3), ("notes.txt", 4), ("cdr.csv", 20), ("cdr.csv", 21)
    )


def test_another_person_on_the_same_phone_is_not_an_identifier() -> None:
    g = GraphBuilder()
    one, two = g.add(EntityType.PERSON, "ramesh"), g.add(EntityType.PERSON, "sunita")
    phone = g.add(EntityType.PHONE, "9000000001")
    g.edge(EdgeType.OWNS, one, phone, 3, "notes.txt")
    g.edge(EdgeType.OWNS, two, phone, 4, "notes.txt")

    assert set(hood(g, "ramesh")) == {"9000000001"}


def test_owned_lists_identifiers_of_one_type_once_in_stated_order() -> None:
    g = GraphBuilder()
    person = g.add(EntityType.PERSON, "irfan")
    a, b = g.add(EntityType.PHONE, "9000000002"), g.add(EntityType.PHONE, "9000000001")
    account = g.add(EntityType.ACCOUNT, "5010000000001")
    for line, target in enumerate((a, b, a, account), start=3):
        g.edge(EdgeType.OWNS, person, target, line, "notes.txt")

    index = NetworkIndex([g.graph()])
    assert index.owned(person, EntityType.PHONE) == (a, b)
    assert index.owned(person, EntityType.ACCOUNT) == (account,)


def test_seen_at_gives_place_date_and_cdr_row_of_the_calling_phone() -> None:
    g = GraphBuilder()
    phone = g.add(EntityType.PHONE, "9000000001")
    g.seen(phone, "hillcrest market", "2026-09-18", 33)

    [seen] = NetworkIndex([g.graph()]).seen_at(phone)

    assert seen == SeenAt("hillcrest market", date(2026, 9, 18), SourceRef(CASE, "cdr.csv", 33))


def at(place: str, day: str, line: int = 1) -> SeenAt:
    return SeenAt(place, date.fromisoformat(day), SourceRef(CASE, "cdr.csv", line))


def test_place_dates_match_on_the_same_place_within_one_day() -> None:
    a = [at("market", "2026-09-10", 1), at("station", "2026-09-12", 2)]
    b = [
        at("market", "2026-09-11", 7),
        at("station", "2026-09-14", 8),
        at("temple", "2026-09-12", 9),
    ]

    assert [(x.source.line, y.source.line) for x, y in match_seen_at(a, b)] == [(1, 7)]


def test_each_place_date_is_used_once_and_cited_by_its_earliest_row() -> None:
    a = [
        at("market", "2026-09-10", 5),
        at("market", "2026-09-10", 2),
        at("market", "2026-09-11", 6),
    ]
    b = [at("market", "2026-09-10", 8)]

    matched = match_seen_at(a, b)

    assert [(x.source.line, y.source.line) for x, y in matched] == [(2, 8)]


def test_greedy_matching_finds_the_largest_set_of_pairs() -> None:
    a = [at("market", "2026-09-10", 1), at("market", "2026-09-11", 2)]
    b = [at("market", "2026-09-09", 3), at("market", "2026-09-11", 4)]

    assert len(match_seen_at(a, b)) == 2
