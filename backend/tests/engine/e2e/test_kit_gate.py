"""The P2.4 gate on the small kit, graded by the data-kit reference scorer (data-kit 8.3).

With only Tier 1 implemented, expected links that need fuzzy (Tier 2) or contextual (Tier 3)
evidence cannot pass yet. The gate is therefore:
  (a) every expected link reachable with Tier 1 passes the scorer's S1 checks;
  (b) the zero-tolerance checks hold over the whole kit, noise included: no forbidden-trap hit,
      no AUTO edge outside a cross_case group, every S4 integrity clause;
  (d) every expected link not reachable yet is pinned per batch in `waiting.py` with the tier
      it waits for and its exact failure kinds (equality, as are the skipped links), and what is
      stored for it is never above its expected state or score and cites nothing outside its
      two end cases.
The scorer's `ok` cannot say "expected link not reached yet, nothing wrong stored", so this
test reads its report (see the PR for the request to the kit owner).
"""

from decimal import Decimal
from typing import Any

import pytest

from tests.engine.e2e.conftest import KitRun
from tests.engine.e2e.kit import failures_by_link
from tests.engine.e2e.waiting import FAILING, MISSED, SKIPPED
from tracex_engine.matching import LinkState

# (a) Expected links Tier 1 reaches: identifier pairs with ID_EXACT only (G5 and G6 included).
TIER1_REACHABLE = {
    "b01": [
        *[f"EL-FX01-{n}-0-1" for n in ("1203", "8816")],
        "EL-ACC-4471-0-1",
        "EL-ACC-4471-0-2",
        "EL-ACC-4471-1-2",
        "EL-ACC-L3-0-1",
        "EL-FX02-0-1",
        *[f"EL-FX-07-R{n}-0-1" for n in (1, 2, 3)],
        "EL-FX07-PHN-0-1",
        *[f"EL-FX-08-R{n}-0-1" for n in (1, 2, 3, 4)],
        "EL-FX08-PHN-0-1",
        *[f"EL-FX-09-R{n}-0-1" for n in (1, 2, 3)],
        *[f"EL-FX09-ACC-{p}" for p in ("0-1", "0-2", "1-2")],
        "EL-FX10-PHN-0-1",
        *[f"EL-FX-11-R{n}-0-1" for n in (1, 2, 3, 4)],
        *[f"EL-FX-12-A-R{n}-0-1" for n in (1, 2, 3)],
        *[f"EL-FX-12-B-R{n}-0-1" for n in (1, 2)],
        "EL-FX12-PA-0-1",
        "EL-FX12-PB-0-1",
        *[f"EL-FX-13-{s}-R{n}-0-1" for s in ("A", "B") for n in (1, 2, 3)],
        *[f"EL-FX-13-C-R{n}-0-1" for n in (1, 2)],
        *[f"EL-FX13-{p}-0-1" for p in ("P12", "P34", "P23")],
        *[f"EL-FX-14-A-R{n}-0-1" for n in (1, 2)],
        *[f"EL-FX-14-B-R{n}-0-1" for n in (1, 2, 3)],
        "EL-FX14-P1-0-1",
        "EL-FX14-P2-0-1",
        "EL-FX17-PHN-0-1",
        "EL-FX19-VEH",
        "EL-FX21-ACC-0-1",
        *[f"EL-FX-22-R{n}-0-1" for n in (1, 2, 3)],
        "EL-FX22-PHN-0-1",
        "EL-FX26-A1A2",
        "EL-FX26-A2A3",
        *[f"EL-SF04-HUB-{p}" for p in ("0-1", "0-2", "1-2")],
        "EL-SF04-X-0-1",
        "EL-SF05-PHN-0-1",
        *[f"EL-SF-06-R{n}-0-1" for n in (1, 2, 3, 4)],
        "EL-SF06-PHN-0-1",
        "EL-SF08-PHN-0-1",
    ],
    "b02": [
        "EL-FX05-PHN-0-1",
        "EL-SF07-PHN-0-1",
        "EL-ACC-4471-0-3",
        "EL-ACC-4471-1-3",
        "EL-ACC-4471-2-3",
    ],
}

PASS_NOW = {
    "b01": {
        "AC-02", "AC-03", "AC-04", "AC-05", "AC-06", "AC-07", "AC-09", "AC-10", "AC-17", "AC-19",
        "AC-21", "AC-26",
    },
    "b02": {
        "AC-02", "AC-03", "AC-04", "AC-06", "AC-07", "AC-09", "AC-10", "AC-15", "AC-17", "AC-19",
        "AC-21", "AC-26",
    },
}  # fmt: skip
# AC-05 fails in b02 only: the harness REJECTs the pair before b02 (AC-15) and the kit has no b02
# expectation for it yet, so the scorer still wants SUGGESTED (see waiting.py).
WAITS = {
    "b01": {"AC-01": 3, "AC-08": 3, "AC-11": 3, "AC-12": 3, "AC-13": 3, "AC-14": 3, "AC-22": 3},
    "b02": {
        "AC-01": 3, "AC-05": 0, "AC-08": 3, "AC-11": 3, "AC-12": 3, "AC-13": 3, "AC-14": 3,
        "AC-22": 3,
    },
}  # fmt: skip


