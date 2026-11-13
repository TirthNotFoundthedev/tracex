"""`Matcher`: the engine calls the API makes (spec section 6, architecture section 6).

    run_matching(input_case_ids, triggered_by, thresholds_version, thresholds) -> RunResult
    apply_decision(link_id, expected_from, to_state, actor_user_id, decision_id,
                   reason_code, reason_text) -> TransitionRecord | DecisionError
    explanation(link_id) -> payload | None
    cluster_of(entity_id) -> entity ids joined to it by active edges

The matcher reads case graphs and writes SAME_AS edges through the two store interfaces; it
opens no other connection, writes no audit rows and knows nothing of users, roles or districts.
"""

import logging
import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from tracex_engine.graph import CaseGraphStore
from tracex_engine.matching.clusters import ActiveGraph
from tracex_engine.matching.decisions import apply_decision
from tracex_engine.matching.explanation import build_explanation
from tracex_engine.matching.link_store import LinkStore
from tracex_engine.matching.model import (
    ACTIVE_STATES,
    DecisionError,
    LinkState,
    RunRecord,
    RunResult,
    RunStatus,
    TransitionRecord,
)
from tracex_engine.matching.providers import EvidenceProvider, default_providers
from tracex_engine.matching.run import MatchRun
from tracex_engine.scoring import DEFAULT_THRESHOLDS, RULESET_VERSION, Thresholds, ThresholdsError

logger = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_link_id() -> str:
    """Random UUIDv4, never derived from entity, case or run ids."""
    return str(uuid.uuid4())


class Matcher:
    def __init__(
        self,
        graphs: CaseGraphStore,
        links: LinkStore,
        providers: Sequence[EvidenceProvider] | None = None,
        clock: Callable[[], str] = utc_now,
        new_id: Callable[[], str] = new_link_id,
    ) -> None:
        self.graphs = graphs
        self.links = links
        self.providers = tuple(default_providers() if providers is None else providers)
        self.clock = clock
        self.new_id = new_id

    def run_matching(
        self,
        input_case_ids: Sequence[str] = (),
        triggered_by: str = "",
        thresholds_version: int = DEFAULT_THRESHOLDS.version,
        thresholds: Mapping[str, int] | None = None,
    ) -> RunResult:
        """Match `input_case_ids` (empty: every loaded case) against every loaded case.

        Raises `ThresholdsError` before anything runs when the thresholds are invalid. Any
        other failure ends the run with status FAILED; transitions already applied are
        returned with it so the API can audit them."""
        if thresholds is None:
            limits = Thresholds(
                DEFAULT_THRESHOLDS.high_min, DEFAULT_THRESHOLDS.medium_min, thresholds_version
            )
        else:
            if "high_min" not in thresholds or "medium_min" not in thresholds:
                raise ThresholdsError("thresholds need high_min and medium_min")
            limits = Thresholds.validated(
                thresholds["high_min"], thresholds["medium_min"], thresholds_version
            )
        run = MatchRun(self.graphs, self.links, self.providers, self.clock, self.new_id, limits)
        try:
            return run.execute(input_case_ids, triggered_by)
        except Exception:
            logger.exception("matching run failed")
            record = RunRecord(
                match_run_id=getattr(run, "run_id", self.new_id()),
                started_at=self.clock(),
                finished_at=self.clock(),
                triggered_by=triggered_by,
                input_case_ids=tuple(input_case_ids),
                ruleset_version=RULESET_VERSION,
                thresholds_version=thresholds_version,
                counts_by_state=dict(run.by_state),
                counts_by_band=dict(run.by_band),
                oversized_block=0,
                status=RunStatus.FAILED,
                error_code="ENGINE_ERROR",
                created_by_state=dict(run.created),
            )
            return RunResult(record, tuple(run.transitions), tuple(run.updated))

    def apply_decision(
        self,
        link_id: str,
        expected_from: LinkState,
        to_state: LinkState,
        actor_user_id: str,
        decision_id: str,
        reason_code: str | None,
        reason_text: str | None,
    ) -> TransitionRecord | DecisionError:
        return apply_decision(
            self.links,
            self.clock,
            link_id,
            expected_from,
            to_state,
            actor_user_id,
            decision_id,
            reason_code,
            reason_text,
        )

    def explanation(self, link_id: str) -> dict[str, Any] | None:
        edge = self.links.get(link_id)
        return build_explanation(edge) if edge else None

    def cluster_of(self, entity_id: str) -> set[str]:
        # Loads every edge per call: fine at kit scale; revisit with a traversal at scale.
        graph = ActiveGraph()
        for edge in self.links.edges():
            if edge.state in ACTIVE_STATES:
                graph.add(*edge.pair)
        return graph.component(entity_id)
