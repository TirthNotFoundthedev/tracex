"""Case-graph edges, provenance, ids and determinism (engine-graph spec sections 1, 3, 4)."""

import pytest

from tests.engine.graph.support import attribute, person, phone, records
from tests.engine.support import (
    BANK_HEADER,
    CDR_HEADER,
    SDR_HEADER,
    cdr_row,
    fir_file,
    note,
    notes_file,
    pinned_file,
)
from tracex_engine.extract import CONFIDENCE_CLEAR, AttributionCode, extract_case
from tracex_engine.graph import (
    CaseGraph,
    Edge,
    EdgeType,
    Entity,
    EntityType,
    build_case_graph,
    entity_sort_key,
)

CASE = "C-201"


def worked_case() -> CaseGraph:
    """C-201 of the worked scenario: note line 3, calls on cdr lines 33 and 41."""
    row33 = (
        "SYN-C-201-33,2026-09-18T10:15:00+05:30,75,9000021203,9000014471,"
        "VOICE,CELL9,Hillcrest Market"
    )
    row41 = (
        "SYN-C-201-41,2026-09-19T11:15:00+05:30,80,9000028816,9000014471,"
        "VOICE,CELL4,Hillcrest Market"
    )
    files = {
        "notes.txt": notes_file(CASE, {3: note("Number 9000014471 is used by Irfan bhai.")}),
        "cdr.csv": pinned_file(
            {1: CDR_HEADER, 33: row33, 41: row41}, lambda n: cdr_row(n), last=45
        ),
    }
    return build_case_graph(extract_case(CASE, files))


def by_value(graph: CaseGraph, normalized: str) -> Entity:
    [entity] = [e for e in graph.entities if e.normalized == normalized]
    return entity


def edges_of(graph: CaseGraph, type_: EdgeType) -> list[Edge]:
    return [e for e in graph.edges if e.type == type_]


def test_the_note_line_gives_an_owns_edge_from_irfan_to_the_phone_citing_line_3() -> None:
    graph = worked_case()

    [owns] = edges_of(graph, EdgeType.OWNS)
    assert owns.source_id == by_value(graph, "irfan").entity_id
    assert owns.target_id == by_value(graph, "9000014471").entity_id
    assert (owns.case_id, owns.file, owns.line) == (CASE, "notes.txt", 3)
    assert owns.hedged is False
    assert owns.confidence == CONFIDENCE_CLEAR
    assert "Irfan bhai" in owns.raw_text


def test_every_call_is_a_called_edge_citing_its_cdr_line() -> None:
    graph = worked_case()

    called = [
        (graph_edge.file, graph_edge.line, dict(graph_edge.properties)["call_id"])
        for graph_edge in edges_of(graph, EdgeType.CALLED)
        if graph_edge.line in (33, 41)
    ]
    assert called == [("cdr.csv", 33, "SYN-C-201-33"), ("cdr.csv", 41, "SYN-C-201-41")]
    first = next(e for e in edges_of(graph, EdgeType.CALLED) if e.line == 33)
    assert first.source_id == by_value(graph, "9000021203").entity_id
    assert first.target_id == by_value(graph, "9000014471").entity_id
    assert dict(first.properties)["duration_sec"] == 75
    assert dict(first.properties)["start_time"] == "2026-09-18T10:15:00+05:30"


def test_the_calling_number_is_seen_at_the_tower_place_on_the_call_date() -> None:
    graph = worked_case()

    seen = [e for e in edges_of(graph, EdgeType.SEEN_AT) if e.line in (33, 41)]
    assert [(dict(e.properties)["on"], e.line) for e in seen] == [
        ("2026-09-18", 33),
        ("2026-09-19", 41),
    ]
    [place] = [p for p in graph.places if p.normalized == "hillcrest market"]
    assert place.place_id == "C-201:place:hillcrest market"
    assert {e.target_id for e in seen} == {place.place_id}
    assert seen[0].source_id == by_value(graph, "9000021203").entity_id


