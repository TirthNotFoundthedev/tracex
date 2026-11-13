"""What a run returns to the API (review of PR #28, blockers 2 and 3, minors 4 and 7).

- every edge a run rewrites without a state change is named in `RunResult.updated_link_ids`;
- a transition record is returned only for a write that happened;
- `RunRecord.created_by_state` counts edges created, by state;
- invalid or incomplete thresholds raise `ThresholdsError` before anything runs.
"""

from decimal import Decimal

import pytest

from tests.engine.matching.fixtures import AC01_FIXTURE, ac01_graphs, matcher
from tracex_engine.matching import (
    DEFAULT_THRESHOLDS,
    InMemoryLinkStore,
    LinkState,
    Matcher,
    RunStatus,
    SameAsEdge,
    Thresholds,
    ThresholdsError,
)

ADMIN = "u-admin"


def ac01() -> Matcher:
    m = matcher(*ac01_graphs(), fixture=AC01_FIXTURE)
    m.run_matching(input_case_ids=(), triggered_by=ADMIN)
    return m


def test_a_new_thresholds_version_names_every_rewritten_edge() -> None:
    m = ac01()
    ids = {e.link_id for e in m.links.edges()}

    result = m.run_matching(
        input_case_ids=(),
        triggered_by=ADMIN,
        thresholds_version=2,
        thresholds={"high_min": 80, "medium_min": 45},
    )

    assert result.transitions == ()
    assert set(result.updated_link_ids) == ids
    assert all(e.thresholds_version == 2 for e in m.links.edges())


def test_an_unchanged_rerun_names_no_edge() -> None:
    m = ac01()

    result = m.run_matching(input_case_ids=(), triggered_by=ADMIN)

    assert result.updated_link_ids == () and result.transitions == ()


def test_new_evidence_inside_the_band_names_the_edge_without_a_transition() -> None:
    """The SUGGESTED Irfan pair gains a second shared phone: score moves, state does not."""
    m = matcher(*ac01_graphs())
    m.run_matching(input_case_ids=(), triggered_by=ADMIN)
    [edge] = [e for e in m.links.edges() if e.entity_type.value == "PERSON"]
    for graph in ac01_graphs(extra_phone="9000033333"):
        m.graphs.write_case(graph)

    result = m.run_matching(input_case_ids=("C-101", "C-201"), triggered_by=ADMIN)

    [after] = [e for e in m.links.edges() if e.entity_type.value == "PERSON"]
    assert (after.link_id, after.state, after.score) == (
        edge.link_id,
        LinkState.SUGGESTED,
        Decimal("60.0"),
    )
    assert edge.link_id in result.updated_link_ids
    assert all(r.link_id != edge.link_id for r in result.transitions)


def test_a_reopened_edge_refreshed_in_place_is_named() -> None:
    m = ac01()
    [edge] = [e for e in m.links.edges() if e.entity_type.value == "PERSON"]
    m.apply_decision(edge.link_id, LinkState.AUTO, LinkState.UNDONE, "u-sup", "d-1", "X", "x")
    m.apply_decision(edge.link_id, LinkState.UNDONE, LinkState.SUGGESTED, "u-sup", "d-2", "X", "x")

    result = m.run_matching(
        input_case_ids=(),
        triggered_by=ADMIN,
        thresholds_version=2,
        thresholds={"high_min": 80, "medium_min": 45},
    )

    assert edge.link_id in result.updated_link_ids
    assert all(r.link_id != edge.link_id for r in result.transitions)


def test_created_by_state_counts_new_edges_only() -> None:
    m = matcher(*ac01_graphs(), fixture=AC01_FIXTURE)

    first = m.run_matching(input_case_ids=(), triggered_by=ADMIN)
    again = m.run_matching(input_case_ids=(), triggered_by=ADMIN)

    assert first.run.created_by_state == {"AUTO": 4, "SUGGESTED": 0}
    assert again.run.created_by_state == {"AUTO": 0, "SUGGESTED": 0}


class FailingLinks(InMemoryLinkStore):
    """Fails on the n-th write (put or remove), counting from 1."""

    def __init__(self, fail_at: int) -> None:
        super().__init__()
        self.writes, self.fail_at = 0, fail_at

    def _tick(self) -> None:
        self.writes += 1
        if self.writes == self.fail_at:
            raise ConnectionError("store unavailable")

    def put(self, edge: SameAsEdge) -> None:
        self._tick()
        super().put(edge)

    def remove(self, link_id: str) -> None:
        self._tick()
        super().remove(link_id)


@pytest.mark.parametrize("fail_at", [1, 2, 4])
def test_a_failed_create_is_never_reported_as_a_transition(fail_at: int) -> None:
    links = FailingLinks(fail_at)
    m = matcher(*ac01_graphs(), fixture=AC01_FIXTURE, links=links)

    result = m.run_matching(input_case_ids=(), triggered_by=ADMIN)

    assert result.run.status is RunStatus.FAILED
    assert {r.link_id for r in result.transitions} == {e.link_id for e in links.edges()}
    assert len(result.transitions) == fail_at - 1


def test_a_failed_withdrawal_is_never_reported_as_a_transition() -> None:
    links = FailingLinks(fail_at=0)
    m = matcher(*ac01_graphs(), links=links)
    m.run_matching(input_case_ids=(), triggered_by=ADMIN)
    [edge] = [e for e in links.edges() if e.entity_type.value == "PERSON"]
    links.fail_at = links.writes + 1

    result = m.run_matching(
        input_case_ids=(),
        triggered_by=ADMIN,
        thresholds_version=2,
        thresholds={"high_min": 80, "medium_min": 60},
    )

    assert result.run.status is RunStatus.FAILED
    assert links.get(edge.link_id) is not None
    assert all(r.link_id != edge.link_id for r in result.transitions)


@pytest.mark.parametrize(
    "thresholds",
    [{"high_min": 65, "medium_min": 45}, {"high_min": 80}, {"medium_min": 45}, {}],
)
def test_invalid_or_incomplete_thresholds_raise_thresholds_error(
    thresholds: dict[str, int],
) -> None:
    m = matcher(*ac01_graphs())

    with pytest.raises(ThresholdsError):
        m.run_matching(input_case_ids=(), triggered_by=ADMIN, thresholds=thresholds)
    assert m.links.edges() == ()


def test_thresholds_types_are_exported_for_the_api() -> None:
    assert Thresholds.validated(80, 45, 1) == DEFAULT_THRESHOLDS
