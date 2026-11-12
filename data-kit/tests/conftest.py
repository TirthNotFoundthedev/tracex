from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from datakit.generate import DEFAULT_SEED, generate_kit

KIT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def small_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("small_a")
    generate_kit("small", DEFAULT_SEED, out)
    return out


@pytest.fixture(scope="session")
def small_dir_again(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("small_b")
    generate_kit("small", DEFAULT_SEED, out)
    return out


@pytest.fixture(scope="session")
def gt(small_dir: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((small_dir / "ground_truth.json").read_text("utf-8"))
    return data


@pytest.fixture(scope="session")
def manifest(small_dir: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((small_dir / "manifest.json").read_text("utf-8"))
    return data


@pytest.fixture(scope="session")
def read_case_file(small_dir: Path) -> Callable[..., list[str]]:
    def _read(case_id: str, name: str, batch: str = "b01") -> list[str]:
        path = small_dir / "batches" / batch / "cases" / case_id / name
        return path.read_text("utf-8").split("\n")[:-1]

    return _read
