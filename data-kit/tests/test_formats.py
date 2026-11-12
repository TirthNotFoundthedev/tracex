"""G-02, G-03, G-07, G-10: file formats, layout, pinned lines, synthetic-data rules."""

from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import KIT_ROOT
from tests.helpers import (
    CASE_RE,
    NOISE_PHONE_RE,
    PLANTED_PHONE_RE,
    accounts_in,
    all_files,
    case_files,
    normalize_phone,
    numbered_lines,
    phones_in,
    plates_in,
)

BANNER = "SYNTHETIC DATA TRACEX-SYN/1 - NOT A REAL RECORD"
HEADERS = {
    "cdr": "call_id,start_time,duration_sec,calling_no,called_no,call_type,cell_id,tower_place",
    "bank": (
        "txn_id,txn_date,account_no,ifsc,account_holder,direction,counterparty,"
        "narration,amount_inr,balance_inr"
    ),
    "sdr": "msisdn,subscriber_name,relative_name,locality,district,activated_on",
}


def _kind(name: str) -> str:
    return name.split("-")[0].removesuffix(".csv").removesuffix(".txt")


def test_every_file_is_clean_utf8_nfc_lf_without_trailing_spaces(small_dir: Path) -> None:
    for path in sorted(small_dir.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        assert not data.startswith(b"\xef\xbb\xbf"), path
        assert b"\r" not in data, path
        text = data.decode("utf-8")
        assert unicodedata.normalize("NFC", text) == text, path
        assert text.endswith("\n") and not text.endswith("\n\n"), path
        for line in text.split("\n")[:-1]:
            assert line == line.rstrip(" \t"), (path, line)


def test_csv_files_parse_and_carry_exactly_the_spec_header(small_dir: Path) -> None:
    seen: set[str] = set()
    for _batch, case_id, name, path in all_files(small_dir):
        if not name.endswith(".csv"):
            continue
        kind = _kind(name)
        seen.add(kind)
        rows = list(csv.reader(io.StringIO(path.read_text("utf-8"), newline="")))
        assert ",".join(rows[0]) == HEADERS[kind], (case_id, name)
        assert all(len(row) == len(rows[0]) for row in rows), (case_id, name)
    assert seen == {"cdr", "bank", "sdr"}


def test_fir_and_notes_follow_the_fixed_frames(small_dir: Path) -> None:
    prefixes = [
        BANNER,
        "FIR No: SYN-",
        "Date of FIR: ",
        "Date of occurrence: ",
        "Police Station: ",
        "District: ",
        "State: ",
        "Sections: ",
        "Complainant: ",
    ]
    for _batch, case_id, name, path in all_files(small_dir):
        lines = path.read_text("utf-8").split("\n")[:-1]
        if name == "fir.txt":
            for index, prefix in enumerate(prefixes):
                assert lines[index].startswith(prefix), (case_id, index + 1)
            assert re.fullmatch(rf"FIR No: SYN-{case_id}/\d{{4}}", lines[1])
            assert lines[9] == ""
            assert lines[10] == "NARRATIVE:"
            assert len(lines) >= 12
        if name.startswith("notes"):
            assert lines[0] == BANNER
            assert lines[1] == f"# Officer notes, case {case_id}"
            for note in lines[2:]:
                assert re.match(r"^\[\d{4}-\d{2}-\d{2}\] (SI|ASI|HC|Insp|SP) [A-Z]{2}: ", note)


def test_layout_matches_the_spec_and_cases_csv_has_one_row_per_baseline_case(
    small_dir: Path,
) -> None:
    for name in ("manifest.json", "cases.csv", "ground_truth.json", "SYNTHETIC.txt"):
        assert (small_dir / name).is_file()
    b01_cases = {case_id for case_id, _, _ in case_files(small_dir, "b01")}
    with (small_dir / "cases.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [r["case_id"] for r in rows] == sorted(
        b01_cases, key=lambda c: (int(c[2]), int(c[3:]))
    )
    jurisdictions = json.loads((KIT_ROOT / "seed" / "jurisdictions.json").read_text("utf-8"))
    districts = {
        d["name"]: (s["name"], d["id_digit"], d["stations"])
        for s in jurisdictions["states"]
        for d in s["districts"]
    }
    for row in rows:
        assert CASE_RE.match(row["case_id"])
        state, digit, stations = districts[row["district"]]
        assert row["state"] == state
        assert row["case_id"][2] == str(digit)
        assert row["station"] in stations
    for case_id in b01_cases:
        assert (small_dir / "batches/b01/cases" / case_id / "fir.txt").is_file()


def test_pinned_lines_of_the_worked_scenario(
    read_case_file: Callable[..., list[str]],
) -> None:
    fir = read_case_file("C-101", "fir.txt")
    assert "Mohd. Irfan" in fir[11] and "mobile 90000 14471" in fir[11]
    assert "5010000019082 (IFSC SYNB0000123)" in fir[11]
    bank = [next(csv.reader([line])) for line in read_case_file("C-101", "bank.csv")]
    for line_no, counterparty in ((4, "9000021203@upi"), (7, "9000028816@upi")):
        row = bank[line_no - 1]
        assert row[2] == "5010000019082"
        assert row[3] == "SYNB0000123"
        assert row[4] == "MOHD IRFAN"
        assert row[5] == "DR"
        assert row[6] == counterparty
    cdr = [next(csv.reader([line])) for line in read_case_file("C-201", "cdr.csv")]
    assert (cdr[32][3], cdr[32][4]) == ("9000021203", "9000014471")
    assert (cdr[40][3], cdr[40][4]) == ("9000028816", "9000014471")
    notes = read_case_file("C-201", "notes.txt")
    assert re.fullmatch(
        r"\[\d{4}-\d{2}-\d{2}\] SI RV: Number 9000014471 is used by Irfan bhai\.", notes[2]
    )


@pytest.mark.parametrize(
    ("case_id", "name", "needle"),
    [
        ("C-103", "fir.txt", "UP32AB1234"),
        ("C-104", "notes.txt", "up 32 ab 1234"),
        ("C-105", "fir.txt", "9000081914"),
        ("C-302", "notes.txt", "9000081194"),
        ("C-106", "fir.txt", "5010000077345"),
        ("C-106", "fir.txt", "SYNB0000123"),
        ("C-203", "bank.csv", "FAKE0000456"),
        ("C-107", "fir.txt", "Jaswinder Bhullar"),
        ("C-108", "fir.txt", "Jasvinder Bhullar"),
        ("C-401", "fir.txt", "Mohammed Khan"),
        ("C-402", "fir.txt", "Mohd Khan"),
        ("C-109", "notes.txt", "Ramesh Yadav"),
        ("C-109", "notes.txt", "Sunita Yadav"),
        ("C-204", "fir.txt", "Suresh Yadav"),
        ("C-110", "fir.txt", "Vikram Chauhan"),
        ("C-110", "fir.txt", "9000035562"),
        ("C-111", "sdr.csv", "Kamla Devi"),
        ("C-111", "bank.csv", "KAMLA DEVI"),
        ("C-112", "bank.csv", "AJAY PAL"),
        ("C-205", "bank.csv", "IMRAN QURESHI"),
        ("C-303", "bank.csv", "DEEPAK RAWAT"),
        ("C-113", "fir.txt", "Arjun Mehra"),
        ("C-114", "fir.txt", "Mohalla Shivpuri"),
        ("C-115", "fir.txt", "Parminder Atwal"),
        ("C-125", "fir.txt", "Parminder Atwaal"),
        ("C-116", "fir.txt", "Sohan Rawat"),
        ("C-207", "fir.txt", "Sohan Rawat"),
        ("C-304", "fir.txt", "Sohan Rawat"),
        ("C-209", "fir.txt", "Rakesh Dubey urf Monu"),
        ("C-120", "fir.txt", unicodedata.normalize("NFC", "मोहम्मद इरफ़ान")),
        ("C-120", "fir.txt", "90000 51234"),
        ("C-210", "fir.txt", "Mohd Irfan"),
        ("C-121", "fir.txt", "UP32CD9021"),
        ("C-211", "notes.txt", "noted as UP32CD9021 (unverified)"),
        ("C-122", "fir.txt", "M/s Shree Balaji Traders"),
        ("C-126", "fir.txt", "M/s Shri Balaji Trading Co"),
        ("C-126", "bank.csv", "SHRI BALAJI TRADING CO"),
        ("C-123", "fir.txt", "Naveen Tomar"),
        ("C-213", "fir.txt", "Naveen Tomar"),
        ("C-124", "bank.csv", "5010000088801"),
        ("C-214", "bank.csv", "5010000088801"),
        ("C-306", "bank.csv", "FAKE0000456"),
        ("C-101", "fir.txt", "UP32AC5678"),
        ("C-301", "notes.txt", "UP32AC5678"),
        ("C-102", "cdr.csv", "9000014471"),
        ("C-128", "fir.txt", "9000091827"),
        ("C-206", "fir.txt", "9000097821"),
        ("C-129", "bank.csv", "5010000091001"),
        ("C-212", "bank.csv", "5010000091002"),
        ("C-130", "cdr.csv", "9000087000"),
        ("C-132", "notes.txt", "shop number"),
        ("C-133", "fir.txt", "Pooja Verma"),
        ("C-217", "fir.txt", "Pooja Verma"),
        ("C-136", "fir.txt", "Girish Bhatt"),
        ("C-218", "fir.txt", "Tanvi Oberoi"),
    ],
)
def test_planted_acceptance_content_is_in_the_expected_file(
    read_case_file: Callable[..., list[str]], case_id: str, name: str, needle: str
) -> None:
    assert any(needle in line for line in read_case_file(case_id, name)), (case_id, name, needle)


@pytest.mark.parametrize(
    ("batch", "case_id", "name", "needles"),
    [
        ("b02", "C-201", "cdr-02.csv", ("9000014471", "9000014741")),
        ("b02", "C-202", "cdr.csv", ("9000014471",)),
        ("b02", "C-107", "notes-02.txt", ("Number 9000079900 is used by",)),
        ("b02", "C-108", "notes-02.txt", ("Number 9000079900 is used by",)),
        ("b02", "C-134", "notes-02.txt", ("9000089015",)),
        ("b02", "C-135", "notes-02.txt", ("9000089015",)),
    ],
)
def test_batch_two_content(
    read_case_file: Callable[..., list[str]],
    batch: str,
    case_id: str,
    name: str,
    needles: tuple[str, ...],
) -> None:
    text = "\n".join(read_case_file(case_id, name, batch))
    for needle in needles:
        assert needle in text


def test_phones_accounts_and_ifsc_stay_inside_the_declared_ranges(small_dir: Path) -> None:
    for _batch, case_id, name, path in all_files(small_dir):
        for line_no, line in numbered_lines(path):
            for phone in phones_in(line):
                value = normalize_phone(phone)
                ok = PLANTED_PHONE_RE.match(value) or NOISE_PHONE_RE.match(value)
                assert ok, (case_id, name, line_no, value)
            for account in accounts_in(line):
                assert re.match(r"^(5010000\d{6}|5019\d{9})$", account), (case_id, name, line_no)
            assert not re.search(r"(?<!\d)\d{12}(?!\d)", line), (case_id, name, line_no)
            for ifsc in re.findall(r"[A-Z]{4}0\d{6}", line):
                assert re.match(r"^(SYNB|FAKE)0\d{6}$", ifsc), (case_id, name, line_no)
            for at in re.finditer("@", line):
                assert re.match(r"\d{10}@upi", line[at.start() - 10 :]), (case_id, name, line_no)


def test_every_fir_and_notes_file_carries_the_banner(small_dir: Path) -> None:
    for _batch, case_id, name, path in all_files(small_dir):
        if name.startswith(("fir", "notes")):
            assert path.read_text("utf-8").split("\n")[0] == BANNER, (case_id, name)


def test_noise_plates_use_the_unissued_zz_series(small_dir: Path, gt: dict[str, Any]) -> None:
    planted = {e["normalized"] for e in gt["entities"] if not e["gt_id"].startswith("NZ-")}
    for _batch, case_id, name, path in all_files(small_dir):
        for line_no, line in numbered_lines(path):
            for plate in plates_in(line):
                if plate not in planted:
                    assert "ZZ" in plate, (case_id, name, line_no, plate)
