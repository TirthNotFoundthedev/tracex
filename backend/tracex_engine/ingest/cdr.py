"""CDR parser: `cdr.csv` of the data kit (docs/specs/data-kit.md section 4.3)."""

from datetime import datetime
from typing import Literal, cast

from tracex_engine.ingest.records import CdrRow, ParseResult, SourceRef
from tracex_engine.ingest.tabular import parse_csv_rows
from tracex_engine.normalize import Value, normalize_phone, normalize_place

CDR_HEADER = (
    "call_id",
    "start_time",
    "duration_sec",
    "calling_no",
    "called_no",
    "call_type",
    "cell_id",
    "tower_place",
)
_CALL_TYPES = ("VOICE", "SMS")


def _number(cell: str) -> Value | None:
    normalized = normalize_phone(cell)
    return Value(cell, normalized) if normalized else None


def _build(source: SourceRef, raw_line: str, cells: dict[str, str]) -> CdrRow | str:
    if not cells["call_id"].strip():
        return "call_id is empty"
    try:
        start_time = datetime.fromisoformat(cells["start_time"].strip())
    except ValueError:
        return f"start_time {cells['start_time']!r} is not an ISO 8601 timestamp"
    if start_time.tzinfo is None:
        return f"start_time {cells['start_time']!r} has no UTC offset"
    duration = cells["duration_sec"].strip()
    if not (duration.isascii() and duration.isdigit()):
        return f"duration_sec {cells['duration_sec']!r} is not a whole number of seconds"
    calling = _number(cells["calling_no"])
    if calling is None:
        return f"calling_no {cells['calling_no']!r} is not a valid mobile number"
    called = _number(cells["called_no"])
    if called is None:
        return f"called_no {cells['called_no']!r} is not a valid mobile number"
    call_type = cells["call_type"].strip()
    if call_type not in _CALL_TYPES:
        return f"call_type {cells['call_type']!r} is not one of {', '.join(_CALL_TYPES)}"
    place = cells["tower_place"]
    return CdrRow(
        source=source,
        raw_line=raw_line,
        call_id=cells["call_id"].strip(),
        start_time=start_time,
        duration_sec=int(duration),
        calling=calling,
        called=called,
        call_type=cast(Literal["VOICE", "SMS"], call_type),
        cell_id=cells["cell_id"].strip(),
        tower_place=Value(place, normalize_place(place)) if place.strip() else None,
    )


def parse_cdr(case_id: str, file: str, text: str) -> ParseResult[CdrRow]:
    """Parse a CDR file. Bad rows are reported in `errors` with their line number and reason."""
    return parse_csv_rows(case_id, file, text, CDR_HEADER, _build)
