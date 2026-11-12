"""Case-level extraction: load order, provenance across files, resilience to bad input."""

import random
import string

from tests.engine.support import CDR_HEADER, cdr_row, fir_file, note, notes_file, pinned_file
from tracex_engine.extract import (
    AttributionCode,
    IdentifierMention,
    IdKind,
    OrgMention,
    PersonMention,
    extract_case,
)
from tracex_engine.ingest import SourceRef


def test_cdr_rows_cite_their_line_and_give_both_numbers_as_phones() -> None:
    """Worked scenario, C-201/cdr.csv:33 and :41."""
    row33 = "SYN-C-201-33,2026-09-18T10:15:00+05:30,75,9000021203,9000014471,VOICE,CELL9,Hillcrest"
    row41 = "SYN-C-201-41,2026-09-18T11:15:00+05:30,75,9000028816,9000014471,VOICE,CELL9,Hillcrest"
    text = pinned_file({1: CDR_HEADER, 33: row33, 41: row41}, lambda n: cdr_row(n), last=45)

    records = extract_case("C-201", {"cdr.csv": text})

    cited = {
        (i.normalized, i.source.line) for i in records.identifiers if i.source.line in (33, 41)
    }
    assert cited == {
        ("9000021203", 33),
        ("9000014471", 33),
        ("9000028816", 41),
        ("9000014471", 41),
    }
    assert [r.source.line for r in records.cdr_rows][:2] == [2, 3]
    assert records.errors == ()


def test_complainant_header_line_is_a_person_cited_to_line_9() -> None:
    records = extract_case("C-101", {"fir.txt": fir_file("C-101", {}, last=12)})

    [complainant] = [p for p in records.persons if p.role == "complainant"]
    assert complainant.raw_text == "Sunil Arora"
    assert complainant.source == SourceRef("C-101", "fir.txt", 9)
    assert complainant.age is not None and complainant.age.normalized == "52"


def test_his_number_is_ties_the_number_to_the_last_person_of_the_previous_sentence() -> None:
    line = "The accused Ramesh Yadav was arrested at the bus stand. His number is 9000022310."
    records = extract_case("C-109", {"fir.txt": fir_file("C-109", {12: line})})

    [attribution] = records.attributions
    assert attribution.holder.normalized == "ramesh yadav"
    assert attribution.code is AttributionCode.OWNS
    assert attribution.identifier.normalized == "9000022310"


def test_mohd_abbreviation_does_not_split_the_sentence() -> None:
    line = "The accused Mohd. Irfan, mobile 9000014471, absconded."
    records = extract_case("C-101", {"fir.txt": fir_file("C-101", {12: line})})

    [attribution] = records.attributions
    assert attribution.holder.raw_text == "Mohd. Irfan"


def test_files_are_read_in_load_order_and_later_batches_follow_the_baseline() -> None:
    files = {
        "notes-02.txt": notes_file("C-107", {3: note("Number 9000079900 is used by Jaswinder.")}),
        "bank.csv": "bad header\n",
        "notes.txt": notes_file("C-107", {3: note("Number 9000011111 is used by Jaswinder.")}),
        "fir.txt": fir_file("C-107", {}),
    }

    records = extract_case("C-107", files)

    note_numbers = [
        (i.source.file, i.normalized) for i in records.identifiers if i.source.file != "fir.txt"
    ]
    assert note_numbers == [("notes.txt", "9000011111"), ("notes-02.txt", "9000079900")]


def test_unknown_file_name_and_malformed_rows_are_reported_and_the_rest_is_still_read() -> None:
    files = {
        "notes.txt": notes_file("C-1", {3: note("Number 9000014471 is used by Irfan bhai.")}),
        "photo.jpg": "not text",
        "cdr.csv": f"{CDR_HEADER}\nbroken row\n",
    }

    records = extract_case("C-1", files)

    assert [a.identifier.normalized for a in records.attributions] == ["9000014471"]
    assert {(e.source.file, e.source.line) for e in records.errors} == {
        ("photo.jpg", 1),
        ("cdr.csv", 2),
    }


def test_arbitrary_text_never_raises_and_every_mention_is_cited_and_raw() -> None:
    rng = random.Random(7)  # noqa: S311 - seeded fuzz input, not security
    alphabet = string.ascii_letters + string.digits + " ,.;:/@()+-क्षां\n"
    for _ in range(300):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 200)))
        line = text.replace("\n", " ")
        files = {"fir.txt": fir_file("C-9", {12: line}), "notes.txt": notes_file("C-9", {3: line})}

        records = extract_case("C-9", files)

        mentions: list[PersonMention | OrgMention | IdentifierMention] = [
            *records.persons,
            *records.orgs,
            *records.identifiers,
        ]
        for mention in mentions:
            assert mention.raw_text in files[mention.source.file]
            assert mention.source.case_id == "C-9" and mention.source.line >= 1
        for attribution in records.attributions:
            assert attribution.identifier.kind in set(IdKind)
