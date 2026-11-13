"""Adapter: the stored entities and SAME_AS edges as an `engine-result/1` document.

That is the input of the data-kit reference scorer (`python -m datakit score`, schema
`data-kit/schema/engine_result.schema.json`). Every entity of every stored case is listed with
every mention line (PERSON and ORG mentions with their own `raw_text`), and every stored edge
with its state, band, score, failed gates, evidence kinds and cited lines.
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from tracex_engine.graph import CaseGraphStore
from tracex_engine.matching.explanation import cited_sources
from tracex_engine.matching.link_store import LinkStore
from tracex_engine.matching.model import RunRecord, SameAsEdge

SCHEMA_VERSION = "engine-result/1"


def engine_result(
    graphs: CaseGraphStore,
    links: LinkStore,
    *,
    batches_loaded: Sequence[str],
    harness_applied: Sequence[str] = (),
    run: RunRecord | None = None,
) -> dict[str, Any]:
    entities: list[dict[str, Any]] = []
    for case_id in graphs.case_ids():
        graph = graphs.read_case(case_id)
        if graph is None:
            continue
        mentions: dict[str, list[dict[str, Any]]] = {}
        for m in graph.mentions:
            mentions.setdefault(m.entity_id, []).append(
                {"case_id": m.case_id, "file": m.file, "line": m.line, "raw_text": m.raw_text}
            )
        entities.extend(
            {
                "id": e.entity_id,
                "type": e.type.value,
                "normalized": e.normalized,
                "mentions": mentions[e.entity_id],
            }
            for e in graph.entities
        )
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "batches_loaded": list(batches_loaded),
        "harness_applied": list(harness_applied),
        "entities": entities,
        "edges": [_edge(e) for e in links.edges()],
    }
    if run is not None:
        document["stats"] = {"oversized_block_count": run.oversized_block}
        document["run"] = {
            "ruleset_version": run.ruleset_version,
            "thresholds_version": run.thresholds_version,
            "status": run.status.value,
            "counts": dict(run.counts_by_state),
        }
    return document


def _edge(edge: SameAsEdge) -> dict[str, Any]:
    evidence = edge.evidence
    kinds = {i["kind"] for t in evidence["support"] for i in t["items"]}
    kinds |= {i["kind"] for i in evidence["against"]}
    return {
        "a": edge.entity_a_id,
        "b": edge.entity_b_id,
        "state": edge.state.value,
        "band": edge.band.value,
        "score": str(edge.score),
        "gates_failed": [
            {"gate": g.gate, "template_key": g.template_key} if g.gate == "G6" else g.gate
            for g in edge.gates_failed
        ],
        "evidence_kinds": sorted(kinds),
        "sources": [
            {"case_id": s.case_id, "file": s.document_id, "line": s.line}
            for s in cited_sources(edge)
        ],
        "link_id": edge.link_id,
    }


def write_engine_result(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, ensure_ascii=False, indent=1, sort_keys=True), "utf-8")
