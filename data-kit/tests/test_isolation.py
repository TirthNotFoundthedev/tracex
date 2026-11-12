"""G-09 per-AC isolation: names, ages, DOBs, localities and place-dates shared between cases."""

from __future__ import annotations

import itertools
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tests.helpers import phones_in
from tests.isolation import (
    AGE_RE,
    CATEGORIES,
    DOB_RE,
    LOCALITY_RE,
    CaseEvidence,
    collect_evidence,
    shared,
)

# Section 5 and 5.1 rows: the end cases of each fixture.
ROWS: dict[str, list[str]] = {
    "AC-01": ["C-101", "C-201"],
    "AC-02": ["C-103", "C-104"],
    "AC-03": ["C-105", "C-302"],
    "AC-04": ["C-106", "C-203"],
    "AC-05": ["C-107", "C-108"],
    "AC-06": ["C-401", "C-402"],
    "AC-07": ["C-109", "C-204"],
    "AC-08": ["C-110", "C-111"],
    "AC-09": ["C-112", "C-205", "C-303"],
    "AC-10": ["C-113", "C-114"],
    "AC-11": ["C-115", "C-125"],
    "AC-12": ["C-116", "C-207", "C-304"],
    "AC-13": ["C-117", "C-118", "C-208", "C-305"],
    "AC-14": ["C-119", "C-209"],
    "AC-17": ["C-120", "C-210"],
    "AC-19": ["C-121", "C-211"],
    "AC-21": ["C-122", "C-126"],
    "AC-22": ["C-123", "C-213"],
    "AC-26": ["C-124", "C-214", "C-306"],
    "SF-02": ["C-128", "C-206"],
    "SF-03": ["C-129", "C-212"],
    "SF-04": ["C-130", "C-131", "C-215"],
    "SF-05": ["C-132", "C-216"],
    "SF-06": ["C-133", "C-217"],
    "SF-07": ["C-134", "C-135"],
    "SF-08": ["C-136", "C-218"],
}

# What section 5 says each row shares beyond identifiers; every other category is empty.
NAMES = {
    "AC-06": {"mohammad khan"},  # TR-01: the common name in two spellings
    "AC-10": {"arjun mehra"},  # TR-05: same name, different DOB
    "AC-12": {"sohan rawat"},  # the same name in all three
    "AC-14": {"rakesh dubey", "monu"},  # Z: `Rakesh Dubey urf Monu`; Y: R1 and R3
    "AC-17": {"mohammad irfan"},  # the Devanagari and Roman writings normalize alike
    "AC-22": {"naveen tomar"},
    "SF-06": {"pooja verma"},
    "SF-07": {"dinesh pathania"},
}
LOCALITIES = {
    "AC-05": {"kherapur"},
    "AC-10": {"shivpuri"},
    "AC-11": {"lal darwaza"},
    "AC-21": {"subhash nagar"},
    "SF-07": {"peepal wali gali"},
}
DOBS = {"AC-11": {"1982-06-18"}}
PLACE_DATES = {
    "AC-11": {
        "rivergate market@2026-03-10",
        "rivergate ghat@2026-03-11",
        "kherapur chowk@2026-03-12",
    }
}
# TR-10: the AC-17 Irfans against the AC-01 Irfans share a normalized name and nothing else.
EXTRA_PAIRS = {frozenset({"C-101", "C-120"}), frozenset({"C-101", "C-210"})}


@pytest.fixture(scope="module")
def evidence(small_dir: Path, gt: dict[str, Any]) -> dict[str, CaseEvidence]:
    return collect_evidence(small_dir, gt)


def _expected(row: str) -> dict[str, set[str]]:
    return {
        "names": set(NAMES.get(row, set())),
        "ages": set(),
        "dobs": set(DOBS.get(row, set())),
        "localities": set(LOCALITIES.get(row, set())),
        "place_dates": set(PLACE_DATES.get(row, set())),
    }


@pytest.mark.parametrize("row", sorted(ROWS))
def test_end_cases_of_a_row_share_exactly_what_section_5_lists(
    evidence: dict[str, CaseEvidence], row: str
) -> None:
    expected = _expected(row)
    for first, second in itertools.combinations(ROWS[row], 2):
        assert shared(evidence[first], evidence[second]) == expected, (row, first, second)


def test_no_two_planted_cases_outside_a_row_share_names_ages_dobs_localities_or_place_dates(
    evidence: dict[str, CaseEvidence], gt: dict[str, Any]
) -> None:
    planted = sorted({e["case_id"] for e in gt["entities"] if not e["gt_id"].startswith("NZ-")})
    in_a_row = {frozenset(p) for cases in ROWS.values() for p in itertools.combinations(cases, 2)}
    for first, second in itertools.combinations(planted, 2):
        pair = frozenset({first, second})
        if pair in in_a_row or pair in EXTRA_PAIRS:
            continue
        assert not any(shared(evidence[first], evidence[second]).values()), (first, second)


def test_worked_scenario_cases_share_no_name_age_dob_locality_or_place_date(
    evidence: dict[str, CaseEvidence],
) -> None:
    assert shared(evidence["C-101"], evidence["C-201"]) == {k: set() for k in CATEGORIES}


def test_evidence_reader_finds_the_values_the_isolation_check_depends_on(
    evidence: dict[str, CaseEvidence],
) -> None:
    assert "34" in evidence["C-107"].ages and "35" in evidence["C-108"].ages
    assert evidence["C-113"].dobs == {"1990-04-12"} and evidence["C-114"].dobs == {"1978-09-30"}
    assert "kherapur" in evidence["C-107"].localities
    assert ("rivergate market", date(2026, 3, 10)) in evidence["C-115"].place_dates
    assert evidence["C-101"].names >= {"mohammad irfan", "harish arora"}


def test_the_reader_sees_every_age_ground_truth_records(
    evidence: dict[str, CaseEvidence], gt: dict[str, Any]
) -> None:
    attrs_age = {
        str(e["attributes"]["age"])
        for e in gt["entities"]
        if e["case_id"] == "C-107" and "age" in e.get("attributes", {})
    }
    assert attrs_age <= evidence["C-107"].ages


def test_shared_detects_planted_leaks() -> None:
    a = CaseEvidence(
        names={"x y"},
        ages={"30"},
        dobs={"1990-01-01"},
        localities={"l"},
        place_dates={("p", date(2026, 1, 10))},
    )
    b = CaseEvidence(
        names={"x y"},
        ages={"30", "31"},
        dobs={"1990-01-01"},
        localities={"l"},
        place_dates={("p", date(2026, 1, 11))},
    )
    result = shared(a, b)
    assert result == {
        "names": {"x y"},
        "ages": {"30"},
        "dobs": {"1990-01-01"},
        "localities": {"l"},
        "place_dates": {"p@2026-01-10"},
    }
    far = CaseEvidence(place_dates={("p", date(2026, 1, 13))})
    assert shared(a, far)["place_dates"] == set()


def test_ac15_b02_notes_files_are_inside_the_isolation_evidence_and_add_only_the_phone(
    small_dir: Path,
) -> None:
    texts = []
    for case_id in ("C-107", "C-108"):
        path = small_dir / "batches" / "b02" / "cases" / case_id / "notes-02.txt"
        assert path.is_file(), case_id
        assert path in set(path.parent.glob("notes*.txt"))
        texts.append(path.read_text("utf-8"))
    for text in texts:
        phones = {p for line in text.splitlines() for p in phones_in(line)}
        assert phones == {"9000079900"}
        assert not AGE_RE.findall(text) and not DOB_RE.findall(text)
        assert not LOCALITY_RE.findall(text)
