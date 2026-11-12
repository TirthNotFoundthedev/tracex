"""FIR and officer-note readers (docs/specs/data-kit.md sections 4.1 and 4.2)."""

import re
from datetime import date

from tracex_engine.ingest.records import (
    FirResult,
    NoteLine,
    NotesResult,
    RowError,
    SourceRef,
    TextLine,
)
from tracex_engine.ingest.tabular import split_lines

NARRATIVE_MARKER = "NARRATIVE:"
_BANNER_PREFIX = "SYNTHETIC DATA"
_NOTE = re.compile(r"^\[(?P<date>[^\]]*)\]\s+(?P<author>[^:]+?):\s*(?P<body>.*)$")
_HEADER_FIELD = re.compile(r"^(?P<label>[A-Za-z][A-Za-z ]*?):\s*(?P<value>.*)$")


def read_notes(case_id: str, file: str, text: str) -> NotesResult:
    """Read officer notes. Lines outside the `[date] author: text` frame are reported."""
    lines: list[NoteLine] = []
    errors: list[RowError] = []
    for number, line in enumerate(split_lines(text), start=1):
        if not line.strip() or line.startswith("#") or (number == 1 and _is_banner(line)):
            continue
        source = SourceRef(case_id, file, number)
        match = _NOTE.match(line)
        if match is None:
            errors.append(
                RowError(source, line, "note is not in the form '[YYYY-MM-DD] author: text'")
            )
            continue
        try:
            note_date = date.fromisoformat(match["date"].strip())
        except ValueError:
            errors.append(RowError(source, line, f"note date {match['date']!r} is not YYYY-MM-DD"))
            continue
        if not match["body"].strip():
            errors.append(RowError(source, line, "note has no text"))
            continue
        lines.append(
            NoteLine(source, line, match["body"].strip(), note_date, match["author"].strip())
        )
    return NotesResult(tuple(lines), tuple(errors))


def read_fir(case_id: str, file: str, text: str) -> FirResult:
    """Split a FIR into its `Label: value` header and the narrative lines after `NARRATIVE:`."""
    all_lines = split_lines(text)
    marker = next((i for i, line in enumerate(all_lines) if line.strip() == NARRATIVE_MARKER), None)
    header: dict[str, tuple[str, SourceRef]] = {}
    errors: list[RowError] = []
    header_end = len(all_lines) if marker is None else marker
    for index in range(header_end):
        line = all_lines[index]
        if not line.strip() or (index == 0 and _is_banner(line)):
            continue
        source = SourceRef(case_id, file, index + 1)
        match = _HEADER_FIELD.match(line)
        if match is not None:
            header.setdefault(match["label"].strip(), (match["value"].strip(), source))
        elif marker is not None:
            errors.append(RowError(source, line, "header line is not in the form 'Label: value'"))
    if marker is None:
        reason = "no NARRATIVE: line found; narrative not read"
        first = all_lines[0] if all_lines else ""
        return FirResult(header, (), (RowError(SourceRef(case_id, file, 1), first, reason),))
    narrative = tuple(
        TextLine(SourceRef(case_id, file, index + 1), all_lines[index])
        for index in range(marker + 1, len(all_lines))
        if all_lines[index].strip()
    )
    return FirResult(header, narrative, tuple(errors))


def _is_banner(line: str) -> bool:
    return line.startswith(_BANNER_PREFIX)
