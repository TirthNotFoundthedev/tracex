"""G-12: noise volume and mix within tolerance; flag material."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tests.helpers import case_files, normalize_phone, phones_in


def _noise_cases(small_dir: Path) -> list[str]:
    return sorted({c for c, _, _ in case_files(small_dir, "b01") if int(c[3:]) >= 50})


def _rows(path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.reader(handle)) - 1


def test_noise_rows_per_case_follow_the_small_tier_ranges(small_dir: Path) -> None:
    cases = _noise_cases(small_dir)
    assert len(cases) == 60
    sdr_cases = 0
    for case_id in cases:
        base = small_dir / "batches/b01/cases" / case_id
        assert 36 <= _rows(base / "cdr.csv") <= 88, case_id
        assert 13 <= _rows(base / "bank.csv") <= 44, case_id
        fir = (base / "fir.txt").read_text("utf-8").split("\n")[:-1]
        assert 3 <= len(fir) - 11 <= 8, case_id
        notes = (base / "notes.txt").read_text("utf-8").split("\n")[:-1]
        assert 2 <= len(notes) - 2 <= 6, case_id
        if (base / "sdr.csv").exists():
            sdr_cases += 1
            assert 1 <= _rows(base / "sdr.csv") <= 3, case_id
    assert abs(sdr_cases / 60 - 0.30) <= 0.05


def test_language_mix_is_recorded_and_within_five_points(manifest: dict[str, Any]) -> None:
    languages = manifest["case_languages"]
    noise = {c: lang for c, lang in languages.items() if int(c[3:]) >= 50}
    assert len(noise) == 60
    counts = Counter(noise.values())
    for lang, share in (("en", 0.40), ("hi", 0.25), ("hi-latn", 0.25), ("mixed", 0.10)):
        assert abs(counts[lang] / 60 - share) <= 0.05, lang
    assert set(languages) >= {"C-101", "C-120", "C-210"}
    assert languages["C-107"] == "hi-latn"
    assert languages["C-109"] == "hi-latn"
    assert languages["C-120"] == "hi"
    assert languages["C-210"] == "en"


def test_recurring_identities_and_look_alikes_have_the_stated_rates(gt: dict[str, Any]) -> None:
    noise_persons = [
        e for e in gt["entities"] if e["type"] == "PERSON" and e["gt_id"].startswith("NZ-")
    ]
    ids = {e["gt_id"] for e in noise_persons}
    in_group = {
        m
        for g in gt["groups"]
        if g["origin"] == "noise" and g["scope"] == "cross_case"
        for m in g["members"]
        if m in ids
    }
    assert abs(len(in_group) / len(noise_persons) - 0.12) <= 0.012
    look_alikes = [n for n in gt["expected_non_links"] if n["trap"] == "TR-19"]
    assert abs(2 * len(look_alikes) / len(noise_persons) - 0.02) <= 0.01
    for non in look_alikes:
        assert non["forbid"] == "AUTO"


def test_hub_shared_and_multi_user_material_is_present(small_dir: Path, gt: dict[str, Any]) -> None:
    hubs = 0
    for case_id in _noise_cases(small_dir):
        peers: dict[str, set[str]] = defaultdict(set)
        path = small_dir / "batches/b01/cases" / case_id / "cdr.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            for row in list(csv.reader(handle))[1:]:
                a, b = normalize_phone(row[3]), normalize_phone(row[4])
                peers[a].add(b)
                peers[b].add(a)
        hubs += sum(1 for v in peers.values() if len(v) >= 25)
    assert 1 <= hubs <= 3
    shared = 0
    for case_id in _noise_cases(small_dir):
        text = (small_dir / "batches/b01/cases" / case_id / "notes.txt").read_text("utf-8")
        if "family number" in text or "shop number" in text:
            shared += len(phones_in(text))
    assert shared >= 2
    entities = {e["gt_id"]: e for e in gt["entities"]}
    owners: dict[str, set[str]] = defaultdict(set)
    for attribution in gt["attributions"]:
        ident = entities[attribution["identifier"]]
        if ident["type"] == "ACCOUNT" and attribution["code"] == "OWNS":
            owners[ident["normalized"]].add(entities[attribution["entity"]]["case_id"])
    assert any(len(cases) >= 2 for v, cases in owners.items() if v.startswith("5019"))
