"""Cross-case matching: blocking, evidence, SAME_AS edges, runs and decisions.

Spec: docs/specs/engine-matching.md (ruleset `engine-matching/1.1`). This slice implements
Tier 1 (exact) evidence, the exact opposing checks, every gate, SAME_AS edges with the D37
rerun rules and human decisions. Tier 2 and Tier 3 items are named seams (`pending_seams`) and
plug in as `EvidenceProvider`s.

The API imports:
    Matcher                     run_matching, apply_decision, explanation, cluster_of
    InMemoryLinkStore, Neo4jLinkStore, LinkStore     SAME_AS edge stores
    LinkState, ReasonCode, RunStatus, DecisionError  the enums
    SameAsEdge, HistoryEntry, TransitionRecord, RunRecord, RunResult   plain data returned
    build_explanation, cited_sources                 the payload of one link
    EvidenceProvider, pending_seams                  the Tier 2 / Tier 3 extension point
    engine_result                                    engine-result/1 document for the kit scorer
"""

from tracex_engine.matching.engine import Matcher
from tracex_engine.matching.explanation import build_explanation, cited_sources
from tracex_engine.matching.link_store import InMemoryLinkStore, LinkConflictError, LinkStore
from tracex_engine.matching.model import (
    DecisionError,
    HistoryEntry,
    LinkState,
    ReasonCode,
    RunRecord,
    RunResult,
    RunStatus,
    SameAsEdge,
    TransitionRecord,
)
from tracex_engine.matching.neo4j_links import Neo4jLinkStore
from tracex_engine.matching.providers import EvidenceProvider, NotYetImplemented, pending_seams
from tracex_engine.matching.result_export import engine_result, write_engine_result
from tracex_engine.scoring import DEFAULT_THRESHOLDS, Thresholds, ThresholdsError

__all__ = [
    "DEFAULT_THRESHOLDS",
    "DecisionError",
    "EvidenceProvider",
    "HistoryEntry",
    "InMemoryLinkStore",
    "LinkConflictError",
    "LinkState",
    "LinkStore",
    "Matcher",
    "Neo4jLinkStore",
    "NotYetImplemented",
    "ReasonCode",
    "RunRecord",
    "RunResult",
    "RunStatus",
    "SameAsEdge",
    "Thresholds",
    "ThresholdsError",
    "TransitionRecord",
    "build_explanation",
    "cited_sources",
    "engine_result",
    "pending_seams",
    "write_engine_result",
]
