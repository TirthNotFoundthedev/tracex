"""G-16: the stdlib reference scorer (spec section 8.3) against flawless and broken result sets."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from datakit.scorer import ScoreInputError, format_report, score
from tests.scorer_helpers import (
    add_edge,
    drop_edge_of_link,
    edge_of_link,
    eid,
    link_by_id,
    merge_mentions,
    perfect_result,
)

ALL_ACS = {f"AC-{n:02d}" for n in range(1, 28)}


@pytest.fixture(scope="module")
def perfect(gt: dict[str, Any]) -> dict[str, Any]:
    return perfect_result(gt)


@pytest.fixture
def broken(perfect: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(perfect)


def _failing_acs(report: dict[str, Any]) -> set[str]:
    return {ac for ac, row in report["per_ac"].items() if row["status"] == "fail"}


def _wrong_kinds(report: dict[str, Any]) -> list[str]:
    return sorted(item["kind"] for item in report["wrong_links"])


def _non_link(gt: dict[str, Any], forbid: str) -> dict[str, Any]:
    """A non-link of the given kind whose pair no other non-link row also names."""
    pairs = [frozenset({n["a"], n["b"]}) for n in gt["expected_non_links"]]
    found: dict[str, Any] = next(
        n
        for n in gt["expected_non_links"]
        if n["forbid"] == forbid and pairs.count(frozenset({n["a"], n["b"]})) == 1
    )
    return found


# --- flawless results pass everything -------------------------------------------------------


def test_a_result_derived_from_ground_truth_passes_every_check(
    gt: dict[str, Any], perfect: dict[str, Any]
) -> None:
    report = score(gt, perfect)
    assert report["ok"] is True
    assert report["missed_links"] == []
    assert report["wrong_links"] == []
    assert report["forbidden_hits"] == []
    assert [item["id"] for item in report["skipped"]] == ["EL-SF07-PER-B01"]
    assert _failing_acs(report) == set()


def test_every_acceptance_case_with_data_expectations_passes_and_the_rest_are_not_evaluated(
    gt: dict[str, Any], perfect: dict[str, Any]
) -> None:
    per_ac = score(gt, perfect)["per_ac"]
    assert set(per_ac) == ALL_ACS
    data_acs = {
        ac for key in ("expected_links", "expected_non_links") for x in gt[key] for ac in x["ac"]
    }
    for ac in ALL_ACS:
        assert per_ac[ac]["status"] == ("pass" if ac in data_acs else "not_evaluated"), ac
        assert per_ac[ac]["failures"] == []
    assert {"AC-01", "AC-04", "AC-06", "AC-12", "AC-26"} <= data_acs


def test_report_counts_every_check_it_ran(gt: dict[str, Any], perfect: dict[str, Any]) -> None:
    checks = score(gt, perfect)["checks"]
    assert checks["S1"] == {"passed": len(gt["expected_links"]) - 1, "failed": 0, "skipped": 1}
    assert checks["S3"] == {"passed": len(gt["expected_non_links"]), "failed": 0, "skipped": 0}
    assert checks["S4"]["failed"] == 0
    assert checks["S2"]["failed"] == 0
    assert checks["S5"]["failed"] == 0


def test_after_b01_only_links_from_b02_are_skipped_and_the_b01_suggestion_is_scored(
    gt: dict[str, Any],
) -> None:
    result = perfect_result(gt, batches=("b01",), harness=())
    report = score(gt, result)
    assert report["ok"] is True
    reasons = {item["id"]: item["reason"] for item in report["skipped"]}
    b02 = {link["id"] for link in gt["expected_links"] if link["batch_min"] == "b02"}
    assert b02 <= set(reasons)
    assert all("b02" in reasons[i] for i in b02)
    assert reasons["EL-FX13-Q1Q2"].startswith("harness HS-AC13")
    assert "EL-SF07-PER-B01" not in reasons


def test_after_b02_the_superseded_b01_suggestion_is_skipped(
    gt: dict[str, Any], perfect: dict[str, Any]
) -> None:
    report = score(gt, perfect)
    assert {item["id"]: item["reason"] for item in report["skipped"]} == {
        "EL-SF07-PER-B01": "superseded by a later batch for the same pair"
    }


def test_harness_link_is_scored_once_the_harness_is_declared_applied(
    gt: dict[str, Any], perfect: dict[str, Any]
) -> None:
    assert perfect["harness_applied"] == ["HS-AC13"]
    broken = copy.deepcopy(perfect)
    edge_of_link(broken, gt, "EL-FX13-Q1Q2")["band"] = "MEDIUM"
    report = score(gt, broken)
    assert _wrong_kinds(report) == ["band"]
    assert _failing_acs(report) == {"AC-13"}


def test_confirmed_state_satisfies_an_auto_link_whose_harness_confirms_it(
    gt: dict[str, Any], perfect: dict[str, Any]
) -> None:
    result = copy.deepcopy(perfect)
    edge_of_link(result, gt, "EL-FX13-Q1Q2")["state"] = "CONFIRMED"
    assert score(gt, result)["ok"] is True
    other = copy.deepcopy(perfect)
    edge_of_link(other, gt, "EL-FX01-PER")["state"] = "CONFIRMED"
    assert _wrong_kinds(score(gt, other)) == ["state"]


def test_confirmed_state_is_accepted_only_when_the_applied_harness_confirms_that_link(
    gt: dict[str, Any], perfect: dict[str, Any]
) -> None:
    changed = copy.deepcopy(gt)
    scenario = next(s for s in changed["scenarios"] if s["id"] == "HS-AC13")
    for step in scenario["steps"]:
        if step["action"] == "CONFIRM":
            step["action"] = "RERUN"
    result = copy.deepcopy(perfect)
    edge_of_link(result, gt, "EL-FX13-Q1Q2")["state"] = "CONFIRMED"
    assert _wrong_kinds(score(changed, result)) == ["state"]
    retargeted = copy.deepcopy(gt)
    for step in next(s for s in retargeted["scenarios"] if s["id"] == "HS-AC13")["steps"]:
        if step["action"] == "CONFIRM":
            step["target"] = "EL-FX13-Q3Q4"
    assert _wrong_kinds(score(retargeted, result)) == ["state"]


# --- deliberately broken results fail in exactly the right place ----------------------------


def test_missing_expected_link_is_reported_as_missed_for_its_acceptance_case_only(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    drop_edge_of_link(broken, gt, "EL-FX01-PER")
    report = score(gt, broken)
    assert report["ok"] is False
    assert [m["id"] for m in report["missed_links"]] == ["EL-FX01-PER"]
    assert report["wrong_links"] == []
    assert report["forbidden_hits"] == []
    assert _failing_acs(report) == {"AC-01"}
    assert report["per_ac"]["AC-01"]["failures"] == ["EL-FX01-PER"]
    assert report["checks"]["S1"]["failed"] == 1


def test_auto_edge_on_a_must_not_auto_trap_is_a_forbidden_hit_and_a_closed_world_violation(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    trap = _non_link(gt, "AUTO")
    add_edge(broken, trap["a"], trap["b"], "AUTO")
    report = score(gt, broken)
    assert report["ok"] is False
    assert [(h["id"], h["trap"], h["forbid"]) for h in report["forbidden_hits"]] == [
        (trap["id"], trap["trap"], "AUTO")
    ]
    assert report["missed_links"] == []
    assert _wrong_kinds(report) == ["closed_world"]
    assert report["wrong_links"][0]["ac"] == []
    assert _failing_acs(report) == set(trap["ac"])
    assert report["checks"]["S3"]["failed"] == 1
    assert report["checks"]["S4"]["failed"] == 1


def test_suggested_edge_on_a_must_not_auto_trap_is_allowed(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    trap = _non_link(gt, "AUTO")
    add_edge(broken, trap["a"], trap["b"], "SUGGESTED", band="MEDIUM", score=60)
    report = score(gt, broken)
    assert report["ok"] is True
    assert report["forbidden_hits"] == []


@pytest.mark.parametrize("state", ["AUTO", "SUGGESTED", "CONFIRMED", "REJECTED"])
def test_any_stored_edge_on_an_any_edge_non_link_is_a_forbidden_hit(
    gt: dict[str, Any], broken: dict[str, Any], state: str
) -> None:
    trap = _non_link(gt, "ANY_EDGE")
    add_edge(broken, trap["b"], trap["a"], state, band="MEDIUM", score=60)
    report = score(gt, broken)
    assert report["ok"] is False
    assert [h["id"] for h in report["forbidden_hits"]] == [trap["id"]]
    assert report["missed_links"] == []
    assert _failing_acs(report) == set(trap["ac"])
    assert _wrong_kinds(report) == (["closed_world"] if state == "AUTO" else [])


def test_wrong_band_fails_only_that_link(gt: dict[str, Any], broken: dict[str, Any]) -> None:
    edge_of_link(broken, gt, "EL-FX01-PER")["band"] = "MEDIUM"
    report = score(gt, broken)
    assert report["ok"] is False
    assert [(w["id"], w["kind"], w["expected"], w["actual"]) for w in report["wrong_links"]] == [
        ("EL-FX01-PER", "band", "HIGH", "MEDIUM")
    ]
    assert report["missed_links"] == []
    assert report["forbidden_hits"] == []
    assert _failing_acs(report) == {"AC-01"}


def test_wrong_state_fails_only_that_link(gt: dict[str, Any], broken: dict[str, Any]) -> None:
    edge_of_link(broken, gt, "EL-FX02-0-1")["state"] = "SUGGESTED"
    report = score(gt, broken)
    assert [(w["id"], w["kind"]) for w in report["wrong_links"]] == [("EL-FX02-0-1", "state")]
    assert _failing_acs(report) == {"AC-02"}


def test_gates_failed_compare_as_a_set(gt: dict[str, Any], broken: dict[str, Any]) -> None:
    link = link_by_id(gt, "EL-FX05-PER")
    assert link["gates_failed"] == ["G1", "G2", "G3"]
    edge = edge_of_link(broken, gt, "EL-FX05-PER")
    edge["gates_failed"] = ["G3", "G1", "G2"]
    assert score(gt, broken)["ok"] is True
    edge["gates_failed"] = ["G1", "G2"]
    report = score(gt, broken)
    assert [(w["id"], w["kind"]) for w in report["wrong_links"]] == [("EL-FX05-PER", "gates")]
    assert _failing_acs(report) == {"AC-05"}


def test_g6_gate_needs_its_template_key(gt: dict[str, Any], broken: dict[str, Any]) -> None:
    link = next(
        x
        for x in gt["expected_links"]
        if x["gates_failed"] and isinstance(x["gates_failed"][0], dict)
    )
    edge = edge_of_link(broken, gt, link["id"])
    edge["gates_failed"] = ["G6"]
    assert [(w["id"], w["kind"]) for w in score(gt, broken)["wrong_links"]] == [
        (link["id"], "gates")
    ]
    edge["gates_failed"] = [{"gate": "G6", "template_key": "match.gate.other"}]
    assert [(w["id"], w["kind"]) for w in score(gt, broken)["wrong_links"]] == [
        (link["id"], "gates")
    ]


def test_exact_score_is_compared_by_decimal_equality(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    edge = edge_of_link(broken, gt, "EL-FX01-PER")
    edge["score"] = "85.50"
    assert score(gt, broken)["ok"] is True
    edge["score"] = 85.4
    report = score(gt, broken)
    assert [(w["id"], w["kind"]) for w in report["wrong_links"]] == [("EL-FX01-PER", "score")]
    assert report["checks"]["S2"]["failed"] == 1
    assert _failing_acs(report) == {"AC-01"}


def test_band_mode_score_is_recorded_not_gating(gt: dict[str, Any], broken: dict[str, Any]) -> None:
    link = next(x for x in gt["expected_links"] if x["score"]["mode"] == "band" and x["ac"])
    edge_of_link(broken, gt, link["id"])["score"] = 12.5
    report = score(gt, broken)
    assert report["ok"] is True
    assert report["reported"]["band_mode_scores"][link["id"]] == {
        "expected": link["score"]["value"],
        "actual": 12.5,
    }


def test_cited_line_missing_from_the_edge_sources_fails_provenance(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    edge = edge_of_link(broken, gt, "EL-FX01-PER")
    edge["sources"] = edge["sources"][1:]
    report = score(gt, broken)
    assert [(w["id"], w["kind"]) for w in report["wrong_links"]] == [("EL-FX01-PER", "provenance")]
    assert _failing_acs(report) == {"AC-01"}
    assert report["checks"]["S5"]["failed"] == 1


def test_source_outside_the_two_end_cases_fails_provenance(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    edge = edge_of_link(broken, gt, "EL-FX01-PER")
    edge["sources"].append({"case_id": "C-301", "file": "notes.txt", "line": 3})
    report = score(gt, broken)
    assert [(w["id"], w["kind"]) for w in report["wrong_links"]] == [("EL-FX01-PER", "provenance")]


def test_auto_edge_on_a_suggested_link_that_carries_a_trap_is_a_forbidden_hit(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    link = next(x for x in gt["expected_links"] if x.get("trap") == "TR-05")
    edge_of_link(broken, gt, link["id"])["state"] = "AUTO"
    report = score(gt, broken)
    assert [(h["id"], h["trap"]) for h in report["forbidden_hits"]] == [(link["id"], "TR-05")]
    assert [(w["id"], w["kind"]) for w in report["wrong_links"] if w["id"]] == [
        (link["id"], "state")
    ]
    assert _wrong_kinds(report) == ["closed_world", "state"]
    assert _failing_acs(report) == set(link["ac"])


def test_auto_edge_between_unrelated_entities_breaks_the_closed_world(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    noise = [
        e["gt_id"] for e in gt["entities"] if e["gt_id"].startswith("NZ-") and e["type"] == "PHONE"
    ]
    add_edge(broken, noise[0], noise[-1], "AUTO")
    report = score(gt, broken)
    assert report["ok"] is False
    assert _wrong_kinds(report) == ["closed_world"]
    assert report["missed_links"] == [] and report["forbidden_hits"] == []
    assert _failing_acs(report) == set()
    assert report["checks"]["S4"]["failed"] == 1


def test_auto_edge_on_an_engine_entity_with_no_ground_truth_counterpart_breaks_the_closed_world(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    some = next(e["gt_id"] for e in gt["entities"] if e["type"] == "PHONE")
    broken["entities"].append(
        {
            "id": "ghost",
            "type": "PHONE",
            "normalized": "9999999999",
            "mentions": [{"case_id": "C-999", "file": "fir.txt", "line": 99}],
        }
    )
    broken["edges"].append(
        {
            "a": "ghost",
            "b": eid(some),
            "state": "AUTO",
            "band": "HIGH",
            "score": 100,
            "gates_failed": [],
            "evidence_kinds": [],
            "sources": [],
        }
    )
    report = score(gt, broken)
    assert _wrong_kinds(report) == ["closed_world"]


def test_second_edge_on_the_same_pair_does_not_hide_a_correct_one_it_fails_the_link(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    link = link_by_id(gt, "EL-FX01-PER")
    wrong = add_edge(broken, link["a"], link["b"], "SUGGESTED", band="MEDIUM", score=50)
    wrong["sources"] = []
    report = score(gt, broken)
    assert report["ok"] is False
    assert {w["id"] for w in report["wrong_links"] if w["kind"] != "duplicate_edge"} == {
        "EL-FX01-PER"
    }
    assert _failing_acs(report) == {"AC-01"}


def test_expected_link_is_satisfied_by_an_engine_entity_matching_any_group_member(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    link = link_by_id(gt, "EL-FX01-PER")
    member = "FX-01.PER.IRFAN_A_BANK"
    assert member != link["a"] and member != link["b"]
    broken["entities"] = [e for e in broken["entities"] if e["id"] != eid(link["a"])]
    edge_of_link_pair = next(e for e in broken["edges"] if eid(link["a"]) in (e["a"], e["b"]))
    key = "a" if edge_of_link_pair["a"] == eid(link["a"]) else "b"
    edge_of_link_pair[key] = eid(member)
    assert score(gt, broken)["ok"] is True


def test_engine_edge_endpoint_order_does_not_matter(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    edge = edge_of_link(broken, gt, "EL-FX01-PER")
    edge["a"], edge["b"] = edge["b"], edge["a"]
    assert score(gt, broken)["ok"] is True


# --- reported, not gating (S6) --------------------------------------------------------------


def test_noise_recall_is_full_for_a_flawless_result_and_zero_without_noise_edges(
    gt: dict[str, Any], perfect: dict[str, Any]
) -> None:
    groups = sum(1 for g in gt["groups"] if g["scope"] == "cross_case" and g["origin"] == "noise")
    assert score(gt, perfect)["reported"]["noise_recall"] == {
        "groups": groups,
        "found": groups,
        "recall": 1.0,
    }
    trimmed = copy.deepcopy(perfect)
    planted = {e["gt_id"] for e in gt["entities"] if not e["gt_id"].startswith("NZ-")}
    trimmed["edges"] = [e for e in trimmed["edges"] if e["a"].removeprefix("E|") in planted]
    report = score(gt, trimmed)
    assert report["ok"] is True
    assert report["reported"]["noise_recall"]["found"] == 0


def test_suggested_edges_on_non_link_pairs_are_counted_per_hundred_persons(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    persons = [
        e["gt_id"] for e in gt["entities"] if e["gt_id"].startswith("NZ-") and e["type"] == "PERSON"
    ]
    add_edge(broken, persons[0], persons[-1], "SUGGESTED", band="MEDIUM", score=60)
    report = score(gt, broken)
    assert report["ok"] is True
    total_persons = sum(1 for e in broken["entities"] if e["type"] == "PERSON")
    assert report["reported"]["suggested_on_non_link_pairs"] == 1
    assert report["reported"]["suggested_per_100_persons"] == round(100 / total_persons, 2)


def test_oversized_block_count_is_passed_through(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    broken["stats"] = {"oversized_block_count": 7}
    assert score(gt, broken)["reported"]["oversized_block_count"] == 7
    del broken["stats"]
    assert score(gt, broken)["reported"]["oversized_block_count"] is None


# --- input validation and text report -------------------------------------------------------


def test_unknown_schema_version_is_rejected(gt: dict[str, Any], broken: dict[str, Any]) -> None:
    broken["schema_version"] = "engine-result/2"
    with pytest.raises(ScoreInputError, match="schema_version"):
        score(gt, broken)


def test_edge_naming_an_unknown_entity_is_rejected(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    broken["edges"][0]["a"] = "nobody"
    with pytest.raises(ScoreInputError, match="nobody"):
        score(gt, broken)


def test_unknown_state_is_rejected(gt: dict[str, Any], broken: dict[str, Any]) -> None:
    broken["edges"][0]["state"] = "MAYBE"
    with pytest.raises(ScoreInputError, match="state"):
        score(gt, broken)


def test_text_report_names_the_failures_and_the_verdict(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    drop_edge_of_link(broken, gt, "EL-FX01-PER")
    text = format_report(score(gt, broken))
    assert "FAIL" in text
    assert "EL-FX01-PER" in text
    assert "AC-01" in text
    clean = format_report(score(gt, perfect_result(gt)))
    assert "PASS" in clean and "FAIL" not in clean


# --- integrity: a clearly wrong engine must not pass ----------------------------------------


def _entity_id(gt: dict[str, Any], raw_text: str, case_id: str) -> str:
    found: str = next(
        e["gt_id"]
        for e in gt["entities"]
        if e["type"] == "PERSON" and e["raw_text"] == raw_text and e["case_id"] == case_id
    )
    return found


def _only_integrity_failure(report: dict[str, Any], kind: str) -> None:
    assert report["ok"] is False
    assert _wrong_kinds(report) == [kind]
    assert report["missed_links"] == [] and report["forbidden_hits"] == []
    assert _failing_acs(report) == set()


def test_two_people_merged_into_one_engine_entity_fail_as_an_entity_conflict(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    witness = _entity_id(gt, "Sunil Pandey", "C-101")
    merge_mentions(broken, gt, "FX-01.PER.IRFAN_A", witness)
    report = score(gt, broken)
    _only_integrity_failure(report, "entity_conflict")
    assert report["wrong_links"][0]["entity"] == eid("FX-01.PER.IRFAN_A")
    assert report["checks"]["S4"]["failed"] == 1


def test_the_family_phone_merge_of_ramesh_and_sunita_fails_as_an_entity_conflict(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    merge_mentions(broken, gt, "FX-07.PER.RAMESH", "FX-07.PER.SUNITA")
    _only_integrity_failure(score(gt, broken), "entity_conflict")


def test_one_engine_entity_with_mentions_in_two_cases_fails_as_an_entity_conflict(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    entity = next(e for e in broken["entities"] if e["id"] == eid("FX-02.VEH.A"))
    entity["mentions"].append({"case_id": "C-104", "file": "notes.txt", "line": 3, "raw_text": "x"})
    report = score(gt, broken)
    assert report["ok"] is False
    assert "entity_conflict" in _wrong_kinds(report)


def test_an_entity_whose_mentions_partly_map_and_partly_do_not_fails(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    entity = next(e for e in broken["entities"] if e["id"] == eid("FX-01.PER.IRFAN_B"))
    entity["mentions"].append({"case_id": "C-201", "file": "fir.txt", "line": 99, "raw_text": "Z"})
    _only_integrity_failure(score(gt, broken), "entity_conflict")


def test_an_engine_entity_that_maps_to_nothing_and_has_no_edge_is_not_a_failure(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    broken["entities"].append(
        {
            "id": "stray",
            "type": "PHONE",
            "normalized": "9999999999",
            "mentions": [{"case_id": "C-999", "file": "fir.txt", "line": 1}],
        }
    )
    assert score(gt, broken)["ok"] is True


def test_an_identical_second_edge_between_the_same_two_engine_entities_fails(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    edge = edge_of_link(broken, gt, "EL-FX01-PER")
    broken["edges"].append({**edge, "a": edge["b"], "b": edge["a"]})
    _only_integrity_failure(score(gt, broken), "duplicate_edge")


def test_a_different_second_edge_on_the_ac01_person_pair_fails_the_link_too(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    link = link_by_id(gt, "EL-FX01-PER")
    extra = add_edge(broken, link["a"], link["b"], "SUGGESTED", band="MEDIUM", score=50)
    extra["gates_failed"] = ["G2"]
    report = score(gt, broken)
    assert report["ok"] is False
    assert "duplicate_edge" in _wrong_kinds(report)
    assert _failing_acs(report) == {"AC-01"}


def test_an_extra_edge_from_an_unmerged_duplicate_entity_in_one_case_fails_the_link(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    add_edge(broken, "FX-01.PER.IRFAN_A_BANK", "FX-01.PER.IRFAN_B", "SUGGESTED", "MEDIUM", 50)
    report = score(gt, broken)
    assert report["ok"] is False
    assert {w["id"] for w in report["wrong_links"]} == {"EL-FX01-PER"}
    assert {"state", "band"} <= set(_wrong_kinds(report))
    assert _failing_acs(report) == {"AC-01"}


def test_the_same_extra_edge_passes_when_it_equals_the_expected_link(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    template = edge_of_link(broken, gt, "EL-FX01-PER")
    broken["edges"].append({**template, "a": eid("FX-01.PER.IRFAN_A_BANK")})
    assert score(gt, broken)["ok"] is True


def test_a_stored_edge_with_band_low_fails_even_between_unrelated_entities(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    persons = [e for e in gt["entities"] if e["gt_id"].startswith("NZ-") and e["type"] == "PERSON"]
    first = persons[0]
    other = next(p for p in persons if p["case_id"] != first["case_id"])
    add_edge(broken, first["gt_id"], other["gt_id"], "SUGGESTED", band="LOW", score=20)
    _only_integrity_failure(score(gt, broken), "low_stored")


def test_an_auto_edge_must_be_band_high(gt: dict[str, Any], broken: dict[str, Any]) -> None:
    noise = next(
        e
        for e in broken["edges"]
        if e["a"].startswith("E|NZ-") and e["state"] == "AUTO" and e["band"] == "HIGH"
    )
    noise["band"] = "MEDIUM"
    _only_integrity_failure(score(gt, broken), "auto_band")


def test_an_auto_edge_inside_one_case_fails(gt: dict[str, Any], broken: dict[str, Any]) -> None:
    add_edge(broken, "FX-01.PER.IRFAN_A", "FX-01.PER.IRFAN_A_BANK", "AUTO")
    _only_integrity_failure(score(gt, broken), "same_case")


def test_a_self_loop_fails(gt: dict[str, Any], broken: dict[str, Any]) -> None:
    add_edge(broken, "FX-01.PER.IRFAN_A", "FX-01.PER.IRFAN_A", "AUTO")
    _only_integrity_failure(score(gt, broken), "self_loop")


def test_edge_evidence_kinds_must_include_the_expected_kinds(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    link = link_by_id(gt, "EL-FX01-PER")
    edge = edge_of_link(broken, gt, "EL-FX01-PER")
    edge["evidence_kinds"] = ["PER_NAME_SIM"]
    report = score(gt, broken)
    assert [(w["id"], w["kind"]) for w in report["wrong_links"]] == [
        ("EL-FX01-PER", "evidence_kinds")
    ]
    assert _failing_acs(report) == {"AC-01"}
    edge["evidence_kinds"] = [*reversed(link["evidence_kinds"]), "EXTRA_KIND"]
    assert score(gt, broken)["ok"] is True


def test_batches_loaded_must_be_a_prefix_of_the_batch_order(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    for bad in (["b02"], [], ["b02", "b01"]):
        broken["batches_loaded"] = bad
        with pytest.raises(ScoreInputError, match="batches_loaded"):
            score(gt, broken)


def test_withdrawn_is_not_a_state_an_engine_can_report(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    broken["edges"][0]["state"] = "WITHDRAWN"
    with pytest.raises(ScoreInputError, match="state"):
        score(gt, broken)


def test_edge_without_evidence_kinds_is_rejected(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    del broken["edges"][0]["evidence_kinds"]
    with pytest.raises(ScoreInputError, match="evidence_kinds"):
        score(gt, broken)


def test_person_mention_without_raw_text_is_rejected(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    person = next(e for e in broken["entities"] if e["type"] == "PERSON")
    del person["mentions"][0]["raw_text"]
    with pytest.raises(ScoreInputError, match="raw_text"):
        score(gt, broken)


def test_scenario_only_acceptance_cases_are_listed_apart_from_passes(
    gt: dict[str, Any], perfect: dict[str, Any]
) -> None:
    report = score(gt, perfect)
    assert report["not_evaluated_acs"] == [f"AC-{n}" for n in (16, 18, 20, 23, 24, 25, 27)]
    assert not set(report["not_evaluated_acs"]) & {
        ac for ac, row in report["per_ac"].items() if row["status"] == "pass"
    }
    assert "Not scored (scenario-only): AC-16, AC-18" in format_report(report)
