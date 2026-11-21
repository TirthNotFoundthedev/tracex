"""The worked scenario on kit files (AC-01, AC-27) and AC-20 / AC-23 over the whole kit.

AC-01 and AC-27 run on a fresh store holding only C-101 and C-201 (data-kit 3.3). The real
extractor and graph builder read the kit files. With Tier 1 and the real Tier 2 comparators the
phones link AUTO and the person pair carries SHARED_PHONE (45.0) and PER_NAME_SIM (22.5) and
waits for Tier 3; with the Tier 2 and Tier 3 values of AC-01 supplied as fixture comparators it
is AUTO 85.5 as the spec fixes.
"""

import json
from decimal import Decimal
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from tests.engine.e2e.conftest import KitRun
from tests.engine.e2e.kit import load
from tests.engine.matching.fixtures import AC01_FIXTURE, FixtureProvider
from tracex_engine.graph import InMemoryCaseGraphStore
from tracex_engine.matching import InMemoryLinkStore, LinkState, Matcher, build_explanation

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[4] / "contracts" / "explanation.schema.json").read_text(
        "utf-8"
    )
)


def scoped(kit: Path, matcher_providers: tuple[FixtureProvider, ...] | None) -> Matcher:
    graphs = InMemoryCaseGraphStore()
    load(graphs, kit, "b01", only=("C-101", "C-201"))
    return Matcher(graphs, InMemoryLinkStore(), providers=matcher_providers)


def test_worked_scenario_tier1_and_tier2_on_kit_files(kit: Path) -> None:
    m = scoped(kit, None)

    result = m.run_matching(input_case_ids=("C-101", "C-201"), triggered_by="u-hari")

    edges = m.links.edges()
    phones = sorted(
        e.evidence["support"][0]["items"][0]["params"]["value"]
        for e in edges
        if e.entity_type.value == "PHONE"
    )
    assert phones == ["9000014471", "9000021203", "9000028816"]
    assert all(e.state is LinkState.AUTO for e in edges if e.entity_type.value == "PHONE")
    [irfan] = [e for e in edges if e.entity_type.value == "PERSON"]
    assert (irfan.state, irfan.score, [g.gate for g in irfan.gates_failed]) == (
        LinkState.SUGGESTED,
        Decimal("67.5"),
        ["G1"],
    )
    [item] = irfan.evidence["support"][0]["items"]
    assert item["kind"] == "SHARED_PHONE" and item["is_anchor"]
    [name] = irfan.evidence["support"][1]["items"]
    assert (name["kind"], name["contribution"]) == ("PER_NAME_SIM", 22.5)
    assert name["params"] == {"name_a": "mohammad irfan", "name_b": "irfan", "sim": 1.0}
    assert {(s["case_id"], s["document_id"], s["line"]) for s in name["sources"]} == {
        ("C-101", "fir.txt", 12),
        ("C-201", "notes.txt", 3),
    }
    assert {(s["case_id"], s["document_id"], s["line"]) for s in item["sources"]} == {
        ("C-101", "fir.txt", 12),
        ("C-201", "notes.txt", 3),
    }
    assert len(edges) == 4
    assert result.run.counts_by_state == {"AUTO": 3, "SUGGESTED": 1}


def test_worked_scenario_with_ac01_comparator_values_is_auto_85_5(kit: Path) -> None:
    """AC-01 and AC-27 end to end, Tier 2 and 3 values as fixtures."""
    m = scoped(kit, (FixtureProvider(AC01_FIXTURE),))

    result = m.run_matching(input_case_ids=("C-101", "C-201"), triggered_by="u-hari")

    [irfan] = [e for e in m.links.edges() if e.entity_type.value == "PERSON"]
    assert (irfan.state, irfan.score, irfan.gates_failed) == (LinkState.AUTO, Decimal("85.5"), ())
    run = result.run
    assert (run.counts_by_state["AUTO"], run.thresholds_version, run.status.value) == (
        4,
        1,
        "SUCCEEDED",
    )
    assert run.input_case_ids == ("C-101", "C-201")
    assert len(result.transitions) == 4


def test_every_kit_payload_validates_and_keeps_the_invariant(run_b02: KitRun) -> None:
    """AC-20 over every edge the engine stores on the small tier."""
    validator = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
    edges = run_b02.matcher.links.edges()
    assert len(edges) > 100
    for edge in edges:
        payload = build_explanation(edge)
        assert list(validator.iter_errors(payload)) == [], edge.link_id
        total = sum((Decimal(str(t["subtotal"])) for t in payload["support"]), Decimal(0))
        total += sum((Decimal(str(i["contribution"])) for i in payload["against"]), Decimal(0))
        total += Decimal(str(payload["clamp_adjustment"]["value"]))
        assert total == Decimal(str(payload["score"]))
        ends = {edge.case_a, edge.case_b}
        for tier in payload["support"]:
            for item in tier["items"]:
                assert item["sources"] and {s["case_id"] for s in item["sources"]} <= ends


def test_a_rerun_on_the_kit_store_changes_nothing(run_b02: KitRun) -> None:
    """AC-23: no new edges, every link id kept, no transition record."""
    before = run_b02.matcher.links.edges()

    result = run_b02.matcher.run_matching(input_case_ids=(), triggered_by="u-hari")

    assert result.transitions == ()
    assert run_b02.matcher.links.edges() == before


def test_two_fresh_kit_runs_agree(run_b01: KitRun, kit: Path) -> None:
    """AC-23: same pairs, states, scores and evidence on an empty store (ids and times aside)."""
    graphs = InMemoryCaseGraphStore()
    load(graphs, kit, "b01")
    again = Matcher(graphs, InMemoryLinkStore())
    again.run_matching(input_case_ids=(), triggered_by="u-hari")

    def shape(m: Matcher) -> list[tuple[object, ...]]:
        return [(e.pair, e.state, e.score, e.gates_failed, e.evidence) for e in m.links.edges()]

    assert shape(again) == shape(run_b01.matcher)
