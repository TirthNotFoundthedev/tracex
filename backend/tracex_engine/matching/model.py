"""SAME_AS edges, their history, transition records and run records (spec section 6).

Plain immutable data. The engine returns transition and run records to the API, which writes
the audit rows; the engine itself never writes audit data and knows no users beyond the opaque
actor id it is given.
"""

from dataclasses import dataclass, field, replace
from decimal import Decimal
from enum import StrEnum
from typing import Any

from tracex_engine.graph import EntityType
from tracex_engine.scoring import Band, FailedGate

ENGINE_ACTOR = "engine"


class LinkState(StrEnum):
    AUTO = "AUTO"
    SUGGESTED = "SUGGESTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    UNDONE = "UNDONE"


ACTIVE_STATES = frozenset({LinkState.AUTO, LinkState.CONFIRMED})
HUMAN_STATES = frozenset({LinkState.CONFIRMED, LinkState.REJECTED, LinkState.UNDONE})
BLOCKED_STATES = frozenset({LinkState.REJECTED, LinkState.UNDONE})


class ReasonCode(StrEnum):
    """Reason codes of engine transitions (D37)."""

    DEMOTED = "DEMOTED"
    PROMOTED = "PROMOTED"
    WITHDRAWN = "WITHDRAWN"


class RunStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class HistoryEntry:
    """One state change on an edge. `decision_id` is None for engine transitions."""

    from_state: LinkState | None
    to_state: LinkState | None
    actor: str
    at: str
    reason_code: str | None = None
    reason_text: str | None = None
    decision_id: str | None = None


@dataclass(frozen=True)
class SameAsEdge:
    """A SAME_AS edge between two untouched entity nodes; `entity_a_id` < `entity_b_id` in
    entity id order. `evidence` is the scored part of the explanation payload (records,
    support, against, clamp_adjustment) as JSON-ready data."""

    link_id: str
    entity_a_id: str
    entity_b_id: str
    entity_type: EntityType
    case_a: str
    case_b: str
    state: LinkState
    score: Decimal
    band: Band
    gates_failed: tuple[FailedGate, ...]
    evidence: dict[str, Any]
    ruleset_version: str
    thresholds_version: int
    high_min: Decimal
    medium_min: Decimal
    match_run_id: str
    created_at: str
    updated_at: str
    history: tuple[HistoryEntry, ...] = field(default=())

    @property
    def pair(self) -> tuple[str, str]:
        return (self.entity_a_id, self.entity_b_id)

    @property
    def reopened(self) -> bool:
        """A human ended it once (REJECTED or UNDONE) and reopened it: only a human ends it."""
        return any(h.to_state in BLOCKED_STATES for h in self.history)

    def with_changes(self, **changes: Any) -> "SameAsEdge":
        return replace(self, **changes)


@dataclass(frozen=True)
class TransitionRecord:
    """One edge transition for the API's audit row. `to_state` is None for WITHDRAWN;
    `decision_id` is None for engine transitions, `match_run_id` None for human ones."""

    link_id: str
    from_state: LinkState | None
    to_state: LinkState | None
    actor: str
    match_run_id: str | None
    decision_id: str | None
    reason_code: str | None
    at: str


@dataclass(frozen=True)
class RunRecord:
    """What one matching run did (spec section 6). Low pairs are counted, never stored."""

    match_run_id: str
    started_at: str
    finished_at: str | None
    triggered_by: str
    input_case_ids: tuple[str, ...]
    ruleset_version: str
    thresholds_version: int
    counts_by_state: dict[str, int]
    counts_by_band: dict[str, int]
    oversized_block: int
    status: RunStatus
    error_code: str | None = None
    # Edges this run created, by state (AUTO, SUGGESTED): the totals an ADMIN may see.
    created_by_state: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class RunResult:
    """`transitions`: one record per state change. `updated_link_ids`: edges the run rewrote
    without a state change (score, band, gates, evidence, thresholds, run id); the API refreshes
    its link rows and cited lines from `explanation(link_id)` for both."""

    run: RunRecord
    transitions: tuple[TransitionRecord, ...]
    updated_link_ids: tuple[str, ...] = ()


class DecisionError(StrEnum):
    """Why `apply_decision` changed nothing.

    NOT_FOUND: no edge has this link id (never created, or withdrawn).
    STATE_MISMATCH: `expected_from` is not the edge's current state (also after losing a race).
    ILLEGAL_TRANSITION: the transition is not in the spec section 6 table.
    REPLAY_CONFLICT: the `decision_id` is already applied with other arguments."""

    ILLEGAL_TRANSITION = "ILLEGAL_TRANSITION"
    STATE_MISMATCH = "STATE_MISMATCH"
    NOT_FOUND = "NOT_FOUND"
    REPLAY_CONFLICT = "REPLAY_CONFLICT"
