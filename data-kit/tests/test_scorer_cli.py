"""G-16: `python -m datakit score` and the engine-result input schema."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from datakit.cli import main
from tests.conftest import KIT_ROOT
from tests.scorer_helpers import drop_edge_of_link, perfect_result

SCHEMA_PATH = KIT_ROOT / "schema" / "engine_result.schema.json"


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(SCHEMA_PATH.read_text("utf-8"))
    return data


@pytest.fixture
def files(tmp_path: Path, small_dir: Path, gt: dict[str, Any]) -> dict[str, Path]:
    result = tmp_path / "perfect.json"
    result.write_text(json.dumps(perfect_result(gt)), encoding="utf-8")
    broken = perfect_result(gt)
    drop_edge_of_link(broken, gt, "EL-FX01-PER")
    missed = tmp_path / "missed.json"
    missed.write_text(json.dumps(broken), encoding="utf-8")
    return {"gt": small_dir / "ground_truth.json", "perfect": result, "missed": missed}


def test_schema_is_a_valid_draft_2020_12_schema(schema: dict[str, Any]) -> None:
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "engine-result/1"


def test_a_result_derived_from_ground_truth_validates(
    schema: dict[str, Any], gt: dict[str, Any]
) -> None:
    for batches in (("b01",), ("b01", "b02")):
        Draft202012Validator(schema).validate(perfect_result(gt, batches=batches))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.pop("entities"),
        lambda r: r.pop("edges"),
        lambda r: r.update(schema_version="engine-result/2"),
        lambda r: r["entities"][0].pop("mentions"),
        lambda r: r["entities"][0].update(type="CAR"),
        lambda r: r["entities"][0].update(raw_text="x"),
        lambda r: next(e for e in r["entities"] if e["type"] == "PERSON")["mentions"][0].pop(
            "raw_text"
        ),
        lambda r: r["edges"][0].pop("evidence_kinds"),
        lambda r: r["edges"][0].update(state="WITHDRAWN"),
        lambda r: r.update(batches_loaded=["b02"]),
        lambda r: r.update(batches_loaded=[]),
        lambda r: r["entities"][0]["mentions"][0].update(line=0),
        lambda r: r["edges"][0].update(state="MAYBE"),
        lambda r: r["edges"][0].update(band="HUGE"),
        lambda r: r["edges"][0].pop("sources"),
        lambda r: r["edges"][0].update(score=True),
        lambda r: r["edges"][0].update(gates_failed=[{"gate": "G6"}]),
        lambda r: r.update(batches_loaded=["b03"]),
        lambda r: r.update(extra="field"),
    ],
)
def test_malformed_results_are_rejected_by_the_schema(
    schema: dict[str, Any], gt: dict[str, Any], mutate: Any
) -> None:
    result = copy.deepcopy(perfect_result(gt))
    mutate(result)
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(result)


def test_score_command_exits_zero_for_a_flawless_result(
    files: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["score", "--ground-truth", str(files["gt"]), "--result", str(files["perfect"])])
    out = capsys.readouterr().out
    assert code == 0
    assert "PASS" in out


def test_score_command_exits_one_and_names_the_missed_link(
    files: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["score", "--ground-truth", str(files["gt"]), "--result", str(files["missed"])])
    out = capsys.readouterr().out
    assert code == 1
    assert "EL-FX01-PER" in out


def test_score_command_json_flag_prints_the_machine_readable_report(
    files: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["score", "--ground-truth", str(files["gt"]), "--result", str(files["missed"]), "--json"]
    )
    report = json.loads(capsys.readouterr().out)
    assert code == 1
    assert report["ok"] is False
    assert [m["id"] for m in report["missed_links"]] == ["EL-FX01-PER"]


def test_score_command_exits_two_on_unreadable_or_invalid_input(
    files: dict[str, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "nope.json"
    assert main(["score", "--ground-truth", str(files["gt"]), "--result", str(missing)]) == 2
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert main(["score", "--ground-truth", str(files["gt"]), "--result", str(bad)]) == 2
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps({"schema_version": "engine-result/9"}), encoding="utf-8")
    assert main(["score", "--ground-truth", str(files["gt"]), "--result", str(wrong)]) == 2
    assert "error" in capsys.readouterr().err.lower()


def test_module_entry_point_runs_the_score_command(files: dict[str, Path]) -> None:
    proc = subprocess.run(  # noqa: S603 - fixed argv, test-owned paths
        [
            sys.executable,
            "-m",
            "datakit",
            "score",
            "--ground-truth",
            str(files["gt"]),
            "--result",
            str(files["perfect"]),
        ],
        cwd=KIT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "PASS" in proc.stdout


def test_optional_run_block_and_per_edge_link_id_validate(
    schema: dict[str, Any], gt: dict[str, Any]
) -> None:
    result = perfect_result(gt)
    result["run"] = {
        "ruleset_version": "engine-matching/1.1",
        "thresholds_version": 1,
        "status": "SUCCEEDED",
        "counts": {"AUTO": 4, "SUGGESTED": 0},
    }
    result["edges"][0]["link_id"] = "link-0001"
    Draft202012Validator(schema).validate(result)
    result["run"]["status"] = ""
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(result)
