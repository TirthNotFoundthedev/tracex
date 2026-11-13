"""Rerun rules (D37), human decisions and the run record (spec section 6).

The Tier 2 and Tier 3 items of the worked scenario come from fixture comparators, so the
person link reaches AUTO 85.5 as AC-01 fixes; everything else is the production matcher.
"""

from decimal import Decimal

import pytest

from tests.engine.matching.fixtures import AC01_FIXTURE, IRFAN_A, IRFAN_B, ac01_graphs, matcher
from tests.engine.matching.support import build, owns, person, phone, store_of
from tracex_engine.matching import DecisionError, LinkState, Matcher, SameAsEdge, TransitionRecord

ADMIN = "u-admin"


def person_edge(m: Matcher) -> SameAsEdge:
    [edge] = [e for e in m.links.edges() if e.entity_type.value == "PERSON"]
    return edge


def ac01(**kw: object) -> Matcher:
    m = matcher(*ac01_graphs(), fixture=AC01_FIXTURE)
    m.run_matching(input_case_ids=(), triggered_by=ADMIN, **kw)  # type: ignore[arg-type]
    return m


def test_worked_scenario_with_fixture_comparators_is_auto_85_5() -> None:
    m = ac01()

    edge = person_edge(m)
    assert (edge.state, edge.score, edge.gates_failed) == (LinkState.AUTO, Decimal("85.5"), ())


def test_run_record_has_every_field() -> None:
    """AC-27 (with fixture comparators): AUTO 4, thresholds_version 1, SUCCEEDED."""
    m = matcher(*ac01_graphs(), fixture=AC01_FIXTURE)

    result = m.run_matching(input_case_ids=("C-101", "C-201"), triggered_by=ADMIN)

    run = result.run
    assert run.input_case_ids == ("C-101", "C-201")
    assert (run.thresholds_version, run.status.value, run.ruleset_version) == (
        1,
        "SUCCEEDED",
        "engine-matching/1.1",
    )
    assert run.counts_by_state["AUTO"] == 4
    assert run.counts_by_band["HIGH"] == 4
    assert run.triggered_by == ADMIN and run.started_at and run.finished_at
    assert run.oversized_block == 0 and run.error_code is None
    assert len(result.transitions) == 4
    assert all(
        t.reason_code is None and t.match_run_id == run.match_run_id for t in result.transitions
    )


def test_rerun_on_the_same_store_changes_nothing() -> None:
    """AC-23: no new edges, same link ids, no transition records."""
    m = ac01()
    before = m.links.edges()

    result = m.run_matching(input_case_ids=(), triggered_by=ADMIN)

    assert result.transitions == ()
    assert m.links.edges() == before


def test_two_runs_on_empty_stores_agree_apart_from_ids_and_times() -> None:
    def shape(m: Matcher) -> list[tuple[object, ...]]:
        return [
            (e.pair, e.state, e.score, e.band, e.gates_failed, e.evidence) for e in m.links.edges()
        ]

    assert shape(ac01()) == shape(ac01())


def test_raised_high_min_demotes_the_person_link_and_keeps_the_phones() -> None:
    """AC-18."""
    m = ac01()

    result = m.run_matching(
        input_case_ids=(),
        triggered_by=ADMIN,
        thresholds_version=2,
        thresholds={"high_min": 90, "medium_min": 45},
    )

    edge = person_edge(m)
    assert (edge.state, edge.thresholds_version) == (LinkState.SUGGESTED, 2)
    [record] = result.transitions
    assert (record.link_id, record.from_state, record.to_state, record.reason_code) == (
        edge.link_id,
        LinkState.AUTO,
        LinkState.SUGGESTED,
        "DEMOTED",
    )
    assert all(e.state is LinkState.AUTO for e in m.links.edges() if e.entity_type.value == "PHONE")


def test_a_confirmed_link_is_untouched_by_a_rerun() -> None:
    """AC-18 variant."""
    m = ac01()
    edge = person_edge(m)
    m.apply_decision(edge.link_id, LinkState.AUTO, LinkState.CONFIRMED, "u-inv", "d-1", None, None)
    confirmed = person_edge(m)

    result = m.run_matching(
        input_case_ids=(),
        triggered_by=ADMIN,
        thresholds_version=2,
        thresholds={"high_min": 90, "medium_min": 45},
    )

    assert person_edge(m) == confirmed
    assert all(r.link_id != edge.link_id for r in result.transitions)


def test_invalid_thresholds_are_refused() -> None:
    """AC-18: high_min 65 fails validation and nothing runs."""
    m = ac01()

    with pytest.raises(ValueError):
        m.run_matching(
            input_case_ids=(),
            triggered_by=ADMIN,
            thresholds_version=2,
            thresholds={"high_min": 65, "medium_min": 45},
        )


