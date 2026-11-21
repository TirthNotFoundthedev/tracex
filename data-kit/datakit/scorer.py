"""Reference scorer: an engine result against `ground_truth.json` (spec section 8.3).

Pure functions over two JSON documents; standard library only. The engine result format is
`schema/engine_result.schema.json`; `score` returns a JSON-serialisable report.

Checks: S1 expected links (state, band, gates as a set), S2 exact scores, S3 non-links, S4 closed
world, S5 provenance. S6 is reported, never gating.

Deferral: an expected link named in `defer` may wait for a later engine tier. If it is missing, or
every one of its failures is "not there yet" (state, band or score at or below the expected one,
other evidence kinds, gates or cited lines absent), it is reported under `deferred` and counted
under `deferred` in the check totals, never as passed or failed. A deferred link that is above its
expected state, band or score, or that cites a line outside its two end cases, fails as usual, and
deferral never reaches S3 non-links, S4 closed world and integrity, or forbidden trap hits.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection
from decimal import Decimal
from typing import Any

from datakit.scoreinput import (
    BATCH_ORDER,
    Edge,
    EngineResult,
    ScoreInputError,
    gate_key,
    parse_result,
    ref_of,
)
from datakit.scoremap import GroundTruthIndex

REPORT_SCHEMA_VERSION = "score-report/1"

__all__ = ["REPORT_SCHEMA_VERSION", "ScoreInputError", "format_report", "score"]


class _Scorer:
    def __init__(self, gt: dict[str, Any], result: EngineResult, defer: frozenset[str]) -> None:
        self.gt = gt
        self.result = result
        self.defer = defer
        self.deferred: list[dict[str, Any]] = []
        self.index = GroundTruthIndex(gt)
        self.entities = {e["gt_id"]: e for e in gt["entities"]}
        self.per_mention = {
            eid: self.index.map_mentions(entity) for eid, entity in result.entities.items()
        }
        self.mapped = {
            eid: self.index.closure(frozenset().union(*self.per_mention[eid]))
            for eid in result.entities
        }
        self.confirm_targets: dict[str, set[str]] = {
            s["id"]: {x["target"] for x in s["steps"] if x["action"] == "CONFIRM"}
            for s in gt["scenarios"]
        }
        pair_of = {link["id"]: (link["a"], link["b"]) for link in gt["expected_links"]}
        self.human_steps: set[tuple[str, str]] = {
            (x["action"], x["target"])
            for s in gt["scenarios"]
            if s["id"] in result.harness_applied
            for x in s["steps"]
        }
        # A human step on an expected link covers every expected link on the same pair (a later
        # batch's expectation of the pair, such as REJECTED after the AC-15 step).
        self.human_pairs: set[tuple[str, tuple[str, str]]] = {
            (action, pair_of[target]) for action, target in self.human_steps if target in pair_of
        }
        self.cross = [g for g in gt["groups"] if g["scope"] == "cross_case"]
        self.groups_of: dict[str, set[int]] = defaultdict(set)
        for position, group in enumerate(self.cross):
            for member in group["members"]:
                self.groups_of[member].add(position)
        self.missed: list[dict[str, Any]] = []
        self.wrong: list[dict[str, Any]] = []
        self.forbidden: list[dict[str, Any]] = []
        self.skipped: list[dict[str, Any]] = []
        self.evaluated_acs: set[str] = set()
        self.checks = {
            k: {"passed": 0, "failed": 0, "skipped": 0, "deferred": 0}
            for k in ("S1", "S2", "S3", "S4", "S5")
        }
        self.link_edges: set[int] = set()
        self.human_ok: set[int] = set()
        self.band_scores: dict[str, dict[str, Any]] = {}

    # --- helpers ---------------------------------------------------------------------------

    def _groups(self, gt_ids: frozenset[str]) -> set[int]:
        out: set[int] = set()
        for gt_id in gt_ids:
            out |= self.groups_of.get(gt_id, set())
        return out

    def _touching(self, first: str, second: str) -> list[Edge]:
        """Edges joining an entity matching `first` to one matching `second`, either order."""
        left, right = self.index.closure({first}), self.index.closure({second})
        return [
            edge
            for edge in self.result.edges
            if (self.mapped[edge.a] & left and self.mapped[edge.b] & right)
            or (self.mapped[edge.a] & right and self.mapped[edge.b] & left)
        ]

    @staticmethod
    def _edge_ref(edge: Edge) -> dict[str, str]:
        return {"a": edge.a, "b": edge.b}

    def _end_cases(self, edge: Edge) -> set[str]:
        cases: set[str] = set()
        for end in (edge.a, edge.b):
            cases |= {str(r["case_id"]) for r in self.result.entities[end]["mentions"]}
        return cases

    # --- S1, S2, S5 on expected links --------------------------------------------------------

    def _applicable_links(self) -> list[dict[str, Any]]:
        loaded = self.result.batches_loaded
        latest: dict[tuple[str, str], str] = {}
        for link in self.gt["expected_links"]:
            applied = not link["harness"] or link["harness"] in self.result.harness_applied
            if BATCH_ORDER[link["batch_min"]] <= loaded and applied:
                key = (link["a"], link["b"])
                latest[key] = max(latest.get(key, "b01"), link["batch_min"])
        links: list[dict[str, Any]] = []
        for link in self.gt["expected_links"]:
            reason = ""
            if BATCH_ORDER[link["batch_min"]] > loaded:
                reason = f"batch {link['batch_min']} not loaded"
            elif link["batch_min"] < latest.get((link["a"], link["b"]), "b01"):
                reason = "superseded by a later batch for the same pair"
            elif link["harness"] and link["harness"] not in self.result.harness_applied:
                reason = f"harness {link['harness']} not applied"
            if reason:
                self.skipped.append({"id": link["id"], "reason": reason})
                self.checks["S1"]["skipped"] += 1
            else:
                links.append(link)
        return links

    def _link_failures(self, link: dict[str, Any], edge: Edge) -> list[dict[str, Any]]:
        failures: list[dict[str, Any]] = []

        def fail(kind: str, expected: Any, actual: Any) -> None:
            failures.append(
                {
                    "id": link["id"],
                    "kind": kind,
                    "ac": list(link["ac"]),
                    "expected": expected,
                    "actual": actual,
                    "edge": self._edge_ref(edge),
                }
            )

        confirmed_by_harness = (
            link["harness"] in self.result.harness_applied
            and link["id"] in self.confirm_targets.get(link["harness"], set())
            and edge.state == "CONFIRMED"
        )
        state_ok = edge.state == link["state"] or confirmed_by_harness
        if not state_ok:
            fail("state", link["state"], edge.state)
        if edge.band != link["band"]:
            fail("band", link["band"], edge.band)
        expected_gates = frozenset(gate_key(g) for g in link["gates_failed"])
        if edge.gates != expected_gates:
            fail("gates", sorted(expected_gates), sorted(edge.gates))
        if link["score"]["mode"] == "exact" and edge.score != Decimal(str(link["score"]["value"])):
            fail("score", link["score"]["value"], edge.raw_score)
        missing_kinds = sorted(set(link["evidence_kinds"]) - edge.kinds)
        if missing_kinds:
            fail("evidence_kinds", sorted(link["evidence_kinds"]), sorted(edge.kinds))
        cited = {ref_of(r) for r in link["cited_lines"]}
        end_cases = {self.entities[link["a"]]["case_id"], self.entities[link["b"]]["case_id"]}
        missing = sorted(cited - edge.sources)
        outside = sorted(r for r in edge.sources if r[0] not in end_cases)
        if missing or outside:
            fail("provenance", {"cited_lines_missing": missing}, {"outside_end_cases": outside})
        return failures

    @staticmethod
    def _deferrable(link: dict[str, Any], failure: dict[str, Any]) -> bool:
        """Is this failure only "not reached yet"? Anything above the expected link is not."""
        kind, actual = failure["kind"], failure["actual"]
        if kind == "state":
            return _rank(_STATE_RANK, actual) <= _rank(_STATE_RANK, link["state"])
        if kind == "band":
            return _rank(_BAND_RANK, actual) <= _rank(_BAND_RANK, link["band"])
        if kind == "score":
            return Decimal(str(actual)) <= Decimal(str(link["score"]["value"]))
        if kind == "provenance":
            return not actual["outside_end_cases"]
        return kind in ("gates", "evidence_kinds")

    def _defer(self, link: dict[str, Any], kinds: list[str], with_edge: bool) -> None:
        self.deferred.append(
            {
                "id": link["id"],
                "ac": list(link["ac"]),
                "status": "waiting" if kinds else "passing",
                "failures": sorted(set(kinds)),
            }
        )
        self.checks["S1"]["deferred"] += 1
        if with_edge:
            if link["score"]["mode"] == "exact":
                self.checks["S2"]["deferred"] += 1
            self.checks["S5"]["deferred"] += 1

    def check_links(self) -> None:
        for link in self._applicable_links():
            candidates = self._touching(link["a"], link["b"])
            self.link_edges.update(e.index for e in candidates)
            for edge in candidates:
                action = _HUMAN_ACTIONS.get(edge.state)
                pair = (link["a"], link["b"])
                if action and (
                    (action, link["id"]) in self.human_steps or (action, pair) in self.human_pairs
                ):
                    self.human_ok.add(edge.index)
            if link.get("trap"):
                for edge in candidates:
                    if edge.state == "AUTO":
                        self._forbidden_hit(link, edge, "AUTO", link["trap"])
                        break
            deferring = link["id"] in self.defer
            if not candidates:
                if deferring:
                    self._defer(link, ["missed"], with_edge=False)
                    continue
                self.missed.append(
                    {
                        "id": link["id"],
                        "ac": list(link["ac"]),
                        "a": link["a"],
                        "b": link["b"],
                        "reason": "no edge on the pair",
                    }
                )
                self.checks["S1"]["failed"] += 1
                continue
            failures = [f for edge in candidates for f in self._link_failures(link, edge)]
            edge = candidates[0]
            if link["score"]["mode"] != "exact":
                self.band_scores[link["id"]] = {
                    "expected": link["score"]["value"],
                    "actual": edge.raw_score,
                }
            if deferring and all(self._deferrable(link, f) for f in failures):
                self._defer(link, [f["kind"] for f in failures], with_edge=True)
                continue
            self.evaluated_acs.update(link["ac"])
            kinds = {f["kind"] for f in failures}
            self.wrong.extend(failures)
            self.checks["S1"]["failed" if kinds - {"score", "provenance"} else "passed"] += 1
            if link["score"]["mode"] == "exact":
                self.checks["S2"]["failed" if "score" in kinds else "passed"] += 1
            self.checks["S5"]["failed" if "provenance" in kinds else "passed"] += 1

    # --- S3 -----------------------------------------------------------------------------------

    def _forbidden_hit(self, row: dict[str, Any], edge: Edge, forbid: str, trap: str) -> None:
        self.forbidden.append(
            {
                "id": row["id"],
                "trap": trap,
                "ac": list(row["ac"]),
                "forbid": forbid,
                "state": edge.state,
                "edge": self._edge_ref(edge),
            }
        )

    def check_non_links(self) -> None:
        for row in self.gt["expected_non_links"]:
            hits = [
                edge
                for edge in self._touching(row["a"], row["b"])
                if row["forbid"] == "ANY_EDGE" or edge.state == "AUTO"
            ]
            self.evaluated_acs.update(row["ac"])
            for edge in hits:
                self._forbidden_hit(row, edge, row["forbid"], row["trap"])
            self.checks["S3"]["failed" if hits else "passed"] += 1

    # --- S4, and S5 on edges that are not expected links -------------------------------------

    def _integrity(self, edge: Edge) -> str | None:
        """The structural defect of an edge, if any (matching spec 1 and 6)."""
        if edge.a == edge.b:
            return "self_loop"
        if self._cases(edge.a) & self._cases(edge.b):
            return "same_case"
        if edge.state in ("AUTO", "SUGGESTED") and edge.band == "LOW":
            return "low_stored"
        if edge.state == "AUTO" and edge.band != "HIGH":
            return "auto_band"
        if edge.state in _HUMAN_ACTIONS and edge.index not in self.human_ok:
            return "human_state"
        return None

    def _cases(self, entity_id: str) -> set[str]:
        return {str(r["case_id"]) for r in self.result.entities[entity_id]["mentions"]}

    def check_entities(self) -> None:
        """An engine entity is one real thing in one case: no merged people, no case spread."""
        for entity_id, per_mention in self.per_mention.items():
            mapped = [m for m in per_mention if m]
            reasons: list[str] = []
            if len(self._cases(entity_id)) > 1:
                reasons.append("mentions span more than one case")
            if mapped and len(mapped) != len(per_mention):
                reasons.append("some mentions map to ground truth and some do not")
            closures = {self.index.closure({g}) for m in mapped for g in m}
            if len(closures) > 1:
                reasons.append("mentions map into more than one within-case group")
            if not reasons:
                self.checks["S4"]["passed"] += 1
                continue
            self.checks["S4"]["failed"] += 1
            self.wrong.append(
                {
                    "id": None,
                    "kind": "entity_conflict",
                    "ac": [],
                    "entity": entity_id,
                    "expected": "one real entity in one case, every mention mapped",
                    "actual": reasons,
                    "edge": None,
                }
            )

    def check_edges(self) -> None:
        seen: set[frozenset[str]] = set()
        for edge in self.result.edges:
            pair = frozenset({edge.a, edge.b})
            defect = "duplicate_edge" if pair in seen else self._integrity(edge)
            seen.add(pair)
            if defect:
                self.checks["S4"]["failed"] += 1
                self.wrong.append(
                    {
                        "id": None,
                        "kind": defect,
                        "ac": [],
                        "expected": _INTEGRITY_RULES[defect],
                        "actual": {"state": edge.state, "band": edge.band},
                        "edge": self._edge_ref(edge),
                    }
                )
                if defect == "self_loop":
                    continue
            if edge.state == "AUTO":
                left, right = self.mapped[edge.a], self.mapped[edge.b]
                inside = bool(left & right) or bool(self._groups(left) & self._groups(right))
                if inside:
                    self.checks["S4"]["passed"] += 1
                else:
                    self.checks["S4"]["failed"] += 1
                    reason = (
                        "an endpoint matches no ground-truth entity"
                        if not (left and right)
                        else None
                    )
                    self.wrong.append(
                        {
                            "id": None,
                            "kind": "closed_world",
                            "ac": [],
                            "expected": "no AUTO edge on a pair outside every cross_case group",
                            "actual": reason or "AUTO",
                            "edge": self._edge_ref(edge),
                        }
                    )
            if edge.index in self.link_edges:
                continue
            outside = sorted(r for r in edge.sources if r[0] not in self._end_cases(edge))
            if outside:
                self.checks["S5"]["failed"] += 1
                self.wrong.append(
                    {
                        "id": None,
                        "kind": "provenance",
                        "ac": [],
                        "expected": "every source inside the two end cases",
                        "actual": {"outside_end_cases": outside},
                        "edge": self._edge_ref(edge),
                    }
                )

    # --- S6 and report -------------------------------------------------------------------------

    def reported(self) -> dict[str, Any]:
        loaded = self.result.batches_loaded
        touched: set[int] = set()
        stray = 0
        for edge in self.result.edges:
            if edge.state not in ("AUTO", "SUGGESTED"):
                continue
            shared = self._groups(self.mapped[edge.a]) & self._groups(self.mapped[edge.b])
            touched |= shared
            if edge.state == "SUGGESTED" and not shared and edge.index not in self.link_edges:
                stray += 1
        noise = [
            position
            for position, group in enumerate(self.cross)
            if group["origin"] == "noise"
            and all(BATCH_ORDER[self.entities[m]["batch"]] <= loaded for m in group["members"])
        ]
        found = sum(1 for position in noise if position in touched)
        persons = sum(1 for e in self.result.entities.values() if e["type"] == "PERSON")
        return {
            "noise_recall": {
                "groups": len(noise),
                "found": found,
                "recall": found / len(noise) if noise else None,
            },
            "suggested_on_non_link_pairs": stray,
            "suggested_per_100_persons": round(stray * 100 / persons, 2) if persons else None,
            "oversized_block_count": self.result.oversized_block_count,
            "band_mode_scores": self.band_scores,
        }

    def per_ac(self) -> dict[str, dict[str, Any]]:
        acs = {
            ac
            for key in ("expected_links", "expected_non_links", "scenarios")
            for x in self.gt[key]
            for ac in x["ac"]
        }
        failing: dict[str, set[str]] = defaultdict(set)
        for item in [*self.missed, *self.wrong, *self.forbidden]:
            if item["id"] is not None:
                for ac in item["ac"]:
                    failing[ac].add(item["id"])
        waiting: dict[str, set[str]] = defaultdict(set)
        for item in self.deferred:
            for ac in item["ac"]:
                waiting[ac].add(item["id"])
        table: dict[str, dict[str, Any]] = {}
        for ac in sorted(acs):
            if failing[ac]:
                status = "fail"
            elif waiting[ac]:
                status = "deferred"
            elif ac in self.evaluated_acs:
                status = "pass"
            else:
                status = "not_evaluated"
            table[ac] = {
                "status": status,
                "failures": sorted(failing[ac]),
                "deferred": sorted(waiting[ac]),
            }
        return table


def score(
    gt: dict[str, Any], result_document: dict[str, Any], defer: Collection[str] = ()
) -> dict[str, Any]:
    """Score one engine result document against the ground truth; see the module docstring.

    `defer`: ids of expected links that may wait for a later tier. An unknown id is an input
    error: a misspelt id would silently defer nothing."""
    if gt.get("schema_version") != "data-kit-gt/1":
        raise ScoreInputError(
            f"ground truth schema_version must be 'data-kit-gt/1', got {gt.get('schema_version')!r}"
        )
    known = {link["id"] for link in gt["expected_links"]}
    unknown = sorted(set(defer) - known)
    if unknown:
        raise ScoreInputError(f"defer names no expected link: {', '.join(unknown)}")
    scorer = _Scorer(gt, parse_result(result_document), frozenset(defer))
    scorer.check_entities()
    scorer.check_links()
    scorer.check_non_links()
    scorer.check_edges()
    per_ac = scorer.per_ac()
    ok = not (scorer.missed or scorer.wrong or scorer.forbidden)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "ok": ok,
        "batches_loaded": result_document["batches_loaded"],
        "checks": scorer.checks,
        "per_ac": per_ac,
        "not_evaluated_acs": [ac for ac, row in per_ac.items() if row["status"] == "not_evaluated"],
        "missed_links": scorer.missed,
        "wrong_links": scorer.wrong,
        "forbidden_hits": scorer.forbidden,
        "deferred": scorer.deferred,
        "skipped": scorer.skipped,
        "reported": scorer.reported(),
    }


_HUMAN_ACTIONS = {"CONFIRMED": "CONFIRM", "REJECTED": "REJECT", "UNDONE": "UNDO"}

_STATE_RANK = {"SUGGESTED": 1, "AUTO": 2}
_BAND_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def _rank(table: dict[str, int], value: str) -> int:
    """Rank of a state or band; a value outside the table (a human state) ranks above all."""
    return table.get(value, len(table) + 1)


_INTEGRITY_RULES = {
    "human_state": "an edge is CONFIRMED, REJECTED or UNDONE only after an applied harness step",
    "self_loop": "an edge joins two different entities",
    "same_case": "an edge joins entities of two different cases",
    "duplicate_edge": "at most one edge per pair of entities",
    "low_stored": "a Low pair is never stored as AUTO or SUGGESTED",
    "auto_band": "an AUTO edge is band HIGH",
}

_CHECK_LABELS = {
    "S1": "S1 expected links",
    "S2": "S2 exact scores",
    "S3": "S3 non-links",
    "S4": "S4 closed world",
    "S5": "S5 provenance",
}


def format_report(report: dict[str, Any]) -> str:
    verdict = "PASS" if report["ok"] else "FAIL"
    batches = ",".join(report["batches_loaded"]) or "none"
    lines = [f"RESULT: {verdict}  (batches {batches})"]
    for key, label in _CHECK_LABELS.items():
        c = report["checks"][key]
        deferred = f", {c['deferred']} deferred" if c["deferred"] else ""
        lines.append(
            f"  {label}: {c['passed']} passed, {c['failed']} failed, {c['skipped']} skipped"
            f"{deferred}"
        )
    lines.append("Acceptance cases:")
    for ac, row in report["per_ac"].items():
        if row["status"] != "not_evaluated":
            detail = f"  ({', '.join(row['failures'])})" if row["failures"] else ""
            lines.append(f"  {ac}: {row['status']}{detail}")
    if report["not_evaluated_acs"]:
        lines.append(f"Not scored (scenario-only): {', '.join(report['not_evaluated_acs'])}")
    for title, key in (
        ("Missed links", "missed_links"),
        ("Wrong links", "wrong_links"),
        ("Forbidden hits", "forbidden_hits"),
    ):
        if report[key]:
            lines.append(f"{title}:")
            for item in report[key]:
                label = item["id"] or item.get("entity") or item["kind"]
                extra = item.get("trap") or item.get("kind", "")
                lines.append(f"  {label} {extra}: {_detail(item)}")
    if report["deferred"]:
        lines.append("Deferred (waiting for a later tier, not counted as passed):")
        for item in report["deferred"]:
            detail = ", ".join(item["failures"]) or "nothing fails now, remove from the defer list"
            lines.append(f"  {item['id']} {item['status']}: {detail}")
    if report["skipped"]:
        lines.append("Skipped:")
        lines.extend(f"  {item['id']}: {item['reason']}" for item in report["skipped"])
    rep = report["reported"]
    recall = rep["noise_recall"]
    lines.append(
        f"Reported (not gating): noise recall {recall['found']}/{recall['groups']}, "
        f"suggested on non-link pairs {rep['suggested_on_non_link_pairs']} "
        f"({rep['suggested_per_100_persons']} per 100 persons), "
        f"oversized blocks {rep['oversized_block_count']}"
    )
    return "\n".join(lines) + "\n"


def _detail(item: dict[str, Any]) -> str:
    if "reason" in item:
        return str(item["reason"])
    if "entity" in item:
        return "; ".join(item["actual"])
    if "forbid" in item:
        edge = item["edge"]
        return f"forbid {item['forbid']}, found {item['state']} edge {edge['a']} - {edge['b']}"
    return f"expected {item['expected']}, got {item['actual']}"
