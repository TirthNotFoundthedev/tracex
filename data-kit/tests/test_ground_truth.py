"""G-05, G-06, G-08, G-09, G-15, G-16 (pinned values): ground truth content and traceability."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from tests.conftest import KIT_ROOT
from tests.helpers import (
    accounts_in,
    all_files,
    normalize_phone,
    numbered_lines,
    phones_in,
    plates_in,
)

EXACT_ACS = {"AC-01", "AC-07", "AC-08", "AC-09", "AC-10", "AC-12", "AC-14", "AC-17", "AC-22"}
FIXTURES = [
    f"FX-{n:02d}" for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17, 19, 21, 22, 26)
]
SUPPORT = [f"SF-{n:02d}" for n in range(1, 9)]


def _file_path(root: Path, batch_hint: str | None, ref: dict[str, Any]) -> Path:
    for batch in ("b01", "b02"):
        path: Path = root / "batches" / batch / "cases" / str(ref["case_id"]) / str(ref["file"])
        if path.is_file():
            return path
    raise AssertionError(f"missing file for {ref}")


def test_ground_truth_validates_against_its_schema(gt: dict[str, Any]) -> None:
    schema = json.loads((KIT_ROOT / "schema" / "ground_truth.schema.json").read_text("utf-8"))
    Draft202012Validator(schema).validate(gt)
    assert gt["schema_version"] == "data-kit-gt/1"
    assert gt["ruleset_version"] == "engine-matching/1.1"
    assert gt["batches"] == ["b01", "b02"]
    assert gt["tier"] == "small"


def test_ground_truth_file_has_sorted_keys_and_two_space_indent(small_dir: Path) -> None:
    text = (small_dir / "ground_truth.json").read_text("utf-8")
    data = json.loads(text)
    assert text == json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def test_pairs_are_ordered_and_never_both_link_and_non_link(gt: dict[str, Any]) -> None:
    for link in gt["expected_links"]:
        assert link["a"] < link["b"], link["id"]
    link_pairs = {(link["a"], link["b"]) for link in gt["expected_links"]}
    for non in gt["expected_non_links"]:
        assert (min(non["a"], non["b"]), max(non["a"], non["b"])) not in link_pairs, non["id"]
    ids = [x["id"] for x in gt["expected_links"]]
    assert len(ids) == len(set(ids))


def test_exact_scores_only_for_acceptance_cases_the_scoring_rules_allow(
    gt: dict[str, Any],
) -> None:
    for link in gt["expected_links"]:
        if link["score"]["mode"] == "exact":
            assert link["ac"], link["id"]
            assert set(link["ac"]) <= EXACT_ACS, link["id"]


def test_every_acceptance_case_and_fixture_is_in_the_ground_truth(gt: dict[str, Any]) -> None:
    covered: set[str] = set()
    for key in ("expected_links", "expected_non_links", "scenarios"):
        for item in gt[key]:
            covered.update(item["ac"])
    assert covered >= {f"AC-{n:02d}" for n in range(1, 28)}
    gt_ids = {e["gt_id"] for e in gt["entities"]}
    for fixture in [*FIXTURES, *SUPPORT]:
        assert any(g.startswith(fixture + ".") for g in gt_ids), fixture
    assert any(s["id"].startswith("SF-09") for s in gt["scenarios"])


def test_traps_tr01_to_tr19_are_all_listed(gt: dict[str, Any]) -> None:
    traps = {n["trap"] for n in gt["expected_non_links"]}
    traps |= {x["trap"] for x in gt["expected_links"] if "trap" in x}
    assert traps >= {f"TR-{n:02d}" for n in range(1, 20)}
    for non in gt["expected_non_links"]:
        assert non["forbid"] in ("ANY_EDGE", "AUTO")


def test_attributions_include_the_first_p2_test(gt: dict[str, Any]) -> None:
    hits = [
        a
        for a in gt["attributions"]
        if a["source"] == {"case_id": "C-201", "file": "notes.txt", "line": 3}
    ]
    assert len(hits) == 1
    assert hits[0]["code"] == "OWNS"
    entities = {e["gt_id"]: e for e in gt["entities"]}
    assert entities[hits[0]["entity"]]["normalized"] == "irfan"
    assert entities[hits[0]["entity"]]["raw_text"] == "Irfan bhai"
    assert entities[hits[0]["identifier"]]["normalized"] == "9000014471"


def test_every_mention_exists_and_the_line_contains_the_raw_text(
    small_dir: Path, gt: dict[str, Any]
) -> None:
    cache: dict[tuple[str, str], list[str]] = {}
    for entity in gt["entities"]:
        assert entity["mentions"], entity["gt_id"]
        for ref in entity["mentions"]:
            key = (ref["case_id"], ref["file"])
            if key not in cache:
                path = _file_path(small_dir, None, ref)
                cache[key] = path.read_text("utf-8").split("\n")[:-1]
            lines = cache[key]
            assert 1 <= ref["line"] <= len(lines), (entity["gt_id"], ref)
            assert entity["raw_text"] in lines[ref["line"] - 1], (entity["gt_id"], ref)


def test_entity_batch_is_the_earliest_batch_of_its_mentions(
    small_dir: Path, gt: dict[str, Any]
) -> None:
    for entity in gt["entities"]:
        batches = set()
        for ref in entity["mentions"]:
            b02 = small_dir / "batches/b02/cases" / ref["case_id"] / ref["file"]
            batches.add("b02" if b02.is_file() else "b01")
        assert entity["batch"] == min(batches), entity["gt_id"]


def _identifier_occurrences(small_dir: Path) -> dict[tuple[str, str], set[tuple[str, str, int]]]:
    found: dict[tuple[str, str], set[tuple[str, str, int]]] = defaultdict(set)
    for _batch, case_id, name, path in all_files(small_dir):
        for line_no, line in numbered_lines(path):
            for phone in phones_in(line):
                found[("PHONE", normalize_phone(phone))].add((case_id, name, line_no))
            for account in accounts_in(line):
                found[("ACCOUNT", account)].add((case_id, name, line_no))
            for plate in plates_in(line):
                found[("VEHICLE", plate)].add((case_id, name, line_no))
    return found


def test_planted_identifiers_occur_only_at_lines_listed_in_ground_truth(
    small_dir: Path, gt: dict[str, Any]
) -> None:
    listed: dict[tuple[str, str], set[tuple[str, str, int]]] = defaultdict(set)
    for entity in gt["entities"]:
        for ref in entity["mentions"]:
            key = (entity["type"], entity["normalized"])
            listed[key].add((ref["case_id"], ref["file"], ref["line"]))
    planted = {
        (e["type"], e["normalized"])
        for e in gt["entities"]
        if e["type"] in ("PHONE", "ACCOUNT", "VEHICLE") and not e["gt_id"].startswith("NZ-")
    }
    found = _identifier_occurrences(small_dir)
    for key in planted:
        assert found.get(key, set()) == listed[key], key


def test_no_identifier_crosses_cases_unless_a_group_says_so(
    small_dir: Path, gt: dict[str, Any]
) -> None:
    group_of: dict[str, set[str]] = defaultdict(set)
    for group in gt["groups"]:
        for member in group["members"]:
            group_of[member].add(group["group_id"])
    by_value: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for entity in gt["entities"]:
        if entity["type"] in ("PHONE", "ACCOUNT", "VEHICLE"):
            by_value[(entity["type"], entity["normalized"])].append(entity)
    vetoed = {
        gt_id
        for n in gt["expected_non_links"]
        if n["trap"] == "TR-17"
        for gt_id in (n["a"], n["b"])
    }
    for key, cases in _identifier_occurrences(small_dir).items():
        case_ids = {c for c, _, _ in cases}
        if len(case_ids) < 2:
            continue
        if any(e["gt_id"] in vetoed for e in by_value[key]):
            continue
        entities = [e for e in by_value[key] if e["case_id"] in case_ids]
        assert {e["case_id"] for e in entities} == case_ids, key
        shared = set.intersection(*(group_of[e["gt_id"]] for e in entities))
        assert shared, key


def test_b2_digit_set_collisions_among_planted_phones_are_only_the_intended_ones(
    gt: dict[str, Any],
) -> None:
    by_key: dict[str, set[str]] = defaultdict(set)
    for entity in gt["entities"]:
        if entity["type"] == "PHONE" and entity["normalized"].startswith("9000"):
            value = entity["normalized"]
            by_key[value[:2] + "".join(sorted(value))].add(value)
    collisions = {frozenset(v) for v in by_key.values() if len(v) > 1}
    assert collisions == {
        frozenset({"9000081914", "9000081194"}),
        frozenset({"9000014471", "9000014741"}),
        frozenset({"9000091827", "9000097821"}),
        frozenset({"9000021203", "9000022310"}),
    }


def test_worked_scenario_shares_only_the_three_phones_between_c101_and_c201(
    small_dir: Path,
) -> None:
    by_case: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for key, cases in _identifier_occurrences(small_dir).items():
        for case_id, _, _ in cases:
            by_case[case_id].add(key)
    shared = by_case["C-101"] & by_case["C-201"]
    assert {v for _, v in shared} == {"9000014471", "9000021203", "9000028816"}


def test_quarantine_planted_name_tokens_never_appear_in_noise_names(gt: dict[str, Any]) -> None:
    def tokens(text: str) -> set[str]:
        return {t for t in re.split(r"[\s.,]+", text.lower()) if t}

    planted: set[str] = set()
    noise: set[str] = set()
    for entity in gt["entities"]:
        if entity["type"] not in ("PERSON", "ORG"):
            continue
        target = noise if entity["gt_id"].startswith("NZ-") else planted
        target |= tokens(entity["normalized"])
    assert not planted & noise
    excluded = (KIT_ROOT / "pools" / "excluded_tokens.txt").read_text("utf-8").split()
    assert {t.lower() for t in excluded} >= {t for t in planted if len(t) > 3}


def test_four_common_given_names_reach_twenty_person_entities(gt: dict[str, Any]) -> None:
    for name in ("rajesh", "sunil", "anil", "vijay"):
        count = sum(
            1
            for e in gt["entities"]
            if e["type"] == "PERSON" and name in e["normalized"].lower().split()
        )
        assert count >= 20, name


def _find(gt: dict[str, Any], ac: str, type_: str, state: str) -> list[dict[str, Any]]:
    return [
        link
        for link in gt["expected_links"]
        if ac in link["ac"] and link["type"] == type_ and link["state"] == state
    ]


@pytest.mark.parametrize(
    ("ac", "type_", "state", "band", "value", "mode", "gates"),
    [
        ("AC-01", "PHONE", "AUTO", "HIGH", 100, "exact", []),
        ("AC-01", "PERSON", "AUTO", "HIGH", 85.5, "exact", []),
        ("AC-02", "VEHICLE", "AUTO", "HIGH", 100, "band", []),
        ("AC-03", "PHONE", "SUGGESTED", "MEDIUM", 55, "band", ["G1"]),
        ("AC-05", "PERSON", "SUGGESTED", "MEDIUM", 48.2, "band", ["G1", "G2", "G3"]),
        ("AC-07", "PHONE", "AUTO", "HIGH", 100, "exact", []),
        ("AC-08", "PERSON", "SUGGESTED", "MEDIUM", 56.5, "exact", ["G1", "G2"]),
        ("AC-09", "ACCOUNT", "AUTO", "HIGH", 100, "exact", []),
        ("AC-10", "PERSON", "SUGGESTED", "MEDIUM", 45.0, "exact", ["G1", "G4"]),
        ("AC-11", "PERSON", "SUGGESTED", "HIGH", 90.0, "band", ["G2"]),
        ("AC-12", "PERSON", "AUTO", "HIGH", 99.0, "exact", []),
        (
            "AC-12",
            "PERSON",
            "SUGGESTED",
            "HIGH",
            93.0,
            "exact",
            [{"gate": "G6", "template_key": "match.gate.cluster_conflict"}],
        ),
        (
            "AC-13",
            "PERSON",
            "SUGGESTED",
            "HIGH",
            None,
            "band",
            [{"gate": "G6", "template_key": "match.gate.cluster_bridge"}],
        ),
        ("AC-14", "PERSON", "AUTO", "HIGH", 93.0, "exact", []),
        (
            "AC-14",
            "PERSON",
            "SUGGESTED",
            "HIGH",
            91.5,
            "exact",
            [{"gate": "G6", "template_key": "match.gate.cluster_same_case"}],
        ),
        ("AC-17", "PERSON", "SUGGESTED", "MEDIUM", 75.0, "exact", ["G1"]),
        ("AC-19", "VEHICLE", "SUGGESTED", "HIGH", 100, "band", ["G5"]),
        ("AC-21", "ORG", "SUGGESTED", "HIGH", None, "band", ["G7"]),
        ("AC-22", "PERSON", "AUTO", "HIGH", 99.0, "exact", []),
        (
            "AC-26",
            "ACCOUNT",
            "SUGGESTED",
            "HIGH",
            100,
            "band",
            [{"gate": "G6", "template_key": "match.gate.cluster_conflict"}],
        ),
    ],
)
def test_pinned_expected_links_match_the_spec_table(
    gt: dict[str, Any],
    ac: str,
    type_: str,
    state: str,
    band: str,
    value: float | None,
    mode: str,
    gates: list[Any],
) -> None:
    matches = [
        link
        for link in _find(gt, ac, type_, state)
        if link["band"] == band
        and link["score"]["mode"] == mode
        and (value is None or link["score"]["value"] == value)
        and link["gates_failed"] == gates
    ]
    assert matches, (ac, type_, state)


def test_ac01_person_link_cites_the_worked_scenario_lines(gt: dict[str, Any]) -> None:
    link = next(x for x in gt["expected_links"] if "AC-01" in x["ac"] and x["type"] == "PERSON")
    assert link["evidence_kinds"] == ["SHARED_PHONE", "PER_NAME_SIM", "PER_SHARED_NETWORK"]
    cited = {(c["case_id"], c["file"], c["line"]) for c in link["cited_lines"]}
    assert {
        ("C-101", "fir.txt", 12),
        ("C-101", "bank.csv", 4),
        ("C-101", "bank.csv", 7),
        ("C-201", "cdr.csv", 33),
        ("C-201", "cdr.csv", 41),
        ("C-201", "notes.txt", 3),
    } <= cited
    assert link["batch_min"] == "b01"


def test_scenarios_have_ordered_steps_with_expectations(gt: dict[str, Any]) -> None:
    by_ac = {ac for s in gt["scenarios"] for ac in s["ac"]}
    assert {"AC-15", "AC-16", "AC-18", "AC-20", "AC-23", "AC-24", "AC-25", "AC-27"} <= by_ac
    for scenario in gt["scenarios"]:
        assert scenario["steps"]
        for step in scenario["steps"]:
            assert set(step) == {"actor_role", "action", "target", "expect"}