def test_undo_keeps_everything_and_splits_the_cluster() -> None:
    """AC-16."""
    m = ac01()
    edge = person_edge(m)
    phones = [e for e in m.links.edges() if e.entity_type.value == "PHONE"]

    record = m.apply_decision(
        edge.link_id, LinkState.AUTO, LinkState.UNDONE, "u-sup", "d-1", "WRONG_PERSON", "not him"
    )

    assert isinstance(record, TransitionRecord)
    assert (
        record.from_state,
        record.to_state,
        record.actor,
        record.decision_id,
        record.match_run_id,
    ) == (
        LinkState.AUTO,
        LinkState.UNDONE,
        "u-sup",
        "d-1",
        None,
    )
    undone = person_edge(m)
    assert undone.state is LinkState.UNDONE and len(undone.history) == 2
    assert undone.history[-1].reason_text == "not him"
    assert [e for e in m.links.edges() if e.entity_type.value == "PHONE"] == phones
    assert m.cluster_of(edge.entity_a_id) == {edge.entity_a_id}
    payload = m.explanation(edge.link_id)
    assert payload is not None and payload["state"] == "UNDONE"


@pytest.mark.parametrize(
    ("first", "then"),
    [
        (LinkState.REJECTED, LinkState.CONFIRMED),
        (LinkState.CONFIRMED, LinkState.REJECTED),
    ],
)
def test_illegal_transitions_change_nothing(first: LinkState, then: LinkState) -> None:
    """AC-24 on a SUGGESTED link."""
    m = matcher(*ac01_graphs())
    m.run_matching(input_case_ids=(), triggered_by=ADMIN)
    edge = person_edge(m)
    m.apply_decision(edge.link_id, LinkState.SUGGESTED, first, "u-inv", "d-1", "X", "x")
    before = person_edge(m)

    answer = m.apply_decision(edge.link_id, first, then, "u-inv", "d-2", "X", "x")

    assert answer is DecisionError.ILLEGAL_TRANSITION
    assert person_edge(m) == before


def test_an_auto_link_cannot_be_rejected_and_a_stale_state_is_refused() -> None:
    """AC-24: AUTO -> REJECTED is illegal; a stale expected_from is a mismatch; no edge is
    NOT_FOUND."""
    m = ac01()
    edge = person_edge(m)

    assert (
        m.apply_decision(edge.link_id, LinkState.AUTO, LinkState.REJECTED, "u", "d-1", "X", "x")
        is DecisionError.ILLEGAL_TRANSITION
    )
    assert (
        m.apply_decision(
            edge.link_id, LinkState.SUGGESTED, LinkState.CONFIRMED, "u", "d-2", None, None
        )
        is DecisionError.STATE_MISMATCH
    )
    assert (
        m.apply_decision(
            "no-such-link", LinkState.AUTO, LinkState.CONFIRMED, "u", "d-3", None, None
        )
        is DecisionError.NOT_FOUND
    )
    assert person_edge(m) == edge


def test_a_replayed_decision_returns_the_same_record_and_changes_nothing() -> None:
    m = ac01()
    edge = person_edge(m)
    first = m.apply_decision(
        edge.link_id, LinkState.AUTO, LinkState.CONFIRMED, "u", "d-1", None, None
    )
    after = person_edge(m)

    again = m.apply_decision(
        edge.link_id, LinkState.AUTO, LinkState.CONFIRMED, "u", "d-1", None, None
    )

    assert again == first and person_edge(m) == after


def test_a_rejected_pair_is_never_proposed_again() -> None:
    """AC-15: the next run adds an owned phone; the pair stays REJECTED with no record."""
    fixture = {
        frozenset({("C-107", "jaswinder bhullar"), ("C-108", "jasvinder bhullar")}): [
            ("PER_NAME_SIM", "0.94"),
            ("PER_AGE_CLOSE", "1.0"),
            ("PER_LOCALITY", "1.0"),
        ]
    }
    a, b = (
        build("C-107", [person("Jaswinder Bhullar")]),
        build("C-108", [person("Jasvinder Bhullar")]),
    )
    m = matcher(a, b, fixture=fixture)
    m.run_matching(input_case_ids=(), triggered_by=ADMIN)
    edge = person_edge(m)
    assert (edge.state, edge.score) == (LinkState.SUGGESTED, Decimal("48.2"))
    m.apply_decision(
        edge.link_id, LinkState.SUGGESTED, LinkState.REJECTED, "u-inv", "d-1", "NOT_SAME", "no"
    )
    rejected = person_edge(m)
    m.graphs.write_case(
        build(
            "C-107",
            [person("Jaswinder Bhullar")],
            attributions=[owns(person("Jaswinder Bhullar"), phone("9000079900"))],
        )
    )
    m.graphs.write_case(
        build(
            "C-108",
            [person("Jasvinder Bhullar")],
            attributions=[owns(person("Jasvinder Bhullar"), phone("9000079900"))],
        )
    )

    result = m.run_matching(input_case_ids=("C-107", "C-108"), triggered_by=ADMIN)

    assert person_edge(m) == rejected
    assert all(r.link_id != edge.link_id for r in result.transitions)
    # AC-25: reopen, confirm, rerun: never AUTO, two transition records from the decisions.
    reopen = m.apply_decision(
        edge.link_id, LinkState.REJECTED, LinkState.SUGGESTED, "u-sup", "d-2", "NEW_FACTS", "re"
    )
    confirm = m.apply_decision(
        edge.link_id, LinkState.SUGGESTED, LinkState.CONFIRMED, "u-inv", "d-3", None, None
    )
    assert isinstance(reopen, TransitionRecord) and isinstance(confirm, TransitionRecord)
    m.run_matching(input_case_ids=(), triggered_by=ADMIN)
    assert person_edge(m).state is LinkState.CONFIRMED


