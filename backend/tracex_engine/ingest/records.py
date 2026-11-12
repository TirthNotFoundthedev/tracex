"""Record types produced by the ingest parsers. All are immutable and carry provenance."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from tracex_engine.normalize import Value


@dataclass(frozen=True)
class SourceRef:
    """Where a value was read: case, file (relative to the case directory) and 1-based line.

    Lines are physical lines of the file, header and blank lines counted (data-kit section 2).
    """

    case_id: str
    file: str
    line: int


@dataclass(frozen=True)
class RowError:
    """A row or line that could not be read. Reported, never dropped silently."""

    source: SourceRef
    raw_line: str
    reason: str


@dataclass(frozen=True)
class ParseResult[T]:
    """Every row that parsed, and an error for every row that did not."""

    rows: tuple[T, ...]
    errors: tuple[RowError, ...]


@dataclass(frozen=True)
class CdrRow:
    """One call record. `calling` and `called` keep the number as written beside the 10 digits."""

    source: SourceRef
    raw_line: str
    call_id: str
    start_time: datetime
    duration_sec: int
    calling: Value
    called: Value
    call_type: Literal["VOICE", "SMS"]
    cell_id: str
    tower_place: Value | None


@dataclass(frozen=True)
class BankRow:
    """One bank-statement row.

    `holder` is the account holder as written (the OWNS source for the account).
    `counterparty_kind` says what `counterparty` holds: a phone (UPI handle or number), an
    account, a name (kept in `counterparty_text` only) or nothing.
    """

    source: SourceRef
    raw_line: str
    txn_id: str
    txn_date: date
    account: Value
    ifsc: Value | None
    holder: str
    direction: Literal["DR", "CR"]
    counterparty: Value | None
    counterparty_kind: Literal["PHONE", "ACCOUNT", "NAME", "NONE"]
    counterparty_text: str
    narration: str
    amount_inr: Decimal
    balance_inr: Decimal | None


@dataclass(frozen=True)
class SdrRow:
    """One SIM subscriber record: the only source of REGISTERED_TO."""

    source: SourceRef
    raw_line: str
    msisdn: Value
    subscriber_name: str
    relative_name: str
    locality: str
    district: str
    activated_on: date | None


@dataclass(frozen=True)
class TextLine:
    """One physical line of free text (FIR narrative), numbered as in the file."""

    source: SourceRef
    text: str


@dataclass(frozen=True)
class NoteLine:
    """One officer note `[YYYY-MM-DD] <rank and initials>: <text>`. `text` is the whole line."""

    source: SourceRef
    text: str
    body: str
    note_date: date
    author: str


@dataclass(frozen=True)
class NotesResult:
    lines: tuple[NoteLine, ...]
    errors: tuple[RowError, ...]


@dataclass(frozen=True)
class FirResult:
    """`header` maps each `Label: value` line before the narrative to (value, source)."""

    header: Mapping[str, tuple[str, SourceRef]]
    narrative: tuple[TextLine, ...]
    errors: tuple[RowError, ...]
