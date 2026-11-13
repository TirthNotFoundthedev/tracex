"""The explanation payload of one link (spec section 7, `contracts/explanation.schema.json`).

The payload carries no English: every line renders from `template_key` and `params`. Sources
are `{case_id, document_id, line}` with `document_id` the file name inside the case; the API
adds `page`, `document_type` and `case_number` when it serves the payload. History entries carry
only `from`, `to`, `at` and `reason_code` (engine reason codes; null for a creation and for a
human decision, as the contract states); `actor` and `reason_text` stay on the edge.
"""

from decimal import Decimal
from typing import Any

from tracex_engine.graph import Entity
from tracex_engine.matching.corpus import Corpus
from tracex_engine.matching.model import ENGINE_ACTOR, SameAsEdge
from tracex_engine.scoring import Breakdown, EvidenceItem, Source
from tracex_engine.scoring.ruleset import (
    CAP_TEMPLATE_KEY,
    CLAMP_TEMPLATE_KEY,
    TRAP_FACTOR,
    TRAP_TEMPLATE_KEY,
)


def number(value: Decimal) -> int | float:
    """JSON number of an exact one-decimal value (weights and thresholds print as integers)."""
    return int(value) if value == value.to_integral_value() else float(value)


def decimal_number(value: Decimal) -> float:
    return float(value)


def source_json(source: Source) -> dict[str, Any]:
    return {"case_id": source.case_id, "document_id": source.document_id, "line": source.line}


def record_json(corpus: Corpus, entity: Entity) -> dict[str, Any]:
    return {
        "entity_id": entity.entity_id,
        "case_id": entity.case_id,
        "raw_text": entity.display_value,
        "normalized": entity.normalized,
        "extraction_confidence": entity.confidence,
        "source": source_json(corpus.first_source(entity.entity_id)),
    }


def item_json(item: EvidenceItem, evidence_id: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "evidence_id": evidence_id,
        "kind": item.kind,
        "strength": float(item.strength),
        "weight": number(item.weight),
        "contribution": decimal_number(item.contribution),
        "is_anchor": item.is_anchor,
        "modifiers": [
            {"code": m.code, "factor": float(TRAP_FACTOR), "template_key": TRAP_TEMPLATE_KEY}
            for m in item.modifiers
        ],
        "template_key": item.spec.template_key,
        "params": dict(item.params),
        "sources": [source_json(s) for s in item.sources],
    }
    if item.severity is not None:
        out["severity"] = item.severity.value
    return out


def evidence_json(corpus: Corpus, a: Entity, b: Entity, breakdown: Breakdown) -> dict[str, Any]:
    """The scored part of the payload, stored on the edge as `evidence`."""
    counter = iter(range(1, 10_000))
    support = []
    for tier in breakdown.support:
        support.append(
            {
                "tier": tier.tier,
                "cap": number(tier.cap),
                "raw": decimal_number(tier.raw),
                "cap_adjustment": {
                    "value": decimal_number(tier.cap_adjustment),
                    "template_key": CAP_TEMPLATE_KEY,
                },
                "subtotal": decimal_number(tier.subtotal),
                "items": [item_json(i, f"ev_{next(counter)}") for i in tier.items],
            }
        )
    against = [item_json(i, f"ev_{next(counter)}") for i in breakdown.against]
    return {
        "records": [record_json(corpus, a), record_json(corpus, b)],
        "support": support,
        "against": against,
        "clamp_adjustment": {
            "value": decimal_number(breakdown.clamp_adjustment),
            "template_key": CLAMP_TEMPLATE_KEY,
        },
    }


def build_explanation(edge: SameAsEdge) -> dict[str, Any]:
    """The full payload of one link, as the API stores and serves it."""
    return {
        "link_id": edge.link_id,
        "entity_type": edge.entity_type.value,
        "state": edge.state.value,
        "score": decimal_number(edge.score),
        "band": edge.band.value,
        "thresholds": {
            "high_min": number(edge.high_min),
            "medium_min": number(edge.medium_min),
            "thresholds_version": edge.thresholds_version,
        },
        "ruleset_version": edge.ruleset_version,
        "gates": {
            "passed": not edge.gates_failed,
            "failed": [{"gate": g.gate, "template_key": g.template_key} for g in edge.gates_failed],
        },
        **edge.evidence,
        "history": [
            {
                "from": h.from_state.value if h.from_state else None,
                "to": h.to_state.value if h.to_state else None,
                "at": h.at,
                "reason_code": h.reason_code if h.actor == ENGINE_ACTOR else None,
            }
            for h in edge.history
        ],
    }


def cited_sources(edge: SameAsEdge) -> list[Source]:
    """The cited-line set: every record source and every item source (spec section 7)."""
    found: set[Source] = set()
    evidence = edge.evidence
    for record in evidence["records"]:
        found.add(_source(record["source"]))
    for tier in evidence["support"]:
        for item in tier["items"]:
            found.update(_source(s) for s in item["sources"])
    for item in evidence["against"]:
        found.update(_source(s) for s in item["sources"])
    return sorted(found)


def _source(raw: dict[str, Any]) -> Source:
    return Source(str(raw["case_id"]), str(raw["document_id"]), int(raw["line"]))
