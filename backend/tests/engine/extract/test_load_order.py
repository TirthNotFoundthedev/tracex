"""The file load-order key exported by the extractor (fir, notes, sdr, cdr, bank, then batches)."""

import pytest

from tests.engine.support import BANK_HEADER, CDR_HEADER, SDR_HEADER, cdr_row, fir_file
from tracex_engine.extract import extract_case, file_load_key


def test_baseline_files_load_in_kind_order() -> None:
    names = ["bank.csv", "cdr.csv", "sdr.csv", "notes.txt", "fir.txt"]

    assert sorted(names, key=file_load_key) == [
        "fir.txt",
        "notes.txt",
        "sdr.csv",
        "cdr.csv",
        "bank.csv",
    ]


def test_later_batches_follow_every_baseline_file_by_number() -> None:
    names = ["notes-10.txt", "cdr-02.csv", "bank.csv", "notes-02.txt", "fir.txt", "fir-03.txt"]

    assert sorted(names, key=file_load_key) == [
        "fir.txt",
        "bank.csv",
        "notes-02.txt",
        "cdr-02.csv",
        "fir-03.txt",
        "notes-10.txt",
    ]


def test_batch_numbers_compare_as_numbers_not_text() -> None:
    assert file_load_key("notes-9.txt") < file_load_key("notes-10.txt")


@pytest.mark.parametrize("name", ["readme.txt", "fir.json", "notes-x.txt", "FIR.txt", ""])
def test_unknown_names_sort_last_by_name(name: str) -> None:
    assert file_load_key(name) > file_load_key("bank-99.csv")
    assert file_load_key(name)[2] == name


def test_extract_case_reads_files_in_the_exported_order() -> None:
    files = {
        "cdr.csv": CDR_HEADER + "\n" + cdr_row(2, "9100000001", "9100000002") + "\n",
        "bank.csv": BANK_HEADER + "\n",
        "sdr.csv": SDR_HEADER + "\n",
        "fir.txt": fir_file("C-107", {12: "Mobile 9100000003 was seen."}),
    }

    records = extract_case("C-107", files)

    first_files = [i.source.file for i in records.identifiers]
    assert first_files == sorted(first_files, key=file_load_key)
