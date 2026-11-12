"""Per-case evidence for the G-09 isolation check: names, ages, DOBs, localities, place-dates."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

CATEGORIES = ("names", "ages", "dobs", "localities", "place_dates")

AGE_RE = re.compile(r"(?:aged|age|umra|उम्र)\s+(\d{1,3})")
DOB_RE = re.compile(r"(?:DOB|janm tithi|जन्म तिथि)\s+(\d{2})-(\d{2})-(\d{4})")
LOCALITY_RE = re.compile(r"(?:village|Mohalla|mohalla|gram|ग्राम|मोहल्ला)\s+([^,.;()]+)")


@dataclass
class CaseEvidence:
    names: set[str] = field(default_factory=set)
    ages: set[str] = field(default_factory=set)
    dobs: set[str] = field(default_factory=set)
    localities: set[str] = field(default_factory=set)
    place_dates: set[tuple[str, date]] = field(default_factory=set)


def _cdr_place_dates(root: Path, case_id: str) -> set[tuple[str, date]]:
    found: set[tuple[str, date]] = set()
    for batch in ("b01", "b02"):
        case_dir = root / "batches" / batch / "cases" / case_id
        if not case_dir.is_dir():
            continue
        for path in sorted(case_dir.glob("cdr*.csv")):
            with path.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    day = date.fromisoformat(row["start_time"][:10])
                    found.add((row["tower_place"].strip().lower(), day))
    return found


def _sdr_localities(root: Path, case_id: str) -> set[str]:
    found: set[str] = set()
    for batch in ("b01", "b02"):
        case_dir = root / "batches" / batch / "cases" / case_id
        if not case_dir.is_dir():
            continue
        for path in sorted(case_dir.glob("sdr*.csv")):
            with path.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    if row["locality"].strip():
                        found.add(row["locality"].strip().lower())
    return found


def _text_evidence(root: Path, case_id: str, item: CaseEvidence) -> None:
    """Ages, DOBs and localities as written in FIR and note lines, independent of ground truth."""
    for batch in ("b01", "b02"):
        case_dir = root / "batches" / batch / "cases" / case_id
        if not case_dir.is_dir():
            continue
        for path in sorted([*case_dir.glob("fir*.txt"), *case_dir.glob("notes*.txt")]):
            for line in path.read_text(encoding="utf-8").splitlines():
                item.ages.update(AGE_RE.findall(line))
                item.dobs.update(f"{y}-{m}-{d}" for d, m, y in DOB_RE.findall(line))
                item.localities.update(m.strip().lower() for m in LOCALITY_RE.findall(line))


def collect_evidence(root: Path, gt: dict[str, Any]) -> dict[str, CaseEvidence]:
    """Evidence per case, read from ground-truth attributes (every person the extractor sees
    has an entity) plus CDR place-dates and SDR localities from the files."""
    evidence: dict[str, CaseEvidence] = defaultdict(CaseEvidence)
    for entity in gt["entities"]:
        if entity["type"] not in ("PERSON", "ORG"):
            continue
        item = evidence[entity["case_id"]]
        item.names.add(entity["normalized"].lower())
        attrs = entity.get("attributes", {})
        item.names.update(str(a).lower() for a in attrs.get("aliases", []))
        if "age" in attrs:
            item.ages.add(str(attrs["age"]))
        if "dob" in attrs:
            item.dobs.add(str(attrs["dob"]))
        if "locality" in attrs:
            item.localities.add(str(attrs["locality"]).lower())
    for case_id in list(evidence):
        evidence[case_id].localities |= _sdr_localities(root, case_id)
        _text_evidence(root, case_id, evidence[case_id])
        evidence[case_id].place_dates = _cdr_place_dates(root, case_id)
    return evidence


def shared_place_dates(a: CaseEvidence, b: CaseEvidence) -> set[tuple[str, date]]:
    """Place-dates of `a` that also occur in `b` on the same day or a day either side (Q5)."""
    day = timedelta(days=1)
    near = {(p, d + shift) for p, d in b.place_dates for shift in (-day, timedelta(0), day)}
    return {pd for pd in a.place_dates if pd in near}


def shared(a: CaseEvidence, b: CaseEvidence) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {
        "names": a.names & b.names,
        "ages": a.ages & b.ages,
        "dobs": a.dobs & b.dobs,
        "localities": a.localities & b.localities,
        "place_dates": {f"{p}@{d.isoformat()}" for p, d in shared_place_dates(a, b)},
    }
    return result
