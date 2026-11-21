"""Deferring expected links that wait for a later engine tier (`score(..., defer=)`, `--defer`).

A deferred link never counts as passed; zero-tolerance checks (non-links, closed world, trap
hits) and anything above the expected link are never deferrable.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from datakit.cli import main
from datakit.scorer import ScoreInputError, format_report, score
from tests.scorer_helpers import (
    add_edge,
    drop_edge_of_link,
    edge_of_link,
    link_by_id,
    perfect_result,
)

WAITING = "EL-FX01-PER"  # AC-01 person link: AUTO HIGH 85.5, exact


@pytest.fixture(scope="module")
def perfect(gt: dict[str, Any]) -> dict[str, Any]:
    return perfect_result(gt)


@pytest.fixture
def broken(perfect: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(perfect)


def lower(edge: dict[str, Any]) -> None:
    """The edge as an engine without Tier 2 stores it: SUGGESTED, Medium, a lower score."""
    edge.update(state="SUGGESTED", band="MEDIUM", score=63.0, gates_failed=["G1"])
    edge["evidence_kinds"] = [k for k in edge["evidence_kinds"] if k != "PER_NAME_SIM"]


def test_a_link_with_no_edge_is_deferred_and_the_result_is_ok(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    drop_edge_of_link(broken, gt, WAITING)

    plain = score(gt, broken)
    report = score(gt, broken, defer=[WAITING])

    assert plain["ok"] is False
    assert report["ok"] is True
    assert report["missed_links"] == [] and report["wrong_links"] == []
    assert report["deferred"] == [
        {"id": WAITING, "ac": ["AC-01"], "status": "waiting", "failures": ["missed"]}
    ]
    assert report["checks"]["S1"]["deferred"] == 1
    assert report["checks"]["S1"]["passed"] == plain["checks"]["S1"]["passed"]
    assert report["per_ac"]["AC-01"] == {
        "status": "deferred",
        "failures": [],
        "deferred": [WAITING],
    }


def test_a_stored_link_below_expectation_is_deferred_with_its_failure_kinds(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    lower(edge_of_link(broken, gt, WAITING))

    report = score(gt, broken, defer=[WAITING])

    assert report["ok"] is True
    [item] = report["deferred"]
    assert item["status"] == "waiting"
    assert item["failures"] == ["band", "evidence_kinds", "gates", "score", "state"]
    assert report["checks"]["S2"]["deferred"] == 1 and report["checks"]["S5"]["deferred"] == 1


def test_a_deferred_link_that_passes_is_reported_passing_never_as_passed(
    gt: dict[str, Any], perfect: dict[str, Any]
) -> None:
    plain = score(gt, perfect)

    report = score(gt, perfect, defer=[WAITING])

    assert report["ok"] is True
    assert report["deferred"] == [
        {"id": WAITING, "ac": ["AC-01"], "status": "passing", "failures": []}
    ]
    assert report["checks"]["S1"]["passed"] == plain["checks"]["S1"]["passed"] - 1
    assert report["per_ac"]["AC-01"]["status"] == "deferred"


def test_a_link_not_named_is_still_judged(gt: dict[str, Any], broken: dict[str, Any]) -> None:
    drop_edge_of_link(broken, gt, WAITING)
    drop_edge_of_link(broken, gt, "EL-FX22-PER")

    report = score(gt, broken, defer=[WAITING])

    assert report["ok"] is False
    assert [m["id"] for m in report["missed_links"]] == ["EL-FX22-PER"]


@pytest.mark.parametrize(
    ("change", "kind"),
    [
        (lambda e: e.update(state="AUTO", band="HIGH"), "state"),
        (lambda e: e.update(score=99.0), "score"),
    ],
    ids=["state-above-expected", "score-above-expected"],
)
def test_a_deferred_link_stored_above_its_expectation_still_fails(
    gt: dict[str, Any], broken: dict[str, Any], change: Any, kind: str
) -> None:
    link = link_by_id(gt, "EL-FX17-PER")  # SUGGESTED MEDIUM 75.0 exact
    edge = edge_of_link(broken, gt, link["id"])
    change(edge)

    report = score(gt, broken, defer=[link["id"]])

    assert report["ok"] is False
    assert kind in {w["kind"] for w in report["wrong_links"]}
    assert report["deferred"] == []


def test_a_deferred_link_above_its_expected_band_still_fails(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    edge = edge_of_link(broken, gt, "EL-FX17-PER")
    edge["band"] = "HIGH"

    report = score(gt, broken, defer=["EL-FX17-PER"])

    assert report["ok"] is False
    assert "band" in {w["kind"] for w in report["wrong_links"]}


def test_a_deferred_link_citing_a_line_outside_its_cases_still_fails(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    lower(edge_of_link(broken, gt, WAITING))
    edge_of_link(broken, gt, WAITING)["sources"].append(
        {"case_id": "C-999", "file": "fir.txt", "line": 1}
    )

    report = score(gt, broken, defer=[WAITING])

    assert report["ok"] is False
    assert any(w["kind"] == "provenance" for w in report["wrong_links"])


def test_deferral_never_reaches_a_non_link(gt: dict[str, Any], broken: dict[str, Any]) -> None:
    row = next(n for n in gt["expected_non_links"] if n["forbid"] == "AUTO")
    add_edge(broken, row["a"], row["b"], "AUTO")

    report = score(gt, broken, defer=[link["id"] for link in gt["expected_links"]])

    assert report["ok"] is False
    assert report["forbidden_hits"] and report["checks"]["S3"]["failed"] >= 1


def test_deferral_never_reaches_closed_world_integrity(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    link = link_by_id(gt, WAITING)
    edge = edge_of_link(broken, gt, WAITING)
    broken["edges"].append(copy.deepcopy(edge))  # a second edge on one pair: S4 duplicate

    report = score(gt, broken, defer=[link["id"]])

    assert report["ok"] is False
    assert report["checks"]["S4"]["failed"] >= 1


def test_deferring_a_trap_link_that_is_stored_as_auto_still_hits_the_trap(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    link = next(x for x in gt["expected_links"] if x.get("trap") and x["state"] != "AUTO")
    edge = edge_of_link(broken, gt, link["id"])
    edge.update(state="AUTO", band="HIGH", gates_failed=[])

    report = score(gt, broken, defer=[link["id"]])

    assert report["ok"] is False
    assert [h["id"] for h in report["forbidden_hits"]] == [link["id"]]


def test_an_unknown_link_id_is_an_input_error(gt: dict[str, Any], perfect: dict[str, Any]) -> None:
    with pytest.raises(ScoreInputError, match="EL-NOPE"):
        score(gt, perfect, defer=["EL-NOPE"])


def test_the_text_report_lists_deferred_links_apart_from_the_checks(
    gt: dict[str, Any], broken: dict[str, Any]
) -> None:
    lower(edge_of_link(broken, gt, WAITING))

    text = format_report(score(gt, broken, defer=[WAITING]))

    assert text.startswith("RESULT: PASS")
    assert "1 deferred" in text
    assert "Deferred (waiting for a later tier, not counted as passed):" in text
    assert f"  {WAITING} waiting: band, evidence_kinds, gates, score, state" in text


@pytest.fixture
def cli_files(
    tmp_path: Path, small_dir: Path, gt: dict[str, Any], broken: dict[str, Any]
) -> dict[str, Path]:
    drop_edge_of_link(broken, gt, WAITING)
    result = tmp_path / "waiting.json"
    result.write_text(json.dumps(broken), encoding="utf-8")
    return {"gt": small_dir / "ground_truth.json", "result": result}


def run_cli(files: dict[str, Path], *extra: str) -> int:
    return main(
        ["score", "--ground-truth", str(files["gt"]), "--result", str(files["result"]), *extra]
    )


def test_cli_exits_1_without_defer_and_0_with_it(cli_files: dict[str, Path]) -> None:
    assert run_cli(cli_files) == 1
    assert run_cli(cli_files, "--defer", WAITING) == 0
    assert run_cli(cli_files, "--defer", f"EL-FX22-PER,{WAITING}") == 0


def test_cli_reads_a_defer_file_of_ids_or_a_keyed_object(
    cli_files: dict[str, Path], tmp_path: Path
) -> None:
    as_list = tmp_path / "list.json"
    as_list.write_text(json.dumps([WAITING]), encoding="utf-8")
    as_object = tmp_path / "object.json"
    as_object.write_text(json.dumps({WAITING: [2, "missed"]}), encoding="utf-8")

    assert run_cli(cli_files, "--defer-file", str(as_list)) == 0
    assert run_cli(cli_files, "--defer-file", str(as_object)) == 0


def test_cli_exits_2_on_an_unknown_id_or_a_bad_defer_file(
    cli_files: dict[str, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]", encoding="utf-8")

    assert run_cli(cli_files, "--defer", "EL-NOPE") == 2
    assert "EL-NOPE" in capsys.readouterr().err
    assert run_cli(cli_files, "--defer-file", str(bad)) == 2
    assert run_cli(cli_files, "--defer-file", str(tmp_path / "missing.json")) == 2
