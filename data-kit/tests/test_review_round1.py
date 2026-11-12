"""Fix round 1 (review of PR 16): AC-21 score, AC-11 place-dates, AC-13 spellings, SF-01 cue, B2."""

from __future__ import annotations

import csv
from collections.abc import Callable
from datetime import date
from typing import Any


def _link(gt: dict[str, Any], link_id: str) -> dict[str, Any]:
    return next(x for x in gt["expected_links"] if x["id"] == link_id)


def test_ac21_org_pair_records_the_org_ceiling_of_ninety(gt: dict[str, Any]) -> None:
    link = _link(gt, "EL-FX21-ORG")
    assert link["type"] == "ORG"
    assert link["score"] == {"value": 90.0, "mode": "band"}


def test_ac11_cdrs_share_exactly_three_place_dates(
    read_case_file: Callable[..., list[str]],
) -> None:
    def pairs(case_id: str) -> set[tuple[str, date]]:
        rows = list(csv.reader(read_case_file(case_id, "cdr.csv")))[1:]
        return {(r[7], date.fromisoformat(r[1][:10])) for r in rows}

    first, second = pairs("C-115"), pairs("C-125")
    shared = {
        (tower, day)
        for tower, day in first
        if any(t == tower and abs((d - day).days) <= 1 for t, d in second)
    }
    assert len(shared) == 3


def test_ac13_uses_four_distinct_close_spellings(gt: dict[str, Any]) -> None:
    names = {
        e["gt_id"]: e["raw_text"] for e in gt["entities"] if e["gt_id"].startswith("FX-13.PER.")
    }
    assert sorted(names) == ["FX-13.PER.Q1", "FX-13.PER.Q2", "FX-13.PER.Q3", "FX-13.PER.Q4"]
    assert len(set(names.values())) == 4


def test_sf01_kalu_line_has_a_person_cue(read_case_file: Callable[..., list[str]]) -> None:
    lines = [x for x in read_case_file("C-127", "notes.txt") if "Kalu" in x]
    assert any("Accused Kalu was seen again near the market." in x for x in lines)


def test_b2_collision_pairs_are_listed_as_non_links(gt: dict[str, Any]) -> None:
    rows = [
        n for n in gt["expected_non_links"] if n["trap"] == "TR-11" and n["id"].startswith("NL-B2-")
    ]
    assert len(rows) == 4
    entities = {e["gt_id"]: e for e in gt["entities"]}
    for row in rows:
        assert row["forbid"] == "ANY_EDGE"
        assert "not an adjacent swap" in row["why"]
        values = {entities[row["a"]]["normalized"], entities[row["b"]]["normalized"]}
        assert values == {"9000021203", "9000022310"}
        cases = {entities[row["a"]]["case_id"], entities[row["b"]]["case_id"]}
        assert len(cases) == 2