def test_a_bank_row_gives_owns_and_a_transfer_in_the_direction_of_the_money() -> None:
    header = BANK_HEADER
    debit = (
        "TX1,2026-09-10,5010000019082,SYNB0000123,MOHD IRFAN,DR,9000021203@upi,pay,1500.00,20000.50"
    )
    credit = (
        "TX2,2026-09-11,5010000019082,SYNB0000123,MOHD IRFAN,CR,5010000077701,in,250.00,20250.50"
    )
    by_name = (
        "TX3,2026-09-12,5010000019082,SYNB0000123,MOHD IRFAN,DR,RAMESH TRADERS,pay,10.00,20240.50"
    )
    text = f"{header}\n{debit}\n{credit}\n{by_name}\n"

    graph = build_case_graph(extract_case("C-101", {"bank.csv": text}))

    account = by_value(graph, "5010000019082")
    [debit_edge, credit_edge] = edges_of(graph, EdgeType.TRANSFERRED_TO)
    assert (debit_edge.source_id, debit_edge.target_id) == (
        account.entity_id,
        by_value(graph, "9000021203").entity_id,
    )
    assert (credit_edge.source_id, credit_edge.target_id) == (
        by_value(graph, "5010000077701").entity_id,
        account.entity_id,
    )
    assert (debit_edge.file, debit_edge.line, credit_edge.line) == ("bank.csv", 2, 3)
    assert dict(debit_edge.properties)["amount_inr"] == "1500.00"
    assert dict(debit_edge.properties)["txn_date"] == "2026-09-10"
    assert len(edges_of(graph, EdgeType.OWNS)) == 3
    assert {e.line for e in edges_of(graph, EdgeType.OWNS)} == {2, 3, 4}
    assert len(edges_of(graph, EdgeType.TRANSFERRED_TO)) == 2


def test_a_subscriber_row_gives_registered_to_never_owns() -> None:
    row = "9000014471,Irfan Khan,Salim Khan,Hillcrest,Hillcrest,2020-01-01"
    text = f"{SDR_HEADER}\n{row}\n"

    graph = build_case_graph(extract_case(CASE, {"sdr.csv": text}))

    [edge] = edges_of(graph, EdgeType.REGISTERED_TO)
    assert (edge.file, edge.line) == ("sdr.csv", 2)
    assert edges_of(graph, EdgeType.OWNS) == []


def test_a_hedged_statement_is_mentioned_with_and_keeps_the_hedge_and_lower_confidence() -> None:
    holder = person("Irfan", 3, "notes.txt", confidence=0.5)
    number = phone("9000014471", 3, "notes.txt")

    graph = build_case_graph(
        records(
            persons=(holder,),
            identifiers=(number,),
            attributions=(attribute(holder, number, AttributionCode.MENTIONED_WITH, hedged=True),),
            case_id="C-101",
        )
    )

    [edge] = graph.edges
    assert edge.type is EdgeType.MENTIONED_WITH
    assert edge.hedged is True
    assert edge.confidence == 0.5


def test_one_edge_per_statement_so_repeated_statements_keep_their_own_lines() -> None:
    holder_a = person("Ramesh Yadav", 12)
    holder_b = person("Ramesh Yadav", 13)
    number = phone("9000014471", 12)

    graph = build_case_graph(
        records(
            persons=(holder_a, holder_b),
            identifiers=(number,),
            attributions=(attribute(holder_a, number), attribute(holder_b, number, line=13)),
        )
    )

    owns = edges_of(graph, EdgeType.OWNS)
    assert [e.line for e in owns] == [12, 13]
    assert len({e.edge_id for e in owns}) == 2
    assert len({e.source_id for e in owns}) == 1


