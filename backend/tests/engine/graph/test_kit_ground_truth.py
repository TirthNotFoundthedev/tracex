"""Case graphs built from real extractor output on the generated data kit (small tier).

The kit is generated into a temp directory by the kit's own CLI (`python -m datakit`, standard
library only), not copied into the repo: it is the same data the ground truth describes, so the
check cannot drift from a hand-copied fixture. Mapping engine entities onto ground-truth
entities follows data-kit section 8.1.
"""

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

from tracex_engine.extract import extract_case
from tracex_engine.graph import CaseGraph, EdgeType, EntityType, build_case_graph

KIT_DIR = Path(__file__).resolve().parents[4] / "data-kit"


@pytest.fixture(scope="module")
def kit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("kit_small")
    subprocess.run(  # noqa: S603 - fixed arguments, repository code
        [sys.executable, "-m", "datakit", "generate", "--tier", "small", "--out", str(out)],
        cwd=KIT_DIR,
        check=True,
        capture_output=True,
    )
    return out


@pytest.fixture(scope="module")
def truth(kit: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((kit / "ground_truth.json").read_text("utf-8"))
    return data


def case_files(kit: Path) -> dict[str, dict[str, str]]:
    """Every case's files, baseline and later batches together, keyed by case id."""
    cases: dict[str, dict[str, str]] = defaultdict(dict)
    for batch in sorted((kit / "batches").iterdir()):
        for case_dir in sorted((batch / "cases").iterdir()):
            for path in sorted(case_dir.iterdir()):
                cases[case_dir.name][path.name] = path.read_text("utf-8")
    return cases


@pytest.fixture(scope="module")
def graphs(kit: Path) -> dict[str, CaseGraph]:
    return {
        case_id: build_case_graph(extract_case(case_id, files))
        for case_id, files in case_files(kit).items()
    }


def engine_to_truth(graphs: dict[str, CaseGraph], truth: dict[str, Any]) -> dict[str, set[str]]:
    """Engine entity id -> ground-truth entity ids it maps to (data-kit 8.1)."""
    index: dict[tuple[str, str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for gt in truth["entities"]:
        for m in gt["mentions"]:
            index[(m["case_id"], m["file"], m["line"], gt["type"])].append(gt)
    mapping: dict[str, set[str]] = defaultdict(set)
    for graph in graphs.values():
        types = {e.entity_id: e.type for e in graph.entities}
        for mention in graph.mentions:
            type_ = types[mention.entity_id]
            for gt in index[(graph.case_id, mention.file, mention.line, type_)]:
                by_text = type_ in (EntityType.PERSON, EntityType.ORG)
                if (
                    (mention.raw_text == gt["raw_text"])
                    if by_text
                    else (mention.normalized == gt["normalized"])
                ):
                    mapping[mention.entity_id].add(gt["gt_id"])
    return mapping


def within_case_groups(truth: dict[str, Any]) -> dict[str, str]:
    """gt_id -> its within_case group id; entities in no group are their own."""
    groups = {g["group_id"]: g for g in truth["groups"] if g["scope"] == "within_case"}
    member_of = {m: gid for gid, g in groups.items() for m in g["members"]}
    return {gt["gt_id"]: member_of.get(gt["gt_id"], gt["gt_id"]) for gt in truth["entities"]}


def test_no_entity_joins_writings_the_ground_truth_keeps_apart(
    graphs: dict[str, CaseGraph], truth: dict[str, Any]
) -> None:
    group_of = within_case_groups(truth)
    merged = [
        (entity_id, sorted(gts))
        for entity_id, gts in engine_to_truth(graphs, truth).items()
        if len({group_of[g] for g in gts}) > 1
    ]

    assert merged == []


def test_every_planted_within_case_group_is_one_engine_entity(
    graphs: dict[str, CaseGraph], truth: dict[str, Any]
) -> None:
    mapping = engine_to_truth(graphs, truth)
    planted = [
        g for g in truth["groups"] if g["scope"] == "within_case" and g["origin"] == "planted"
    ]
    assert len(planted) >= 7

    for group in planted:
        engine_entities = {e for e, gts in mapping.items() if gts & set(group["members"])}
        assert len(engine_entities) == 1, group["group_id"]


def test_noise_within_case_groups_are_found_unless_only_transliteration_differs(
    graphs: dict[str, CaseGraph], truth: dict[str, Any]
) -> None:
    """A Devanagari FIR name and its Roman bank-holder writing can transliterate differently
    (`shrivastav` vs `srivastava`). Joining them needs fuzzy matching, which dedupe never does,
    so those groups may stay split; every other noise group must be one entity."""
    mapping = engine_to_truth(graphs, truth)
    entities = {e["gt_id"]: e for e in truth["entities"]}
    noise = [g for g in truth["groups"] if g["scope"] == "within_case" and g["origin"] == "noise"]

    split = [
        g for g in noise if len({e for e, gts in mapping.items() if gts & set(g["members"])}) != 1
    ]

    assert len(noise) >= 50
    for group in split:
        assert any(not entities[m]["raw_text"].isascii() for m in group["members"]), group[
            "group_id"
        ]
    assert len(split) <= len(noise) * 0.05


def test_worked_scenario_cases_carry_the_planted_lines(graphs: dict[str, CaseGraph]) -> None:
    c201 = graphs["C-201"]
    [owns] = [
        e for e in c201.edges if e.type is EdgeType.OWNS and (e.file, e.line) == ("notes.txt", 3)
    ]
    ends = {e.entity_id: e for e in c201.entities}
    assert ends[owns.source_id].normalized == "irfan"
    assert ends[owns.target_id].normalized == "9000014471"

    c101 = graphs["C-101"]
    irfan = [e for e in c101.entities if e.normalized == "mohammad irfan"]
    assert len(irfan) == 1
    lines = {(m.file, m.line) for m in c101.mentions if m.entity_id == irfan[0].entity_id}
    assert lines >= {("fir.txt", 12), ("bank.csv", 4), ("bank.csv", 7)}
    account = [e for e in c101.entities if e.normalized == "5010000019082"]
    assert len(account) == 1 and account[0].ifsc == "SYNB0000123"


def test_every_mention_is_kept_and_cited_on_all_kit_cases(
    kit: Path, graphs: dict[str, CaseGraph]
) -> None:
    for case_id, files in case_files(kit).items():
        extracted = extract_case(case_id, files)
        graph = graphs[case_id]
        expected = len(extracted.persons) + len(extracted.orgs) + len(extracted.identifiers)
        assert len(graph.mentions) == expected, case_id
        assert {m.entity_id for m in graph.mentions} == {e.entity_id for e in graph.entities}
        assert all(m.file in files and m.line >= 1 for m in graph.mentions), case_id
