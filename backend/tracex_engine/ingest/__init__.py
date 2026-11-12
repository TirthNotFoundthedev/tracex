"""Ingest: parsers that turn case files into typed rows, keeping provenance on every one.

Pure functions over file text (`str`); reading files from disk is the caller's job. Line numbers
are physical lines of the file as in docs/specs/data-kit.md section 2. A row that cannot be read
becomes a `RowError` (source, raw line, reason); it is never dropped silently and never stops the
batch.

Exposed:
    SourceRef                  case_id, file (relative to the case directory), 1-based line
    RowError, ParseResult[T]   rows that parsed, errors for rows that did not
    parse_cdr    -> ParseResult[CdrRow]    cdr.csv
    parse_bank   -> ParseResult[BankRow]   bank.csv
    parse_sdr    -> ParseResult[SdrRow]    sdr.csv (SIM subscriber records)
    read_notes   -> NotesResult            notes.txt: NoteLine(source, text, body, date, author)
    read_fir     -> FirResult              fir.txt: header fields and narrative TextLines

Phone numbers in rows are `Value(raw_text, normalized)`: the number as written beside its
ten digits.
"""

from tracex_engine.ingest.bank import parse_bank
from tracex_engine.ingest.cdr import parse_cdr
from tracex_engine.ingest.records import (
    BankRow,
    CdrRow,
    FirResult,
    NoteLine,
    NotesResult,
    ParseResult,
    RowError,
    SdrRow,
    SourceRef,
    TextLine,
)
from tracex_engine.ingest.sdr import parse_sdr
from tracex_engine.ingest.text import read_fir, read_notes

__all__ = [
    "BankRow",
    "CdrRow",
    "FirResult",
    "NoteLine",
    "NotesResult",
    "ParseResult",
    "RowError",
    "SdrRow",
    "SourceRef",
    "TextLine",
    "parse_bank",
    "parse_cdr",
    "parse_sdr",
    "read_fir",
    "read_notes",
]
