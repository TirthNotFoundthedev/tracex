"""Integration fixtures: the API fixtures of tests/api, and one generated small-tier dataset."""

from pathlib import Path

import pytest

from tests.api.conftest import Api, api, pg_template  # noqa: F401 - fixtures re-exported
from tracex_api.seed_demo import generate_dataset

DATA_KIT = Path(__file__).resolve().parents[3] / "data-kit"


@pytest.fixture(scope="session")
def small_dataset(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return generate_dataset(DATA_KIT, "small", tmp_path_factory.mktemp("kit") / "small")