ACCIDENTAL_PHONE_SWAPS = 9


def reachable(batch: str) -> set[str]:
    return set(TIER1_REACHABLE["b01"]) | (set(TIER1_REACHABLE["b02"]) if batch == "b02" else set())


@pytest.fixture(params=["b01", "b02"])
def kit_run(request: pytest.FixtureRequest) -> tuple[str, KitRun]:
    batch: str = request.param
    return batch, request.getfixturevalue(f"run_{batch}")


def failures(report: dict[str, Any]) -> dict[str, set[str]]:
    return failures_by_link(report)


def test_every_tier1_reachable_link_passes_s1(kit_run: tuple[str, KitRun]) -> None:
    batch, run = kit_run
    report = run.report
    skipped = {s["id"] for s in report["skipped"]}

    failed = {k: v for k, v in failures(report).items() if k in reachable(batch)}

    assert failed == {}
    assert reachable(batch).isdisjoint(skipped)


def test_zero_tolerance_checks_hold_over_the_whole_kit(kit_run: tuple[str, KitRun]) -> None:
    _, run = kit_run
    report = run.report

    assert report["forbidden_hits"] == []
    assert [w for w in report["wrong_links"] if w["id"] is None] == []
    assert report["checks"]["S3"]["failed"] == 0 and report["checks"]["S4"]["failed"] == 0
    assert report["checks"]["S4"]["passed"] > 1000


def test_failing_links_are_exactly_the_pinned_waiting_list(kit_run: tuple[str, KitRun]) -> None:
    """Equality: a waiting link that starts passing, or fails another way, or a new failure,
    stops CI by name (update `waiting.py` with the tier that changed it)."""
    batch, run = kit_run

    found = {k: frozenset(v) for k, v in failures(run.report).items()}

    assert found == {k: kinds for k, (_, kinds) in FAILING[batch].items()}


def test_skipped_links_are_exactly_the_pinned_list(kit_run: tuple[str, KitRun]) -> None:
    batch, run = kit_run

    assert {s["id"]: s["reason"] for s in run.report["skipped"]} == SKIPPED[batch]


def test_a_waiting_link_is_never_above_its_expected_state_or_score(
    kit_run: tuple[str, KitRun],
) -> None:
    """For every waiting link with a stored edge: state rank and score not above the expected
    ones, and no source outside the two end cases."""
    batch, run = kit_run
    report = run.report
    waiting = set(FAILING[batch])
    expected = {e["id"]: e for e in run.truth["expected_links"]}
    actual_state: dict[str, str] = {}
    actual_score: dict[str, Decimal] = {}
    for item in report["wrong_links"]:
        if item["id"] not in waiting:
            continue
        if item["kind"] == "state":
            actual_state[item["id"]] = item["actual"]
        if item["kind"] == "score":
            actual_score[item["id"]] = Decimal(str(item["actual"]))
        if item["kind"] == "provenance":
            assert item["actual"]["outside_end_cases"] == [], item
    for link_id, row in report["reported"]["band_mode_scores"].items():
        if link_id in waiting:
            actual_score[link_id] = Decimal(str(row["actual"]))
    rank = {"REJECTED": 0, "SUGGESTED": 1, "AUTO": 2}
    stored = [k for k in waiting if FAILING[batch][k][1] != MISSED]
    assert stored
    for link_id in stored:
        link = expected[link_id]
        state = actual_state.get(link_id, link["state"])
        assert rank[state] <= rank[link["state"]], link_id
        score = actual_score.get(link_id, Decimal(str(link["score"]["value"])))
        assert score <= Decimal(str(link["score"]["value"])), link_id


def test_acceptance_cases_pass_or_wait_for_their_tier(kit_run: tuple[str, KitRun]) -> None:
    batch, run = kit_run
    per_ac = run.report["per_ac"]

    assert {ac for ac, row in per_ac.items() if row["status"] == "pass"} == PASS_NOW[batch]
    assert {ac for ac, row in per_ac.items() if row["status"] == "fail"} == set(WAITS[batch])


def test_no_suggested_edge_on_a_non_link_pair(kit_run: tuple[str, KitRun]) -> None:
    """S6 is reported, not gating. Tier 1 stored nothing on a true non-link. With Tier 2 exactly
    nine random noise phones of the small kit happen to differ from another case's phone by one
    adjacent swap (PHONE_TRANSPOSED 55, SUGGESTED, as the spec fixes); no person or org pair is
    suggested on a non-link. Pinned by equality so any other stray fails by count."""
    _, run = kit_run

    assert run.report["reported"]["suggested_on_non_link_pairs"] == ACCIDENTAL_PHONE_SWAPS


def test_the_ac15_rejected_pair_stays_rejected_through_b02(run_b02: KitRun) -> None:
    """AC-15 on the engine side: b02 adds a shared owned phone that would pass every gate, and
    the rejected pair keeps its state with no transition record from the b02 run."""
    [rejected] = [e for e in run_b02.matcher.links.edges() if e.state is LinkState.REJECTED]
    assert rejected.history[-1].decision_id == "kit-ac15-reject"
    assert all(t.link_id != rejected.link_id for t in run_b02.results[-1].transitions)
