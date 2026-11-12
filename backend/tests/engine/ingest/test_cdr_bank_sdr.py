"""CDR, bank and SDR parsers: provenance on every row, malformed rows reported not dropped."""

from decimal import Decimal

import pytest

from tests.engine.support import BANK_HEADER, CDR_HEADER, SDR_HEADER, bank_row, cdr_row, pinned_file
from tracex_engine.ingest import SourceRef, parse_bank, parse_cdr, parse_sdr


def test_cdr_row_keeps_raw_numbers_normalized_numbers_and_its_line() -> None:
    row33 = (
        "SYN-C-201-33,2026-09-18T10:15:00+05:30,75,90000 21203,+91-9000014471,"
        "VOICE,CELL9,Hillcrest Market"
    )
    text = pinned_file({1: CDR_HEADER, 33: row33}, lambda n: cdr_row(n))

    result = parse_cdr("C-201", "cdr.csv", text)

    assert result.errors == ()
    assert len(result.rows) == 32
    [row] = [r for r in result.rows if r.source.line == 33]
    assert row.source == SourceRef("C-201", "cdr.csv", 33)
    assert row.raw_line == row33
    assert (row.calling.raw_text, row.calling.normalized) == ("90000 21203", "9000021203")
    assert (row.called.raw_text, row.called.normalized) == ("+91-9000014471", "9000014471")
    assert row.call_id == "SYN-C-201-33"
    assert row.start_time.isoformat() == "2026-09-18T10:15:00+05:30"
    assert row.duration_sec == 75
    assert row.call_type == "VOICE"
    assert row.cell_id == "CELL9"
    assert row.tower_place is not None
    assert (row.tower_place.raw_text, row.tower_place.normalized) == (
        "Hillcrest Market",
        "hillcrest market",
    )


def test_cdr_malformed_rows_are_reported_with_row_number_and_reason_and_the_batch_continues() -> (
    None
):
    lines = [
        CDR_HEADER,
        cdr_row(2),
        "SYN-C-201-3,not-a-time,60,9100000001,9100000002,VOICE,CELL3,Market",
        cdr_row(4),
        "SYN-C-201-5,2026-09-18T10:00:00+05:30,sixty,9100000001,9100000002,VOICE,CELL5,Market",
        "SYN-C-201-6,2026-09-18T10:00:00+05:30,60,12345,9100000002,VOICE,CELL6,Market",
        "SYN-C-201-7,2026-09-18T10:00:00+05:30,60,9100000001,9100000002,FAX,CELL7,Market",
        "SYN-C-201-8,only,three",
        cdr_row(9),
        '"SYN-C-201-10,unterminated quote',
    ]

    result = parse_cdr("C-201", "cdr.csv", "\n".join(lines) + "\n")

    assert [r.source.line for r in result.rows] == [2, 4, 9]
    assert [e.source.line for e in result.errors] == [3, 5, 6, 7, 8, 10]
    assert all(e.reason for e in result.errors)
    assert result.errors[0].raw_line == lines[2]
    assert "start_time" in result.errors[0].reason
    assert "duration_sec" in result.errors[1].reason
    assert "calling_no" in result.errors[2].reason
    assert "call_type" in result.errors[3].reason
    assert "8" in result.errors[4].reason and "columns" in result.errors[4].reason


def test_cdr_header_mismatch_is_one_error_on_line_1_and_no_rows() -> None:
    result = parse_cdr("C-201", "cdr.csv", "id,time\n1,2\n")

    assert result.rows == ()
    assert [e.source.line for e in result.errors] == [1]
    assert "header" in result.errors[0].reason


def test_cdr_empty_file_is_reported_not_a_crash() -> None:
    result = parse_cdr("C-201", "cdr.csv", "")

    assert result.rows == ()
    assert len(result.errors) == 1


def test_bank_row_parses_holder_account_counterparty_and_amounts() -> None:
    row4 = (
        "TX4,2026-09-10,5010000019082,SYNB0000123,MOHD IRFAN,DR,9000021203@upi,"
        "upi transfer,9500.00,100.50"
    )
    text = pinned_file({1: BANK_HEADER, 4: row4}, lambda n: bank_row(n))

    result = parse_bank("C-101", "bank.csv", text)

    assert result.errors == ()
    [row] = [r for r in result.rows if r.source.line == 4]
    assert row.source == SourceRef("C-101", "bank.csv", 4)
    assert row.raw_line == row4
    assert (row.account.raw_text, row.account.normalized) == ("5010000019082", "5010000019082")
    assert row.ifsc is not None and row.ifsc.normalized == "SYNB0000123"
    assert row.holder == "MOHD IRFAN"
    assert row.direction == "DR"
    assert row.counterparty is not None
    assert (row.counterparty.raw_text, row.counterparty.normalized) == (
        "9000021203@upi",
        "9000021203",
    )
    assert row.counterparty_kind == "PHONE"
    assert row.amount_inr == Decimal("9500.00")
    assert row.balance_inr == Decimal("100.50")


