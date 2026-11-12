"""Bank-statement parser: `bank.csv` of the data kit (docs/specs/data-kit.md section 4.3)."""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal, cast

from tracex_engine.ingest.records import BankRow, ParseResult, SourceRef
from tracex_engine.ingest.tabular import parse_csv_rows
from tracex_engine.normalize import (
    Value,
    normalize_account,
    normalize_ifsc,
    normalize_phone,
    phone_from_upi,
)

BANK_HEADER = (
    "txn_id",
    "txn_date",
    "account_no",
    "ifsc",
    "account_holder",
    "direction",
    "counterparty",
    "narration",
    "amount_inr",
    "balance_inr",
)
_CounterpartyKind = Literal["PHONE", "ACCOUNT", "NAME", "NONE"]


def _money(cell: str) -> Decimal | None:
    try:
        value = Decimal(cell.strip())
    except InvalidOperation:
        return None
    return value if value.is_finite() and value >= 0 else None


def _counterparty(cell: str) -> tuple[Value | None, _CounterpartyKind]:
    text = cell.strip()
    if not text:
        return None, "NONE"
    if phone := phone_from_upi(text) or normalize_phone(text):
        return Value(cell, phone), "PHONE"
    if account := normalize_account(text):
        return Value(cell, account), "ACCOUNT"
    return None, "NAME"


def _build(source: SourceRef, raw_line: str, cells: dict[str, str]) -> BankRow | str:
    try:
        txn_date = date.fromisoformat(cells["txn_date"].strip())
    except ValueError:
        return f"txn_date {cells['txn_date']!r} is not an ISO date (YYYY-MM-DD)"
    account = normalize_account(cells["account_no"])
    if account is None:
        return f"account_no {cells['account_no']!r} is not 9 to 18 digits"
    ifsc_cell = cells["ifsc"]
    ifsc = normalize_ifsc(ifsc_cell)
    if ifsc_cell.strip() and ifsc is None:
        return f"ifsc {ifsc_cell!r} is not a valid IFSC"
    if not cells["account_holder"].strip():
        return "account_holder is empty"
    direction = cells["direction"].strip()
    if direction not in ("DR", "CR"):
        return f"direction {cells['direction']!r} is not DR or CR"
    amount = _money(cells["amount_inr"])
    if amount is None:
        return f"amount_inr {cells['amount_inr']!r} is not a non-negative amount"
    balance_cell = cells["balance_inr"]
    balance = _money(balance_cell)
    if balance_cell.strip() and balance is None:
        return f"balance_inr {balance_cell!r} is not a non-negative amount"
    counterparty, kind = _counterparty(cells["counterparty"])
    return BankRow(
        source=source,
        raw_line=raw_line,
        txn_id=cells["txn_id"].strip(),
        txn_date=txn_date,
        account=Value(cells["account_no"], account),
        ifsc=Value(ifsc_cell, ifsc) if ifsc else None,
        holder=cells["account_holder"],
        direction=cast(Literal["DR", "CR"], direction),
        counterparty=counterparty,
        counterparty_kind=kind,
        counterparty_text=cells["counterparty"],
        narration=cells["narration"],
        amount_inr=amount,
        balance_inr=balance,
    )


def parse_bank(case_id: str, file: str, text: str) -> ParseResult[BankRow]:
    """Parse a bank statement. Bad rows are reported in `errors` with line number and reason."""
    return parse_csv_rows(case_id, file, text, BANK_HEADER, _build)
