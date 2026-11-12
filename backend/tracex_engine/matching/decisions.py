"""Human decisions as engine transitions: `apply_decision` (spec section 6).

The engine checks only that `expected_from` is the edge's current state and that the transition
is legal; role and jurisdiction checks are the API's. The call is idempotent on `decision_id`: a
replay returns the recorded transition and changes nothing.
"""

from collections.abc import Callable

from tracex_engine.matching.link_store import LinkStore
from tracex_engine.matching.model import (
    DecisionError,
    HistoryEntry,
    LinkState,
    TransitionRecord,
)

_A, _S, _C, _R, _U = (
    LinkState.AUTO,
    LinkState.SUGGESTED,
    LinkState.CONFIRMED,
    LinkState.REJECTED,
    LinkState.UNDONE,
)

# Every human transition the spec allows; everything else is illegal (409 at the API).
LEGAL_DECISIONS = frozenset({(_S, _C), (_S, _R), (_A, _C), (_A, _U), (_C, _U), (_R, _S), (_U, _S)})


def apply_decision(
    links: LinkStore,
    clock: Callable[[], str],
    link_id: str,
    expected_from: LinkState,
    to_state: LinkState,
    actor_user_id: str,
    decision_id: str,
    reason_code: str | None,
    reason_text: str | None,
) -> TransitionRecord | DecisionError:
    edge = links.get(link_id)
    if edge is not None:
        for entry in edge.history:
            if entry.decision_id == decision_id:
                return _record(link_id, entry)
    if edge is None or edge.state is not expected_from:
        return DecisionError.STATE_MISMATCH
    if (expected_from, to_state) not in LEGAL_DECISIONS:
        return DecisionError.ILLEGAL_TRANSITION
    at = clock()
    entry = HistoryEntry(
        expected_from, to_state, actor_user_id, at, reason_code, reason_text, decision_id
    )
    links.put(edge.with_changes(state=to_state, updated_at=at, history=(*edge.history, entry)))
    return _record(link_id, entry)


def _record(link_id: str, entry: HistoryEntry) -> TransitionRecord:
    return TransitionRecord(
        link_id=link_id,
        from_state=entry.from_state,
        to_state=entry.to_state,
        actor=entry.actor,
        match_run_id=None,
        decision_id=entry.decision_id,
        reason_code=entry.reason_code,
        at=entry.at,
    )
