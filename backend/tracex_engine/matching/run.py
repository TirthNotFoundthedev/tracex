"""One matching run: candidates, evidence, score, band and gates, then SAME_AS edges (spec 2-6).

Run order (C5): identifier pairs first, so person items can rely on settled identifier links,
then person and org pairs; inside each group by score descending, ties by entity ids. Rerun
rules (D37): CONFIRMED, REJECTED and UNDONE edges are never changed and blocked pairs never
compared; an AUTO edge that fails a gate is DEMOTED; a SUGGESTED edge that passes every gate is
PROMOTED unless a human reopened it; a SUGGESTED edge below medium_min is WITHDRAWN (removed).

While a pair waits for its turn, its own earlier AUTO edge is left out of the cluster checks,
so a rerun on an unchanged store reaches exactly the first run's decisions (AC-23).
"""

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from tracex_engine.graph import CaseGraphStore, Entity, EntityType, entity_sort_key
from tracex_engine.matching.blocking import Pair, canonical, identifier_candidates, party_candidates
from tracex_engine.matching.clusters import ActiveGraph, cluster_verdict
from tracex_engine.matching.corpus import Corpus
from tracex_engine.matching.evidence import (
    Context,
    identifier_items,
    person_conflicts,
    shared_identifier_items,
)
from tracex_engine.matching.explanation import evidence_json
from tracex_engine.matching.flags import identifier_flags
from tracex_engine.matching.link_store import LinkStore
from tracex_engine.matching.model import (
    ENGINE_ACTOR,
    HUMAN_STATES,
    HistoryEntry,
    LinkState,
    ReasonCode,
    RunRecord,
    RunResult,
    RunStatus,
    SameAsEdge,
    TransitionRecord,
)
from tracex_engine.matching.providers import EvidenceProvider
from tracex_engine.scoring import (
    RULESET_VERSION,
    Band,
    Breakdown,
    FailedGate,
    Thresholds,
    band_of,
    compose,
    evaluate_gates,
)
from tracex_engine.scoring.ruleset import IDENTIFIER_TYPES


@dataclass(frozen=True)
class Scored:
    a: Entity
    b: Entity
    breakdown: Breakdown
    band: Band

    @property
    def pair(self) -> Pair:
        return (self.a.entity_id, self.b.entity_id)

    def order(self) -> tuple[Decimal, tuple[int, int, int], tuple[int, int, int]]:
        return (
            -self.breakdown.score,
            entity_sort_key(self.a.entity_id),
            entity_sort_key(self.b.entity_id),
        )


