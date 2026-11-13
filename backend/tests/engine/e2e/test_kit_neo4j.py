"""The kit pipeline over Neo4j (case graphs and SAME_AS edges), b01: same edges as in memory and
the same scorer verdict. Runs when `NEO4J_URI` is set; skipped with a visible reason otherwise.
(b02 over Neo4j adds only case rewrites, covered by the link-store tests, at twice the time.)"""

import os
from pathlib import Path

import pytest
from neo4j import GraphDatabase

from tests.engine.e2e.conftest import KitRun
from tests.engine.e2e.kit import batch_cases, result_document, run_batches, score
from tracex_engine.graph import Neo4jCaseGraphStore
from tracex_engine.matching import Neo4jLinkStore

NEO4J_URI = os.environ.get("NEO4J_URI")


@pytest.mark.skipif(not NEO4J_URI, reason="NEO4J_URI not set: Neo4j integration tests skipped")
def test_the_kit_over_neo4j_matches_the_in_memory_run(
    kit: Path, run_b01: KitRun, tmp_path: Path
) -> None:
    assert NEO4J_URI
    auth = (os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", ""))
    driver = GraphDatabase.driver(NEO4J_URI, auth=auth)
    cases = batch_cases(kit, "b01")

    def clean() -> None:
        driver.execute_query("MATCH (n) WHERE n.case_id IN $cases DETACH DELETE n", cases=cases)

    clean()
    try:
        graphs, links = Neo4jCaseGraphStore(driver), Neo4jLinkStore(driver)
        graphs.ensure_schema()
        links.ensure_schema()

        _, results = run_batches(graphs, links, kit, "b01")
        report = score(kit, result_document(graphs, links, ["b01"], results[-1]), tmp_path)

        def shape(edges: object) -> list[tuple[object, ...]]:
            return [(e.pair, e.state, e.score, e.gates_failed, e.evidence) for e in edges]  # type: ignore[attr-defined]

        assert shape(links.edges()) == shape(run_b01.matcher.links.edges())
        assert report["per_ac"] == run_b01.report["per_ac"]
        assert report["forbidden_hits"] == [] and report["checks"]["S4"]["failed"] == 0
    finally:
        clean()
        driver.close()
