"""Case graph stores: write idempotently, read back what was built, look up values across cases.

The same tests run against the in-memory store and, when `NEO4J_URI` is set (with `NEO4J_USER`
and `NEO4J_PASSWORD`, as in `.env.example`), against a real Neo4j. They use case ids C-901 to
C-903, which no kit case uses, and remove only those cases' nodes before and after.
"""

import os
from collections import Counter
from collections.abc import Iterator

import pytest
from neo4j import Driver, GraphDatabase

from tests.engine.support import (
    BANK_HEADER,
    CDR_HEADER,
    cdr_row,
    fir_file,
    note,
    notes_file,
    pinned_file,
)
from tracex_engine.extract import extract_case
from tracex_engine.graph import (
    CaseGraph,
    CaseGraphStore,
    EdgeType,
    EntityType,
    InMemoryCaseGraphStore,
    Neo4jCaseGraphStore,
    build_case_graph,
)

NEO4J_URI = os.environ.get("NEO4J_URI")
TEST_CASES = ("C-901", "C-902", "C-903")

STORES = [
    "memory",
    pytest.param(
        "neo4j",
        marks=pytest.mark.skipif(
            not NEO4J_URI, reason="NEO4J_URI not set: Neo4j integration tests skipped"
        ),
    ),
]


def make_graph(case_id: str, phone: str = "9000014471") -> CaseGraph:
    row = (
        f"SYN-{case_id}-3,2026-09-18T10:15:00+05:30,75,9000021203,{phone},"
        "VOICE,CELL9,Hillcrest Market"
    )
    bank = (
        f"TX1,2026-09-10,5010000019082,SYNB0000123,MOHD IRFAN,DR,{phone}@upi,pay,1500.00,20000.50"
    )
    files = {
        "fir.txt": fir_file(case_id, {12: "The accused Mohd. Irfan, mobile 90000 14471, fled."}),
        "notes.txt": notes_file(case_id, {3: note(f"Number {phone} is used by Irfan bhai.")}),
        "cdr.csv": pinned_file({1: CDR_HEADER, 3: row}, lambda n: cdr_row(n), last=3),
        "bank.csv": f"{BANK_HEADER}\n{bank}\n",
    }
    return build_case_graph(extract_case(case_id, files))


