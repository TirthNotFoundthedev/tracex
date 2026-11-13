"""`apply_decision` under replay and races (review of PR #28, minor 5 and NOT_FOUND).

The write is conditional on the edge being unchanged since it was read; a lost race re-reads
the edge and returns the recorded transition if the same decision won. A known `decision_id`
with other arguments is refused, and a link id with no edge is NOT_FOUND.
"""

import pytest

from tests.engine.matching.fixtures import AC01_FIXTURE, ac01_graphs, matcher
from tracex_engine.matching import (
    DecisionError,
    InMemoryLinkStore,
    LinkState,
    Matcher,
    Neo4jLinkStore,
    SameAsEdge,
    TransitionRecord,
)
from tracex_engine.matching.decisions import apply_decision


def ac01(links: InMemoryLinkStore | None = None) -> tuple[Matcher, SameAsEdge]:
    m = matcher(*ac01_graphs(), fixture=AC01_FIXTURE, links=links)
    m.run_matching(input_case_ids=(), triggered_by="u-admin")
    [edge] = [e for e in m.links.edges() if e.entity_type.value == "PERSON"]
    return m, edge


class RacingLinks(InMemoryLinkStore):
    """On the first read of an edge, another worker applies `racer` first (a concurrent replay
    or a different decision), so the reader holds a stale copy."""

    def __init__(self) -> None:
        super().__init__()
        self.racer: tuple[object, ...] | None = None

    def get(self, link_id: str) -> SameAsEdge | None:
        edge = super().get(link_id)
        if self.racer is not None:
            racer, self.racer = self.racer, None
            outcome = apply_decision(self, lambda: "2026-12-01T00:00:00Z", *racer)  # type: ignore[arg-type]
            assert isinstance(outcome, TransitionRecord)
        return edge


def test_a_concurrent_replay_writes_the_decision_once() -> None:
    links = RacingLinks()
    m, edge = ac01(links)
    args = (edge.link_id, LinkState.AUTO, LinkState.CONFIRMED, "u-inv", "d-1", None, None)
    links.racer = args

    record = m.apply_decision(*args)

    assert isinstance(record, TransitionRecord) and record.decision_id == "d-1"
    stored = links.get(edge.link_id)
    assert stored is not None
    assert [h.decision_id for h in stored.history].count("d-1") == 1


def test_a_lost_race_against_another_decision_is_a_state_mismatch() -> None:
    links = RacingLinks()
    m, edge = ac01(links)
    links.racer = (edge.link_id, LinkState.AUTO, LinkState.UNDONE, "u-sup", "d-9", "X", "x")

    outcome = m.apply_decision(
        edge.link_id, LinkState.AUTO, LinkState.CONFIRMED, "u-inv", "d-1", None, None
    )

    assert outcome is DecisionError.STATE_MISMATCH
    stored = links.get(edge.link_id)
    assert stored is not None and stored.state is LinkState.UNDONE
    assert [h.decision_id for h in stored.history] == [None, "d-9"]


def test_a_known_decision_id_with_other_arguments_is_refused() -> None:
    m, edge = ac01()
    m.apply_decision(edge.link_id, LinkState.AUTO, LinkState.CONFIRMED, "u-inv", "d-1", None, None)
    before = m.links.get(edge.link_id)

    outcome = m.apply_decision(
        edge.link_id, LinkState.AUTO, LinkState.UNDONE, "u-inv", "d-1", "X", "x"
    )

    assert outcome is DecisionError.REPLAY_CONFLICT
    assert m.links.get(edge.link_id) == before


@pytest.mark.parametrize("link_id", ["no-such-link", "withdrawn"])
def test_a_link_id_with_no_edge_is_not_found(link_id: str) -> None:
    m, edge = ac01()
    if link_id == "withdrawn":
        m.links.remove(edge.link_id)
        link_id = edge.link_id

    outcome = m.apply_decision(link_id, LinkState.AUTO, LinkState.CONFIRMED, "u", "d-1", None, None)

    assert outcome is DecisionError.NOT_FOUND


def test_both_stores_offer_a_conditional_write() -> None:
    assert hasattr(InMemoryLinkStore, "put_if_unchanged")
    assert hasattr(Neo4jLinkStore, "put_if_unchanged")
