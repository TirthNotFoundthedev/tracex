"""The scorer's `--defer` on the real engine result: nothing waits, so `ok` holds alone.

With Tiers 1-3 every expected link passes, so nothing is deferred and `ok` holds on its own; a
deferred link that passes is reported `passing`, never counted as passed.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.engine.e2e.conftest import KitRun
from tests.engine.e2e.kit import KIT_DIR
from tests.engine.e2e.waiting import FAILING, SKIPPED
from tracex_engine.matching import write_engine_result


def score_with_defer(kit: Path, run: KitRun, workdir: Path, ids: list[str]) -> dict[str, Any]:
    result = workdir / "result.json"
    write_engine_result(result, run.document)
    listed = workdir / "defer.json"
    listed.write_text(json.dumps(ids), encoding="utf-8")
    done = subprocess.run(  # noqa: S603 - fixed arguments, repository code
        [
            sys.executable,
            "-m",
            "datakit",
            "score",
            "--ground-truth",
            str(kit / "ground_truth.json"),
            "--result",
            str(result),
            "--defer-file",
            str(listed),
            "--json",
        ],
        cwd=KIT_DIR,
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert done.returncode in (0, 1), done.stderr.decode("utf-8", "replace")
    report: dict[str, Any] = json.loads(done.stdout)
    return report


@pytest.mark.parametrize("batch", ["b01", "b02"])
def test_the_scorer_is_ok_with_nothing_deferred(
    batch: str, kit: Path, tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    """P3.3 goal: every expected link passes, so `ok` holds without `--defer`."""
    run: KitRun = request.getfixturevalue(f"run_{batch}")
    assert FAILING[batch] == {}

    report = score_with_defer(kit, run, tmp_path, [])

    assert report["ok"] is True and report["deferred"] == []
    assert report["missed_links"] == [] and report["wrong_links"] == []
    assert report["forbidden_hits"] == []
    assert {s["id"] for s in report["skipped"]} == set(SKIPPED[batch])


def test_a_deferred_link_that_passes_is_reported_passing_never_passed(
    kit: Path, tmp_path: Path, run_b01: KitRun
) -> None:
    report = score_with_defer(kit, run_b01, tmp_path, ["EL-FX01-PER"])

    assert report["deferred"] == [
        {"id": "EL-FX01-PER", "ac": ["AC-01"], "status": "passing", "failures": []}
    ]
    assert report["checks"]["S1"]["deferred"] == 1
