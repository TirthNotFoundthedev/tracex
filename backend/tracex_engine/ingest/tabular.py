"""Line-by-line CSV reading that keeps physical line numbers and reports bad rows."""

import csv
import re
from collections.abc import Callable, Sequence

from tracex_engine.ingest.records import ParseResult, RowError, SourceRef

_LINE_BREAK = re.compile(r"\r\n|\n|\r")


def split_lines(text: str) -> list[str]:
    """Physical lines of `text` (LF, CRLF or CR), without a trailing empty line."""
    text = text.removeprefix("﻿")
    lines = _LINE_BREAK.split(text)
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def parse_csv_rows[T](
    case_id: str,
    file: str,
    text: str,
    header: Sequence[str],
    build: Callable[[SourceRef, str, dict[str, str]], T | str],
) -> ParseResult[T]:
    """Parse `text` whose first line must be exactly `header`.

    `build` returns the row, or a reason string when the row is invalid. Blank lines are not
    rows. A row that cannot be read becomes a `RowError` with its physical line number; one bad
    row never stops the rest.
    """
    lines = split_lines(text)
    first = SourceRef(case_id, file, 1)
    if not lines:
        return ParseResult((), (RowError(first, "", "file is empty, expected a header row"),))
    if _split_csv_line(lines[0]) != list(header):
        reason = f"header does not match the expected columns: {','.join(header)}"
        return ParseResult((), (RowError(first, lines[0], reason),))

    rows: list[T] = []
    errors: list[RowError] = []
    for number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        source = SourceRef(case_id, file, number)
        cells = _split_csv_line(line)
        if cells is None:
            errors.append(RowError(source, line, "line is not valid CSV"))
        elif len(cells) != len(header):
            errors.append(
                RowError(source, line, f"expected {len(header)} columns, got {len(cells)}")
            )
        else:
            built = build(source, line, dict(zip(header, cells, strict=True)))
            if isinstance(built, str):
                errors.append(RowError(source, line, built))
            else:
                rows.append(built)
    return ParseResult(tuple(rows), tuple(errors))


def _split_csv_line(line: str) -> list[str] | None:
    try:
        return next(csv.reader([line]), [])
    except csv.Error:
        return None
