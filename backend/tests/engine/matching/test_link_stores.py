"""Both link stores behave the same; the matcher gives the same edges over Neo4j and in memory.

Neo4j tests run when `NEO4J_URI` is set (with `NEO4J_USER` and `NEO4J_PASSWORD`) and are
skipped with a visible reason otherwise. They load the worked-scenario cases C-101 and C-201
and delete every node of those cases before and after each test.
"""

import os
from collections.abc import Iterator
from dataclasses import replace

import pytest
from neo4j import Driver, GraphDatabase

from tests.engine.matching.fixtures import AC01_FIXTURE, ac01_graphs, matcher
from tracex_engine.graph import (
    CaseGraph,
    CaseGraphStore,
    InMemoryCaseGraphStore,
    Neo4jCaseGraphStore,
)
from tracex_engine.matching import (
    InMemoryLinkStore,
    LinkConflictError,
    LinkState,
    LinkStore,
    Neo4jLinkStore,
    SameAsEdge,
)

NEO4J_URI = os.environ.get("NEO4J_URI")
NEEDS_NEO4J = pytest.mark.skipif(
    not NEO4J_URI, reason="NEO4J_URI not set: Neo4j integration tests skipped"
)
STORES = ["memory", pytest.param("neo4j", marks=NEEDS_NEO4J)]
CASES = ("C-101", "C-201")


def driver() -> Driver:
    assert NEO4J_URI
    auth = (os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", ""))
    return GraphDatabase.driver(NEO4J_URI, auth=auth)


def clean(d: Driver) -> None:
    d.execute_query("MATCH (n) WHERE n.case_id IN $cases DETACH DELETE n", cases=list(CASES))


@pytest.fixture
def stores(request: pytest.FixtureRequest) -> Iterator[tuple[CaseGraphStore, LinkStore]]:
    if request.param == "memory":
        yield InMemoryCaseGraphStore(), InMemoryLinkStore()
        return
    d = driver()
    clean(d)
    graphs, links = Neo4jCaseGraphStore(d), Neo4jLinkStore(d)
    graphs.ensure_schema()
    links.ensure_schema()
    try:
        yield graphs, links
    finally:
        clean(d)
        d.close()


def loaded(graphs: CaseGraphStore) -> tuple[CaseGraph, CaseGraph]:
    pair = ac01_graphs()
    for g in pair:
        graphs.write_case(g)
    return pair


def first_edge(graphs: CaseGraphStore, links: LinkStore) -> SameAsEdge:
    m = matcher(store=graphs, links=links, fixture=AC01_FIXTURE)
    m.run_matching(input_case_ids=(), triggered_by="u-admin")
    return next(e for e in links.edges() if e.entity_type.value == "PERSON")


@pytest.mark.parametrize("stores", STORES, indirect=True)
def test_an_edge_reads_back_exactly_as_written(stores: tuple[CaseGraphStore, LinkStore]) -> None:
    graphs, links = stores
    loaded(graphs)

    edge = first_edge(graphs, links)

    assert links.get(edge.link_id) == edge
    assert len(links.edges()) == 4
    assert links.get("no-such-link") is None


@pytest.mark.parametrize("stores", STORES, indirect=True)
def test_a_pair_holds_one_edge_and_a_link_id_never_moves(
    stores: tuple[CaseGraphStore, LinkStore],
) -> None:
    graphs, links = stores
    loaded(graphs)
    edge = first_edge(graphs, links)
    phone = next(e for e in links.edges() if e.entity_type.value == "PHONE")

    with pytest.raises(LinkConflictError):
        links.put(replace(edge, link_id="00000000-0000-4000-8000-00000000ffff"))
    with pytest.raises(LinkConflictError):
        links.put(
            replace(
                edge,
                entity_a_id=phone.entity_a_id,
                entity_b_id=phone.entity_b_id,
                link_id=edge.link_id,
            )
        )
    assert links.get(edge.link_id) == edge


@pytest.mark.parametrize("stores", STORES, indirect=True)
def test_replace_and_remove(stores: tuple[CaseGraphStore, LinkStore]) -> None:
    graphs, links = stores
    loaded(graphs)
    edge = first_edge(graphs, links)

    links.put(replace(edge, state=LinkState.CONFIRMED))
    assert links.get(edge.link_id) == replace(edge, state=LinkState.CONFIRMED)
    links.remove(edge.link_id)
    assert links.get(edge.link_id) is None and len(links.edges()) == 3


@pytest.mark.parametrize("stores", STORES, indirect=True)
def test_edges_survive_a_case_rewrite(stores: tuple[CaseGraphStore, LinkStore]) -> None:
    graphs, links = stores
    pair = loaded(graphs)
    first_edge(graphs, links)
    before = links.edges()

    for g in pair:
        graphs.write_case(g)

    assert links.edges() == before


@NEEDS_NEO4J
def test_the_matcher_gives_the_same_edges_over_neo4j_and_in_memory() -> None:
    d = driver()
    clean(d)
    try:
        neo = (Neo4jCaseGraphStore(d), Neo4jLinkStore(d))
        mem = (InMemoryCaseGraphStore(), InMemoryLinkStore())
        shapes = []
        for graphs, links in (neo, mem):
            graphs.ensure_schema()
            links.ensure_schema()
            loaded(graphs)
            m = matcher(store=graphs, links=links, fixture=AC01_FIXTURE)
            m.run_matching(input_case_ids=(), triggered_by="u-admin")
            again = m.run_matching(input_case_ids=(), triggered_by="u-admin")
            assert again.transitions == ()
            shapes.append(
                [(e.pair, e.state, e.score, e.gates_failed, e.evidence) for e in links.edges()]
            )
        assert shapes[0] == shapes[1]
    finally:
        clean(d)
        d.close()