def test_bank_unknown_ifsc_and_account_number_counterparty_and_name_counterparty() -> None:
    lines = [
        BANK_HEADER,
        "TX2,2026-09-10,5010000088801,,AJAY PAL,CR,5019000000002,neft,10.00,",
        "TX3,2026-09-10,5010000088801,,AJAY PAL,CR,RAJU STORE,cash,10.00,5.00",
    ]

    result = parse_bank("C-214", "bank.csv", "\n".join(lines) + "\n")

    assert result.errors == ()
    first, second = result.rows
    assert first.ifsc is None
    assert first.balance_inr is None
    assert first.counterparty_kind == "ACCOUNT"
    assert first.counterparty is not None and first.counterparty.normalized == "5019000000002"
    assert second.counterparty is None
    assert second.counterparty_kind == "NAME"
    assert second.counterparty_text == "RAJU STORE"


def test_bank_account_leading_zeros_are_kept() -> None:
    row = "TX2,2026-09-10,0010000088801,SYNB0000123,AJAY PAL,CR,,neft,10.00,5.00"

    [parsed] = parse_bank("C-1", "bank.csv", f"{BANK_HEADER}\n{row}\n").rows

    assert parsed.account.normalized == "0010000088801"


@pytest.mark.parametrize(
    ("row", "field"),
    [
        ("TX2,10-09-2026,5010000088801,SYNB0000123,AJAY PAL,DR,,x,10.00,5.00", "txn_date"),
        ("TX2,2026-09-10,50100,SYNB0000123,AJAY PAL,DR,,x,10.00,5.00", "account_no"),
        ("TX2,2026-09-10,5010000088801,BADIFSC,AJAY PAL,DR,,x,10.00,5.00", "ifsc"),
        ("TX2,2026-09-10,5010000088801,SYNB0000123,AJAY PAL,XX,,x,10.00,5.00", "direction"),
        ("TX2,2026-09-10,5010000088801,SYNB0000123,AJAY PAL,DR,,x,ten,5.00", "amount_inr"),
        ("TX2,2026-09-10,5010000088801,SYNB0000123,AJAY PAL,DR,,x,10.00,5.00,extra", "columns"),
    ],
)
def test_bank_malformed_row_is_reported_with_its_line_and_the_field_at_fault(
    row: str, field: str
) -> None:
    text = f"{BANK_HEADER}\n{bank_row(2)}\n{row}\n{bank_row(4)}\n"

    result = parse_bank("C-1", "bank.csv", text)

    assert [r.source.line for r in result.rows] == [2, 4]
    [error] = result.errors
    assert error.source == SourceRef("C-1", "bank.csv", 3)
    assert error.raw_line == row
    assert field in error.reason


def test_sdr_rows_carry_subscriber_phone_and_provenance() -> None:
    rows = ["9000035562,Kamla Devi,Ram Devi,Kherapur,Rivergate,2024-01-05", "9000035563,,,,,"]
    text = "\n".join([SDR_HEADER, *rows]) + "\n"

    result = parse_sdr("C-111", "sdr.csv", text)

    [row] = result.rows
    assert row.source == SourceRef("C-111", "sdr.csv", 2)
    assert (row.msisdn.raw_text, row.msisdn.normalized) == ("9000035562", "9000035562")
    assert row.subscriber_name == "Kamla Devi"
    assert row.relative_name == "Ram Devi"
    assert row.locality == "Kherapur"
    assert row.district == "Rivergate"
    [error] = result.errors
    assert error.source.line == 3
    assert "subscriber_name" in error.reason


def test_bank_row_with_no_account_holder_is_a_valid_row_with_an_empty_holder() -> None:
    """Real planted rows (AC-04, AC-26) leave account_holder empty."""
    row = "TX3,2026-09-10,5010000088801,SYNB0000123,,DR,CASH DEPOSIT,x,10.00,5.00"

    result = parse_bank("C-124", "bank.csv", f"{BANK_HEADER}\n{row}\n")

    assert result.errors == ()
    [parsed] = result.rows
    assert parsed.holder == ""
    assert parsed.account.normalized == "5010000088801"
    assert parsed.counterparty_kind == "NAME"
