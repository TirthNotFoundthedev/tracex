"""Review round 1, minors 1 and 2: nothing is dropped without a report; header kept verbatim."""

from tests.engine.support import BANNER, fir_file, note
from tracex_engine.extract import AttributionCode, extract_case
from tracex_engine.ingest import SourceRef, read_fir, read_notes


def test_a_hash_line_other_than_the_title_is_reported() -> None:
    text = "\n".join([BANNER, "# Officer notes, case C-1", note("one."), "# stray", note("two.")])

    result = read_notes("C-1", "notes.txt", text)

    assert [line.source.line for line in result.lines] == [3, 5]
    [error] = result.errors
    assert error.source == SourceRef("C-1", "notes.txt", 4)
    assert error.raw_line == "# stray"


def test_a_repeated_fir_header_label_is_reported_and_the_first_value_kept() -> None:
    text = fir_file("C-1", {5: "District: Rivergate", 6: "District: Hillcrest"}, last=12)

    result = read_fir("C-1", "fir.txt", text)

    assert result.header["District"] == ("Rivergate", SourceRef("C-1", "fir.txt", 5))
    [error] = result.errors
    assert error.source == SourceRef("C-1", "fir.txt", 6)
    assert "District" in error.reason


def test_complainant_statement_is_the_header_line_as_written() -> None:
    line = "Complainant: Sunil Arora, aged 52, mobile 9000011111"
    files = {"fir.txt": fir_file("C-1", {9: line}, last=12)}

    records = extract_case("C-1", files)

    [attribution] = [a for a in records.attributions if a.source.line == 9]
    assert attribution.raw_text == line
    assert attribution.code is AttributionCode.OWNS
    assert attribution.holder.raw_text == "Sunil Arora"
