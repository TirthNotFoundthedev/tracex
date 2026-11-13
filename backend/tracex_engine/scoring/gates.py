"""Gates G1-G7: the High rule, the only path to a link without human review (spec section 5).

Identifier pairs are judged on G1, G4, G5, G6; person pairs on G1-G6; org pairs on G1, G4,
G5, G6 and G7 (org pairs are never AUTO in this ruleset). A pair is AUTO only when no gate
fails. The cluster checks C3 and C4 (G6) need the store, so the matcher computes them and
passes the verdict in.
"""

from dataclasses import dataclass

from tracex_engine.graph import EntityType
from tracex_engine.scoring.composite import Breakdown
from tracex_engine.scoring.ruleset import (
    G6_BRIDGE,
    G6_CONFLICT,
    G6_SAME_CASE,
    GATE_TEMPLATE_KEYS,
    IDENTIFIER_TYPES,
    MIN_CONFIDENCE,
    TIER_MIN_CONTRIBUTION,
    Severity,
    Thresholds,
)


@dataclass(frozen=True)
class FailedGate:
    gate: str
    template_key: str


@dataclass(frozen=True)
class ClusterVerdict:
    """C3 and C4 on the cluster the edge would create (spec section 6)."""

    conflict: bool = False
    bridge: bool = False
    same_case: bool = False


def _failed(gate: str) -> FailedGate:
    return FailedGate(gate, GATE_TEMPLATE_KEYS[gate])


def evaluate_gates(
    breakdown: Breakdown,
    *,
    thresholds: Thresholds,
    confidences: tuple[float, float],
    cluster: ClusterVerdict,
) -> tuple[FailedGate, ...]:
    """The failed gates in gate order; empty means every gate passed (AUTO)."""
    entity_type = breakdown.entity_type
    person = entity_type is EntityType.PERSON
    failed: list[FailedGate] = []
    if breakdown.vetoed or breakdown.score < thresholds.high_min:
        failed.append(_failed("G1"))
    if person and not any(i.is_anchor for t in breakdown.support for i in t.items):
        failed.append(_failed("G2"))
    if person:
        counting = [t for t in breakdown.support if t.subtotal >= TIER_MIN_CONTRIBUTION]
        if len(counting) < 2:
            failed.append(_failed("G3"))
    if any(i.severity in (Severity.HARD, Severity.VETO) for i in breakdown.against):
        failed.append(_failed("G4"))
    if min(confidences) < MIN_CONFIDENCE:
        failed.append(_failed("G5"))
    for flag, key in (
        (cluster.conflict, G6_CONFLICT),
        (cluster.bridge, G6_BRIDGE),
        (cluster.same_case, G6_SAME_CASE),
    ):
        if flag:
            failed.append(FailedGate("G6", key))
    if entity_type is EntityType.ORG:
        failed.append(_failed("G7"))
    assert person or entity_type is EntityType.ORG or entity_type in IDENTIFIER_TYPES  # noqa: S101
    return tuple(failed)
