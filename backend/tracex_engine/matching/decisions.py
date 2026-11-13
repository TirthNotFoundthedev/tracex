"""Human decisions as engine transitions: `apply_decision` (spec section 6).

The engine checks only that `expected_from` is the edge's current state and that the transition
is legal; role and jurisdiction checks are the API's. The call is idempotent on `decision_id`: a
replay with the same arguments returns the recorded transition and changes nothing; the same
`decision_id` with other arguments is refused (REPLAY_CONFLICT). The write is a compare-and-set
on the `updated_at` read, so a concurrent replay or another decision cannot both win: the loser
re-reads the edge and answers from what is stored.
"""

from collections.abc import Callable

from tracex_engine.matching.link_store import LinkStore
from tracex_engine.matching.model import (
    DecisionError,
    HistoryEntry,
    LinkState,
    SameAsEdge,
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
    wanted = (expected_from, to_state, actor_user_id, reason_code, reason_text)
    edge = links.get(link_id)
    if edge is None:
        return DecisionError.NOT_FOUND
    replayed = _replay(edge, decision_id, wanted)
    if replayed is not None:
        return replayed
    if edge.state is not expected_from:
        return DecisionError.STATE_MISMATCH
    if (expected_from, to_state) not in LEGAL_DECISIONS:
        return DecisionError.ILLEGAL_TRANSITION
    at = clock()
    entry = HistoryEntry(
        expected_from, to_state, actor_user_id, at, reason_code, reason_text, decision_id
    )
    changed = edge.with_changes(state=to_state, updated_at=at, history=(*edge.history, entry))
    if links.put_if_unchanged(changed, edge.updated_at):
        return _record(link_id, entry)
    current = links.get(link_id)
    if current is None:
        return DecisionError.NOT_FOUND
    return _replay(current, decision_id, wanted) or DecisionError.STATE_MISMATCH


def _replay(
    edge: SameAsEdge,
    decision_id: str,
    wanted: tuple[LinkState, LinkState, str, str | None, str | None],
) -> TransitionRecord | DecisionError | None:
    """The stored outcome of `decision_id` on this edge, or None if it was never applied."""
    for entry in edge.history:
        if entry.decision_id == decision_id:
            stored = (
                entry.from_state,
                entry.to_state,
                entry.actor,
                entry.reason_code,
                entry.reason_text,
            )
            if stored != wanted:
                return DecisionError.REPLAY_CONFLICT
            return _record(edge.link_id, entry)
    return None


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