def neo4j_driver() -> Driver:
    assert NEO4J_URI
    auth = (os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", ""))
    return GraphDatabase.driver(NEO4J_URI, auth=auth)


def clean(driver: Driver) -> None:
    driver.execute_query("MATCH (n) WHERE n.case_id IN $cases DETACH DELETE n", cases=TEST_CASES)


@pytest.fixture(params=STORES)
def store(request: pytest.FixtureRequest) -> Iterator[CaseGraphStore]:
    if request.param == "memory":
        yield InMemoryCaseGraphStore()
        return
    driver = neo4j_driver()
    clean(driver)
    adapter = Neo4jCaseGraphStore(driver)
    adapter.ensure_schema()
    yield adapter
    clean(driver)
    driver.close()


def test_a_written_case_reads_back_equal_to_the_built_graph(store: CaseGraphStore) -> None:
    graph = make_graph("C-901")
    assert graph.places and graph.edges and graph.mentions

    store.write_case(graph)

    assert store.read_case("C-901") == graph


def test_writing_the_same_case_twice_changes_nothing(store: CaseGraphStore) -> None:
    graph = make_graph("C-901")

    store.write_case(graph)
    store.write_case(graph)

    assert store.read_case("C-901") == graph
    assert len(store.find_entities(EntityType.PHONE, "9000014471")) == 1


def test_an_unknown_case_reads_as_none(store: CaseGraphStore) -> None:
    assert store.read_case("C-903") is None


def test_cases_are_read_separately_and_listed_in_numeric_order(store: CaseGraphStore) -> None:
    store.write_case(make_graph("C-902"))
    store.write_case(make_graph("C-901"))

    assert [c for c in store.case_ids() if c in TEST_CASES] == ["C-901", "C-902"]
    assert {e.case_id for e in (store.read_case("C-901") or make_graph("C-903")).entities} == {
        "C-901"
    }


def test_an_exact_value_lookup_finds_the_entity_in_every_case_in_id_order(
    store: CaseGraphStore,
) -> None:
    store.write_case(make_graph("C-902"))
    store.write_case(make_graph("C-901"))

    found = store.find_entities(EntityType.PHONE, "9000014471")

    assert [e.case_id for e in found] == ["C-901", "C-902"]
    assert all(e.type is EntityType.PHONE and e.normalized == "9000014471" for e in found)
    assert store.find_entities(EntityType.ACCOUNT, "9000014471") == ()
    assert store.find_entities(EntityType.PHONE, "9999999999") == ()


def test_ensure_schema_can_run_again(store: CaseGraphStore) -> None:
    store.ensure_schema()
    store.ensure_schema()


@pytest.fixture
def driver() -> Iterator[Driver]:
    if not NEO4J_URI:
        pytest.skip("NEO4J_URI not set: Neo4j integration tests skipped")
    connection = neo4j_driver()
    clean(connection)
    yield connection
    clean(connection)
    connection.close()


@pytest.mark.skipif(not NEO4J_URI, reason="NEO4J_URI not set: Neo4j integration tests skipped")
class TestNeo4jOnly:
    """Properties only a real database has: constraints, relationship types, SAME_AS."""

    def test_the_matchers_lookup_has_its_constraints_and_indexes(self, driver: Driver) -> None:
        Neo4jCaseGraphStore(driver).ensure_schema()

        records, _, _ = driver.execute_query("SHOW CONSTRAINTS YIELD labelsOrTypes, properties")
        constraints = {(tuple(r["labelsOrTypes"]), tuple(r["properties"])) for r in records}
        records, _, _ = driver.execute_query("SHOW INDEXES YIELD labelsOrTypes, properties")
        indexes = {(tuple(r["labelsOrTypes"] or ()), tuple(r["properties"] or ())) for r in records}
        assert (("Entity",), ("entity_id",)) in constraints
        assert (("Mention",), ("mention_id",)) in constraints
        assert (("Place",), ("place_id",)) in constraints
        assert (("Entity",), ("type", "normalized")) in indexes
        assert (("Entity",), ("case_id",)) in indexes

    def test_edges_are_real_relationship_types_between_entity_nodes(self, driver: Driver) -> None:
        store = Neo4jCaseGraphStore(driver)
        store.ensure_schema()
        store.write_case(make_graph("C-901"))

        records, _, _ = driver.execute_query(
            "MATCH (a:Entity {case_id: 'C-901'})-[r]->(b) "
            "RETURN type(r) AS t, count(r) AS n ORDER BY t"
        )
        counts = {r["t"]: r["n"] for r in records}
        built = make_graph("C-901")
        expected = Counter(e.type.value for e in built.edges)
        assert set(expected) == {t.value for t in EdgeType} - {"REGISTERED_TO"}
        assert {t: n for t, n in counts.items() if t != "HAS_MENTION"} == dict(expected)
        assert counts["HAS_MENTION"] == len(built.mentions)

    def test_a_same_as_edge_survives_loading_a_case_again_and_is_not_part_of_the_case(
        self, driver: Driver
    ) -> None:
        store = Neo4jCaseGraphStore(driver)
        store.ensure_schema()
        first, second = make_graph("C-901"), make_graph("C-902")
        store.write_case(first)
        store.write_case(second)
        phone_a = store.find_entities(EntityType.PHONE, "9000014471")[0]
        phone_b = store.find_entities(EntityType.PHONE, "9000014471")[1]
        driver.execute_query(
            "MATCH (a:Entity {entity_id: $a}), (b:Entity {entity_id: $b}) "
            "CREATE (a)-[:SAME_AS {link_id: 'test-link'}]->(b)",
            a=phone_a.entity_id,
            b=phone_b.entity_id,
        )

        store.write_case(first)

        records, _, _ = driver.execute_query(
            "MATCH (:Entity)-[r:SAME_AS {link_id: 'test-link'}]->(:Entity) RETURN count(r) AS n"
        )
        assert records[0]["n"] == 1
        assert store.read_case("C-901") == first
        assert store.read_case("C-902") == second
