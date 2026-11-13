"""Session fixtures: the small kit is generated once, and each batch run is made once."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tests.engine.e2e.kit import generate, result_document, run_batches, score
from tracex_engine.graph import InMemoryCaseGraphStore
from tracex_engine.matching import InMemoryLinkStore, Matcher, RunResult


@dataclass
class KitRun:
    matcher: Matcher
    results: list[RunResult]
    document: dict[str, Any]
    report: dict[str, Any]
    truth: dict[str, Any]


@pytest.fixture(scope="session")
def kit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("kit_small")
    generate(out)
    return out


def _run(kit: Path, upto: str, workdir: Path) -> KitRun:
    graphs, links = InMemoryCaseGraphStore(), InMemoryLinkStore()
    matcher, results = run_batches(graphs, links, kit, upto)
    batches = ["b01"] if upto == "b01" else ["b01", "b02"]
    document = result_document(graphs, links, batches, results[-1])
    truth = json.loads((kit / "ground_truth.json").read_text("utf-8"))
    return KitRun(matcher, results, document, score(kit, document, workdir), truth)


@pytest.fixture(scope="session")
def run_b01(kit: Path, tmp_path_factory: pytest.TempPathFactory) -> KitRun:
    return _run(kit, "b01", tmp_path_factory.mktemp("result_b01"))


@pytest.fixture(scope="session")
def run_b02(kit: Path, tmp_path_factory: pytest.TempPathFactory) -> KitRun:
    return _run(kit, "b02", tmp_path_factory.mktemp("result_b02"))
