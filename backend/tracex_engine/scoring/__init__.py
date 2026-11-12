"""Scoring: evidence items, composite score, bands and gates (docs/specs/engine-matching.md §3, §5).

Pure functions over evidence items; no I/O. The matcher (`tracex_engine.matching`) produces
the items and the cluster verdict; this package turns them into a score, a band and the list
of failed gates.

Exposed:
    RULESET_VERSION, CATALOGUE, EvidenceSpec, pending_kinds   the evidence catalogue
    Thresholds, ThresholdsError, DEFAULT_THRESHOLDS            band thresholds (admin config)
    Band, Severity                                              the enums
    EvidenceItem, Source, Modifier, round_half_up               the evidence model
    compose, band_of, Breakdown, TierTotal                      composite score and band
    evaluate_gates, FailedGate, ClusterVerdict                  gates G1-G7
"""

from tracex_engine.scoring.composite import Breakdown, TierTotal, band_of, compose
from tracex_engine.scoring.evidence import EvidenceItem, Modifier, Source, round_half_up
from tracex_engine.scoring.gates import ClusterVerdict, FailedGate, evaluate_gates
from tracex_engine.scoring.ruleset import (
    CATALOGUE,
    DEFAULT_THRESHOLDS,
    RULESET_VERSION,
    Band,
    EvidenceSpec,
    Severity,
    Thresholds,
    ThresholdsError,
    pending_kinds,
)

__all__ = [
    "CATALOGUE",
    "DEFAULT_THRESHOLDS",
    "RULESET_VERSION",
    "Band",
    "Breakdown",
    "ClusterVerdict",
    "EvidenceItem",
    "EvidenceSpec",
    "FailedGate",
    "Modifier",
    "Severity",
    "Source",
    "Thresholds",
    "ThresholdsError",
    "TierTotal",
    "band_of",
    "compose",
    "evaluate_gates",
    "pending_kinds",
    "round_half_up",
]
