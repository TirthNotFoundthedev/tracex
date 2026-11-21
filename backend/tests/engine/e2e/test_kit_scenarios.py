"""The behavioural acceptance cases on the small kit with the real Tier 1-3 providers.

The kit lists them as scenarios (data-kit 6), each from a fresh load of b01 (plus b02 where the
steps say so). Covered here: AC-16 undo, AC-18 raised high_min, AC-23 reruns, AC-24 illegal
decisions, AC-25 reopen then confirm. AC-15 is in test_kit_gate.py, AC-20 and AC-27 in
test_worked_scenario.py.
"""

from pathlib import Path

import pytest

from tests.engine.e2e.kit import load, run_batches
from tracex_engine.graph import InMemoryCaseGraphStore
from tracex_engine.matching import (
    DecisionError,
    InMemoryLinkStore,
    LinkState,
    Matcher,
    ReasonCode,
    SameAsEdge,
)

A, S, C, R, U = (
    LinkState.AUTO,
    LinkState.SUGGESTED,
    LinkState.CONFIRMED,
    LinkState.REJECTED,
    LinkState.UNDONE,
)


def fresh_b01(kit: Path) -> Matcher:
    graphs, links = InMemoryCaseGraphStore(), InMemoryLinkStore()
    matcher, _ = run_batches(graphs, links, kit, "b01")
    return matcher


def edge(m: Matcher, type_: str, *cases: str) -> SameAsEdge:
    [found] = [
        e
        for e in m.links.edges()
        if e.entity_type.value == type_ and {e.case_a, e.case_b} == set(cases)
    ]
    return found


def decide(m: Matcher, e: SameAsEdge, to: LinkState, n: int) -> object:
    reason = None if to in (C,) else "kit scenario"
    return m.apply_decision(e.link_id, e.state, to, "kit-officer", f"kit-{n}", None, reason)


def snapshot(m: Matcher) -> dict[tuple[str, str], tuple[LinkState, str]]:
    return {e.pair: (e.state, str(e.score)) for e in m.links.edges()}


def test_ac16_undo_keeps_everything_and_splits_the_person_cluster(kit: Path) -> None:
    m = fresh_b01(kit)
    person = edge(m, "PERSON", "C-101", "C-201")
    phones_before = {e.pair: e.state for e in m.links.edges() if e.entity_type.value == "PHONE"}
    assert person.state is A

    decide(m, person, U, 1)

    undone = m.links.get(person.link_id)
    assert undone is not None and undone.state is U and len(undone.history) == 2
    assert {e.pair: e.state for e in m.links.edges() if e.entity_type.value == "PHONE"} == (
        phones_before
    )
    assert person.entity_b_id not in m.cluster_of(person.entity_a_id)
    rerun = m.run_matching(triggered_by="kit-harness")
    assert all(t.link_id != person.link_id for t in rerun.transitions)


def test_ac18_raised_high_min_demotes_the_person_link_and_keeps_the_phones(kit: Path) -> None:
    m = fresh_b01(kit)
    person = edge(m, "PERSON", "C-101", "C-201")

    rerun = m.run_matching(
        triggered_by="kit-harness",
        thresholds_version=2,
        thresholds={"high_min": 90, "medium_min": 45},
    )

    demoted = m.links.get(person.link_id)
    assert demoted is not None and (demoted.state, demoted.thresholds_version) == (S, 2)
    [record] = [t for t in rerun.transitions if t.link_id == person.link_id]
    assert (record.from_state, record.to_state, record.reason_code) == (A, S, ReasonCode.DEMOTED)
    phones = [
        e
        for e in m.links.edges()
        if e.entity_type.value == "PHONE" and {e.case_a, e.case_b} == {"C-101", "C-201"}
    ]
    assert phones and all(e.state is A for e in phones)


def test_ac23_reruns_repeat_the_first_run(kit: Path) -> None:
    first, second = fresh_b01(kit), fresh_b01(kit)

    assert snapshot(first) == snapshot(second)
    rerun = first.run_matching(triggered_by="kit-harness")
    assert rerun.transitions == () and snapshot(first) == snapshot(second)


@pytest.mark.parametrize(("first", "then"), [(R, C), (C, R)])
def test_ac24_a_second_contrary_decision_is_refused(
    kit: Path, first: LinkState, then: LinkState
) -> None:
    m = fresh_b01(kit)
    pair = edge(m, "PERSON", "C-107", "C-108")
    assert pair.state is S
    decide(m, pair, first, 1)
    before = m.links.get(pair.link_id)
    assert before is not None

    refused = m.apply_decision(
        pair.link_id, first, then, "kit-officer", "kit-2", None, "kit scenario"
    )

    assert refused is DecisionError.ILLEGAL_TRANSITION
    assert m.links.get(pair.link_id) == before


def test_ac24_an_auto_link_cannot_be_rejected(kit: Path) -> None:
    m = fresh_b01(kit)
    person = edge(m, "PERSON", "C-101", "C-201")

    assert decide(m, person, R, 1) is DecisionError.ILLEGAL_TRANSITION
    assert m.links.get(person.link_id) == person


def test_ac25_reopen_then_confirm_and_the_rerun_never_makes_it_auto(kit: Path) -> None:
    graphs, links = InMemoryCaseGraphStore(), InMemoryLinkStore()
    m, _ = run_batches(graphs, links, kit, "b02")  # the AC-15 REJECT is applied before b02
    pair = edge(m, "PERSON", "C-107", "C-108")
    assert pair.state is R

    decide(m, pair, S, 2)
    confirmed = m.apply_decision(pair.link_id, S, C, "kit-officer", "kit-3", None, None)
    assert not isinstance(confirmed, DecisionError)
    load(graphs, kit, "b02")
    rerun = m.run_matching(triggered_by="kit-harness")

    final = m.links.get(pair.link_id)
    assert final is not None and final.state is C
    assert [h.to_state for h in final.history][-3:] == [R, S, C]
    assert all(t.link_id != pair.link_id for t in rerun.transitions)