def test_every_node_and_edge_lies_inside_the_case_and_cites_a_real_line() -> None:
    graph = worked_case()
    entity_ids = {e.entity_id for e in graph.entities}
    place_ids = {p.place_id for p in graph.places}

    assert {m.entity_id for m in graph.mentions} <= entity_ids
    for edge in graph.edges:
        assert edge.case_id == CASE and edge.line >= 1 and edge.file
        assert edge.source_id in entity_ids
        assert edge.target_id in entity_ids | place_ids
    for entity in graph.entities:
        assert entity.case_id == CASE and entity.file and entity.line >= 1


def test_mention_counts_equal_the_extractors_per_type() -> None:
    files = {
        "fir.txt": fir_file(
            CASE,
            {12: "The accused Mohd. Irfan, mobile 90000 14471, a/c 5010000019082, fled."},
        ),
        "notes.txt": notes_file(CASE, {3: note("Number 9000014471 is used by Irfan bhai.")}),
    }
    extracted = extract_case(CASE, files)

    graph = build_case_graph(extracted)

    kinds = [e.type for e in graph.entities]
    by_entity = {e.entity_id: e.type for e in graph.entities}
    mention_types = [by_entity[m.entity_id] for m in graph.mentions]
    assert mention_types.count(EntityType.PERSON) == len(extracted.persons)
    assert mention_types.count(EntityType.PHONE) + mention_types.count(
        EntityType.ACCOUNT
    ) + mention_types.count(EntityType.VEHICLE) == len(extracted.identifiers)
    assert kinds.count(EntityType.PHONE) == 1


def test_building_twice_gives_equal_graphs() -> None:
    assert worked_case() == worked_case()


def test_entity_ids_follow_load_order_not_dictionary_order() -> None:
    files = {
        "bank.csv": (
            f"{BANK_HEADER}\nTX1,2026-09-10,5010000019082,SYNB0000123,MOHD IRFAN,DR,,x,1.00,2.00\n"
        ),
        "notes-02.txt": notes_file(CASE, {3: note("Number 9000079900 is used by Jaswinder.")}),
        "notes.txt": notes_file(CASE, {3: note("Number 9000011111 is used by Jaswinder.")}),
        "fir.txt": fir_file(CASE, {}),
    }

    graph = build_case_graph(extract_case(CASE, files))

    first_files = [e.file for e in sorted(graph.entities, key=lambda e: e.ordinal)]
    assert first_files.index("fir.txt") < first_files.index("notes.txt")
    assert first_files.index("notes.txt") < first_files.index("bank.csv")
    assert first_files.index("bank.csv") < first_files.index("notes-02.txt")
    assert [e.entity_id for e in graph.entities] == sorted(e.entity_id for e in graph.entities)
    assert graph.entities[0].entity_id == "C-201:00001"


def test_a_later_batch_only_appends_ids() -> None:
    base = {
        "fir.txt": fir_file(CASE, {}),
        "notes.txt": notes_file(CASE, {3: note("Number 9000011111 is used by Jaswinder.")}),
    }
    later = {
        **base,
        "notes-02.txt": notes_file(CASE, {3: note("Number 9000079900 is used by Jaswinder.")}),
    }

    before = build_case_graph(extract_case(CASE, base))
    after = build_case_graph(extract_case(CASE, later))

    assert set(before.entities) <= set(after.entities)
    assert set(before.mentions) <= set(after.mentions)
    assert set(before.edges) <= set(after.edges)


@pytest.mark.parametrize(
    ("low", "high"),
    [
        (("C-150", 9), ("C-1100", 1)),
        (("C-101", 5), ("C-101", 6)),
        (("C-109", 99), ("C-201", 1)),
    ],
)
def test_sort_key_orders_case_ids_numerically_then_by_ordinal(
    low: tuple[str, int], high: tuple[str, int]
) -> None:
    assert entity_sort_key(f"{low[0]}:{low[1]:05d}") < entity_sort_key(f"{high[0]}:{high[1]:05d}")
