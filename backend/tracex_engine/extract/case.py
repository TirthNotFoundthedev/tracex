"""Extraction for one case: every file in load order, one `CaseRecords` out."""

from collections.abc import Callable, Mapping

from tracex_engine.extract.order import FILE_NAME, file_load_key
from tracex_engine.extract.records import (
    Attribution,
    CaseRecords,
    IdentifierMention,
    OrgMention,
    PersonMention,
)
from tracex_engine.extract.structured import extract_bank, extract_cdr, extract_sdr
from tracex_engine.extract.text import TextRecords, extract_text_line
from tracex_engine.ingest import (
    BankRow,
    CdrRow,
    RowError,
    SdrRow,
    SourceRef,
    parse_bank,
    parse_cdr,
    parse_sdr,
    read_fir,
    read_notes,
)
from tracex_engine.ingest.tabular import split_lines


class _Collector:
    def __init__(self) -> None:
        self.persons: list[PersonMention] = []
        self.orgs: list[OrgMention] = []
        self.identifiers: list[IdentifierMention] = []
        self.attributions: list[Attribution] = []
        self.cdr_rows: list[CdrRow] = []
        self.bank_rows: list[BankRow] = []
        self.sdr_rows: list[SdrRow] = []
        self.errors: list[RowError] = []

    def add(self, records: TextRecords) -> None:
        self.persons.extend(records.persons)
        self.orgs.extend(records.orgs)
        self.identifiers.extend(records.identifiers)
        self.attributions.extend(records.attributions)


def extract_case(case_id: str, files: Mapping[str, str]) -> CaseRecords:
    """Read and extract every file of one case. `files` maps file name to its text.

    Files are processed in load order, so mentions come out in the order entity ids must
    follow. A file whose name is not one of the data-kit kinds is reported, not read.
    """
    out = _Collector()
    readable: list[tuple[str, str]] = []
    for name in sorted(files):
        match = FILE_NAME.match(name)
        if match is None:
            out.errors.append(
                RowError(SourceRef(case_id, name, 1), "", "file name not recognised; not read")
            )
            continue
        readable.append((match["kind"], name))
    for kind, name in sorted(readable, key=lambda item: file_load_key(item[1])):
        _READERS[kind](case_id, name, files[name], out)
    return CaseRecords(
        case_id=case_id,
        persons=tuple(out.persons),
        orgs=tuple(out.orgs),
        identifiers=tuple(out.identifiers),
        attributions=tuple(out.attributions),
        cdr_rows=tuple(out.cdr_rows),
        bank_rows=tuple(out.bank_rows),
        sdr_rows=tuple(out.sdr_rows),
        errors=tuple(out.errors),
    )


def _read_fir(case_id: str, name: str, text: str, out: _Collector) -> None:
    fir = read_fir(case_id, name, text)
    out.errors.extend(fir.errors)
    complainant = fir.header.get("Complainant")
    if complainant is not None and complainant[0]:
        value, source = complainant
        written = split_lines(text)[source.line - 1]
        out.add(extract_text_line(source, f"complainant {value}", statement=written))
    for line in fir.narrative:
        out.add(extract_text_line(line.source, line.text))


def _read_notes(case_id: str, name: str, text: str, out: _Collector) -> None:
    notes = read_notes(case_id, name, text)
    out.errors.extend(notes.errors)
    for line in notes.lines:
        out.add(extract_text_line(line.source, line.body, whole_line=True))


def _read_sdr(case_id: str, name: str, text: str, out: _Collector) -> None:
    parsed = parse_sdr(case_id, name, text)
    out.errors.extend(parsed.errors)
    for row in parsed.rows:
        out.sdr_rows.append(row)
        records = extract_sdr(row)
        out.persons.extend(records.persons)
        out.identifiers.extend(records.identifiers)
        out.attributions.extend(records.attributions)


def _read_cdr(case_id: str, name: str, text: str, out: _Collector) -> None:
    parsed = parse_cdr(case_id, name, text)
    out.errors.extend(parsed.errors)
    for row in parsed.rows:
        out.cdr_rows.append(row)
        out.identifiers.extend(extract_cdr(row).identifiers)


def _read_bank(case_id: str, name: str, text: str, out: _Collector) -> None:
    parsed = parse_bank(case_id, name, text)
    out.errors.extend(parsed.errors)
    for row in parsed.rows:
        out.bank_rows.append(row)
        records = extract_bank(row)
        out.persons.extend(records.persons)
        out.orgs.extend(records.orgs)
        out.identifiers.extend(records.identifiers)
        out.attributions.extend(records.attributions)


_READERS: dict[str, Callable[[str, str, str, _Collector], None]] = {
    "fir": _read_fir,
    "notes": _read_notes,
    "sdr": _read_sdr,
    "cdr": _read_cdr,
    "bank": _read_bank,
}
