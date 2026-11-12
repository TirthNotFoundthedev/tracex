"""G-01, G-04, G-13, G-18: determinism, golden hash, tiers, batch isolation, size."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from datakit.generate import DEFAULT_SEED, KIT_VERSION, generate_kit
from tests.conftest import KIT_ROOT
from tests.helpers import case_files


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_same_seed_gives_byte_identical_output(small_dir: Path, small_dir_again: Path) -> None:
    first, second = _tree(small_dir), _tree(small_dir_again)
    assert first.keys() == second.keys()
    assert all(first[name] == second[name] for name in first)


def test_manifest_hash_equals_committed_golden_hash(small_dir: Path) -> None:
    golden = (KIT_ROOT / "golden" / "small.sha256").read_text("utf-8").strip()
    actual = hashlib.sha256((small_dir / "manifest.json").read_bytes()).hexdigest()
    assert actual == golden


def test_manifest_lists_every_file_with_matching_sha256(
    small_dir: Path, manifest: dict[str, Any]
) -> None:
    assert manifest["kit_version"] == KIT_VERSION
    assert manifest["seed"] == DEFAULT_SEED
    assert manifest["tier"] == "small"
    listed = {entry["path"]: entry for entry in manifest["files"]}
    on_disk = {
        name for name in _tree(small_dir) if name not in ("manifest.json",)
    }
    assert set(listed) == on_disk
    for name, entry in listed.items():
        data = (small_dir / name).read_bytes()
        assert entry["sha256"] == hashlib.sha256(data).hexdigest()
        assert entry["bytes"] == len(data)


def test_different_seed_changes_the_noise_but_not_the_planted_values(
    small_dir: Path, tmp_path: Path
) -> None:
    generate_kit("small", DEFAULT_SEED + 1, tmp_path)
    first = (small_dir / "manifest.json").read_bytes()
    assert (tmp_path / "manifest.json").read_bytes() != first
    planted = (small_dir / "batches/b01/cases/C-201/notes.txt").read_text("utf-8").split("\n")[2]
    other = (tmp_path / "batches/b01/cases/C-201/notes.txt").read_text("utf-8").split("\n")[2]
    assert "Number 9000014471 is used by Irfan bhai." in planted
    assert "Number 9000014471 is used by Irfan bhai." in other


def test_small_tier_has_62_planted_and_60_noise_cases(gt: dict[str, Any], small_dir: Path) -> None:
    ids = {case_id for case_id, _, _ in case_files(small_dir, "b01")}
    ids |= {case_id for case_id, _, _ in case_files(small_dir, "b02")}
    planted = {c for c in ids if int(c[3:]) < 50}
    noise = ids - planted
    assert len(planted) == 62
    assert len(noise) == 60
    per_district = {d: sum(1 for c in noise if c[2] == d) for d in "1234"}
    assert per_district == {"1": 15, "2": 15, "3": 15, "4": 15}


def test_planted_cases_are_byte_identical_in_the_demo_tier(small_dir: Path, tmp_path: Path) -> None:
    started = time.monotonic()
    generate_kit("demo", DEFAULT_SEED, tmp_path)
    assert time.monotonic() - started < 300
    for batch in ("b01", "b02"):
        for case_id, name, path in case_files(small_dir, batch):
            if int(case_id[3:]) >= 50:
                continue
            other = tmp_path / "batches" / batch / "cases" / case_id / name
            assert other.read_bytes() == path.read_bytes(), (case_id, name)
    demo_noise = {c for c, _, _ in case_files(tmp_path, "b01") if int(c[3:]) >= 50}
    assert len(demo_noise) == 600


def test_b02_only_adds_files_and_leaves_b01_untouched(small_dir: Path, tmp_path: Path) -> None:
    generate_kit("small", DEFAULT_SEED, tmp_path, batches=("b01",))
    assert not (tmp_path / "batches" / "b02").exists()
    full = json.loads((small_dir / "manifest.json").read_text("utf-8"))
    only = json.loads((tmp_path / "manifest.json").read_text("utf-8"))
    full_b01 = {e["path"]: e["sha256"] for e in full["files"] if "/b01/" in e["path"]}
    only_b01 = {e["path"]: e["sha256"] for e in only["files"] if "/b01/" in e["path"]}
    assert full_b01 == only_b01
    b02_names = {
        (case_id, name) for case_id, name, _ in case_files(small_dir, "b02")
    }
    b01_names = {(case_id, name) for case_id, name, _ in case_files(small_dir, "b01")}
    assert b02_names and not (b02_names & b01_names)


def test_small_tier_is_within_the_size_budget(small_dir: Path) -> None:
    total = sum(p.stat().st_size for p in small_dir.rglob("*") if p.is_file())
    assert total <= 10 * 1024 * 1024


def test_small_tier_generates_in_under_thirty_seconds(tmp_path: Path) -> None:
    started = time.monotonic()
    generate_kit("small", DEFAULT_SEED, tmp_path)
    assert time.monotonic() - started < 30
