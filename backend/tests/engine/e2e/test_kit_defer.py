"""The scorer's `--defer` on the real engine result: the waiting list makes `ok` true mid-build.

The links pinned in `waiting.py` are the ones the engine cannot reach until Tier 2 lands. Naming
exactly them lets `python -m datakit score` report `ok: true` while they are listed apart from
the passed ones; naming fewer leaves the run failing.
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
def test_the_waiting_list_deferred_makes_the_scorer_ok(
    batch: str, kit: Path, tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    run: KitRun = request.getfixturevalue(f"run_{batch}")
    waiting = sorted(FAILING[batch])

    report = score_with_defer(kit, run, tmp_path, waiting)

    assert report["ok"] is True
    assert sorted(d["id"] for d in report["deferred"]) == waiting
    assert all(d["status"] == "waiting" for d in report["deferred"])
    assert report["forbidden_hits"] == [] and report["wrong_links"] == []
    assert {s["id"] for s in report["skipped"]} == set(SKIPPED[batch])


def test_deferring_all_but_one_waiting_link_leaves_that_one_failing(
    kit: Path, tmp_path: Path, run_b01: KitRun
) -> None:
    waiting = sorted(FAILING["b01"])

    report = score_with_defer(kit, run_b01, tmp_path, waiting[1:])

    assert report["ok"] is False
    named = {m["id"] for m in report["missed_links"]} | {w["id"] for w in report["wrong_links"]}
    assert named == {waiting[0]}