def test_a_reopened_link_is_never_promoted_by_a_rerun() -> None:
    fixture = {frozenset({IRFAN_A, IRFAN_B}): AC01_FIXTURE[frozenset({IRFAN_A, IRFAN_B})]}
    m = matcher(*ac01_graphs(), fixture=fixture)
    m.run_matching(input_case_ids=(), triggered_by=ADMIN)
    edge = person_edge(m)
    m.apply_decision(edge.link_id, LinkState.AUTO, LinkState.UNDONE, "u-sup", "d-1", "X", "x")
    m.apply_decision(edge.link_id, LinkState.UNDONE, LinkState.SUGGESTED, "u-sup", "d-2", "X", "x")

    result = m.run_matching(input_case_ids=(), triggered_by=ADMIN)

    assert person_edge(m).state is LinkState.SUGGESTED
    assert result.transitions == ()


def test_new_evidence_promotes_a_suggested_link() -> None:
    """SF-07: Medium without anchor, then a later batch adds the owned phone: PROMOTED."""
    names = {
        frozenset({("C-134", "dinesh pathania"), ("C-135", "dinesh pathania")}): [
            ("PER_NAME_SIM", "1.0"),
            ("PER_RELATIVE_NAME", "1.0"),
            ("PER_LOCALITY", "1.0"),
        ]
    }
    store = store_of(
        build("C-134", [person("Dinesh Pathania")]), build("C-135", [person("Dinesh Pathania")])
    )
    m = matcher(fixture=names, store=store)
    m.run_matching(input_case_ids=(), triggered_by=ADMIN)
    edge = person_edge(m)
    assert (edge.state, edge.score) == (LinkState.SUGGESTED, Decimal("55.0"))
    for case in ("C-134", "C-135"):
        p = person("Dinesh Pathania")
        store.write_case(
            build(case, [p], attributions=[owns(p, phone("9000089015", 3, "notes-02.txt"))])
        )

    result = m.run_matching(input_case_ids=("C-134", "C-135"), triggered_by=ADMIN)

    promoted = person_edge(m)
    assert (promoted.link_id, promoted.state, promoted.score) == (
        edge.link_id,
        LinkState.AUTO,
        Decimal("100.0"),
    )
    assert [
        (r.reason_code, r.to_state) for r in result.transitions if r.link_id == edge.link_id
    ] == [("PROMOTED", LinkState.AUTO)]


def test_raised_medium_min_withdraws_and_a_later_proposal_is_a_new_link() -> None:
    """SF-09: a SUGGESTED edge below medium_min is removed (WITHDRAWN), not block-listed."""
    m = matcher(*ac01_graphs())
    m.run_matching(input_case_ids=(), triggered_by=ADMIN)
    edge = person_edge(m)

    result = m.run_matching(
        input_case_ids=(),
        triggered_by=ADMIN,
        thresholds_version=2,
        thresholds={"high_min": 80, "medium_min": 60},
    )

    assert [e for e in m.links.edges() if e.entity_type.value == "PERSON"] == []
    [record] = result.transitions
    assert (record.from_state, record.to_state, record.reason_code) == (
        LinkState.SUGGESTED,
        None,
        "WITHDRAWN",
    )
    m.run_matching(
        input_case_ids=(),
        triggered_by=ADMIN,
        thresholds_version=3,
        thresholds={"high_min": 80, "medium_min": 45},
    )
    assert person_edge(m).link_id != edge.link_id


def test_undoing_the_phone_link_removes_the_person_evidence_built_on_it() -> None:
    """Section 4 rule 2: without SHARED_PHONE the AUTO person link scores 40.5 (Low): it is
    demoted and then withdrawn, two transition records."""
    m = ac01()
    person_link = person_edge(m)
    [phone_link] = [
        e
        for e in m.links.edges()
        if e.entity_type.value == "PHONE"
        and e.evidence["support"][0]["items"][0]["params"]["value"] == "9000014471"
    ]
    m.apply_decision(phone_link.link_id, LinkState.AUTO, LinkState.UNDONE, "u-sup", "d-1", "X", "x")

    result = m.run_matching(input_case_ids=(), triggered_by=ADMIN)

    assert [e for e in m.links.edges() if e.entity_type.value == "PERSON"] == []
    assert [(r.link_id, r.from_state, r.to_state, r.reason_code) for r in result.transitions] == [
        (person_link.link_id, LinkState.AUTO, LinkState.SUGGESTED, "DEMOTED"),
        (person_link.link_id, LinkState.SUGGESTED, None, "WITHDRAWN"),
    ]
