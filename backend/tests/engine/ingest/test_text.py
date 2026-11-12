"""FIR and officer-note readers: line numbers are physical, malformed lines are reported."""

from datetime import date

from tests.engine.support import BANNER, fir_file, note, notes_file
from tracex_engine.ingest import SourceRef, read_fir, read_notes


def test_notes_lines_carry_physical_line_number_date_author_and_body() -> None:
    text = notes_file("C-201", {3: note("Number 9000014471 is used by Irfan bhai.")}, last=5)

    result = read_notes("C-201", "notes.txt", text)

    assert result.errors == ()
    first = result.lines[0]
    assert first.source == SourceRef("C-201", "notes.txt", 3)
    assert first.note_date == date(2026, 10, 2)
    assert first.author == "SI RV"
    assert first.body == "Number 9000014471 is used by Irfan bhai."
    assert first.text == note("Number 9000014471 is used by Irfan bhai.")
    assert [line.source.line for line in result.lines] == [3, 4, 5]


def test_notes_line_outside_the_frame_is_reported_and_the_rest_still_read() -> None:
    text = "\n".join(
        [
            BANNER,
            "# Officer notes, case C-201",
            note("fine one."),
            "free text with no frame",
            note("fine two."),
        ]
    )

    result = read_notes("C-201", "notes.txt", text)

    assert [line.source.line for line in result.lines] == [3, 5]
    [error] = result.errors
    assert error.source == SourceRef("C-201", "notes.txt", 4)
    assert error.raw_line == "free text with no frame"
    assert error.reason


def test_notes_blank_lines_are_not_rows() -> None:
    text = "\n".join([BANNER, "# Officer notes, case C-201", "", note("one.")])

    result = read_notes("C-201", "notes.txt", text)

    assert [line.source.line for line in result.lines] == [4]
    assert result.errors == ()


def test_fir_reader_splits_header_fields_from_narrative_lines() -> None:
    text = fir_file("C-101", {12: "First paragraph.", 13: "Second paragraph."}, last=13)

    result = read_fir("C-101", "fir.txt", text)

    assert result.errors == ()
    assert result.header["District"] == ("Rivergate", SourceRef("C-101", "fir.txt", 6))
    assert result.header["Complainant"][0] == "Sunil Arora, aged 52"
    assert [(line.source.line, line.text) for line in result.narrative] == [
        (12, "First paragraph."),
        (13, "Second paragraph."),
    ]


def test_fir_without_a_narrative_marker_is_reported_and_yields_no_narrative() -> None:
    result = read_fir("C-101", "fir.txt", f"{BANNER}\nFIR No: SYN-C-101/2026\nSome text.\n")

    assert result.narrative == ()
    assert [e.reason for e in result.errors] == ["no NARRATIVE: line found; narrative not read"]
    assert result.errors[0].source.line == 1


def test_crlf_files_give_the_same_lines() -> None:
    lf = fir_file("C-101", {12: "Para."}, last=12)

    assert read_fir("C-101", "fir.txt", lf.replace("\n", "\r\n")) == read_fir(
        "C-101", "fir.txt", lf
    )