class MatchRun:
    def __init__(
        self,
        graphs: CaseGraphStore,
        links: LinkStore,
        providers: Sequence[EvidenceProvider],
        clock: Callable[[], str],
        new_id: Callable[[], str],
        thresholds: Thresholds,
    ) -> None:
        self.graphs, self.links, self.providers = graphs, links, providers
        self.clock, self.new_id, self.thresholds = clock, new_id, thresholds
        self.transitions: list[TransitionRecord] = []
        self.by_state: Counter[str] = Counter()
        self.by_band: Counter[str] = Counter()

    def execute(self, input_case_ids: Sequence[str], triggered_by: str) -> RunResult:
        started, self.run_id = self.clock(), self.new_id()
        corpus = Corpus.load(self.graphs)
        scope = frozenset(input_case_ids) or frozenset(corpus.case_ids)
        self.corpus = corpus
        self.stored = {e.pair: e for e in self.links.edges()}
        confirmed = frozenset(
            frozenset(p)
            for p, e in self.stored.items()
            if e.state is LinkState.CONFIRMED and e.entity_type is EntityType.PERSON
        )
        id_found = identifier_candidates(corpus, scope)
        party_found = party_candidates(corpus, scope)
        id_pairs, party_pairs = id_found.pairs, party_found.pairs
        for provider in self.providers:
            for x, y in provider.candidates(corpus):
                self._add(canonical(x, y), scope, id_pairs, party_pairs)
        for edge in self.stored.values():
            if edge.state not in HUMAN_STATES:
                self._add(edge.pair, scope, id_pairs, party_pairs)
        pending = (id_pairs | party_pairs) - {
            p for p, e in self.stored.items() if e.state in HUMAN_STATES
        }
        self.active = ActiveGraph()
        for edge in self.stored.values():
            if edge.state is LinkState.CONFIRMED or (
                edge.state is LinkState.AUTO and edge.pair not in pending
            ):
                self.active.add(*edge.pair)
        self.ctx = Context(corpus, identifier_flags(corpus, confirmed), self.active.has)
        for pairs in (id_pairs, party_pairs):
            scored = sorted((self._score(p) for p in pairs & pending), key=Scored.order)
            for item in scored:
                self._settle(item)
        run = RunRecord(
            match_run_id=self.run_id,
            started_at=started,
            finished_at=self.clock(),
            triggered_by=triggered_by,
            input_case_ids=tuple(input_case_ids),
            ruleset_version=RULESET_VERSION,
            thresholds_version=self.thresholds.version,
            counts_by_state=dict(self.by_state),
            counts_by_band=dict(self.by_band),
            oversized_block=id_found.oversized_block + party_found.oversized_block,
            status=RunStatus.SUCCEEDED,
        )
        return RunResult(run, tuple(self.transitions))

    def _add(self, pair: Pair, scope: frozenset[str], ids: set[Pair], parties: set[Pair]) -> None:
        entities = self.corpus.entities
        if pair[0] not in entities or pair[1] not in entities:
            return
        a, b = entities[pair[0]], entities[pair[1]]
        if a.type is not b.type or a.case_id == b.case_id:
            return
        if a.case_id in scope or b.case_id in scope:
            (ids if a.type in IDENTIFIER_TYPES else parties).add(pair)

    def _score(self, pair: Pair) -> Scored:
        a, b = self.corpus.entities[pair[0]], self.corpus.entities[pair[1]]
        if a.type in IDENTIFIER_TYPES:
            items = identifier_items(self.ctx, a, b)
        else:
            items = shared_identifier_items(self.ctx, a, b)
            if a.type is EntityType.PERSON:
                items += person_conflicts(self.corpus, a, b)
        for provider in self.providers:
            items += provider.items(self.corpus, a, b)
        breakdown = compose(a.type, items)
        return Scored(a, b, breakdown, band_of(breakdown, self.thresholds))

    def _settle(self, s: Scored) -> None:
        verdict = cluster_verdict(self.active, self.corpus, *s.pair)
        failed = evaluate_gates(
            s.breakdown,
            thresholds=self.thresholds,
            confidences=(s.a.confidence, s.b.confidence),
            cluster=verdict,
        )
        target = None if s.band is Band.LOW else (LinkState.SUGGESTED if failed else LinkState.AUTO)
        self.by_band[s.band.value] += 1
        existing = self.stored.get(s.pair)
        now = self.clock()
        if existing is None:
            final = self._create(s, failed, target, now) if target else None
        elif existing.reopened:
            final = existing.state
            if target:
                self._update(existing, s, failed, existing.state, now, ())
        elif target is None:
            final = None
            self._withdraw(existing, now)
        else:
            final = target
            reason = None
            if target is not existing.state:
                reason = ReasonCode.PROMOTED if target is LinkState.AUTO else ReasonCode.DEMOTED
            self._update(existing, s, failed, target, now, (reason,) if reason else ())
        self.by_state[final.value if final else "NONE"] += 1
        if final is LinkState.AUTO:
            self.active.add(*s.pair)

    def _content(self, s: Scored, failed: tuple[FailedGate, ...]) -> dict[str, object]:
        return {
            "score": s.breakdown.score,
            "band": s.band,
            "gates_failed": failed,
            "evidence": evidence_json(self.corpus, s.a, s.b, s.breakdown),
            "ruleset_version": RULESET_VERSION,
            "thresholds_version": self.thresholds.version,
            "high_min": self.thresholds.high_min,
            "medium_min": self.thresholds.medium_min,
        }

    def _record(
        self,
        edge: SameAsEdge,
        frm: LinkState | None,
        to: LinkState | None,
        reason: str | None,
        at: str,
    ) -> HistoryEntry:
        self.transitions.append(
            TransitionRecord(edge.link_id, frm, to, ENGINE_ACTOR, self.run_id, None, reason, at)
        )
        return HistoryEntry(frm, to, ENGINE_ACTOR, at, reason)

    def _create(
        self, s: Scored, failed: tuple[FailedGate, ...], state: LinkState, now: str
    ) -> LinkState:
        content = self._content(s, failed)
        edge = SameAsEdge(
            link_id=self.new_id(),
            entity_a_id=s.a.entity_id,
            entity_b_id=s.b.entity_id,
            entity_type=s.a.type,
            case_a=s.a.case_id,
            case_b=s.b.case_id,
            state=state,
            match_run_id=self.run_id,
            created_at=now,
            updated_at=now,
            **content,  # type: ignore[arg-type]
        )
        entry = self._record(edge, None, state, None, now)
        self.links.put(edge.with_changes(history=(entry,)))
        return state

    def _update(
        self,
        edge: SameAsEdge,
        s: Scored,
        failed: tuple[FailedGate, ...],
        state: LinkState,
        now: str,
        reasons: tuple[ReasonCode, ...],
    ) -> None:
        content = self._content(s, failed)
        if state is edge.state and all(getattr(edge, k) == v for k, v in content.items()):
            return
        history = edge.history
        for reason in reasons:
            history += (self._record(edge, edge.state, state, reason.value, now),)
        self.links.put(
            edge.with_changes(
                state=state, match_run_id=self.run_id, updated_at=now, history=history, **content
            )
        )

    def _withdraw(self, edge: SameAsEdge, now: str) -> None:
        if edge.state is LinkState.AUTO:
            self._record(edge, LinkState.AUTO, LinkState.SUGGESTED, ReasonCode.DEMOTED.value, now)
        self._record(edge, LinkState.SUGGESTED, None, ReasonCode.WITHDRAWN.value, now)
        self.links.remove(edge.link_id)
