"""Ownership statements: an identifier is attached to the person it is said to belong to."""

from tests.engine.support import BANK_HEADER, bank_row, fir_file, note, notes_file, pinned_file
from tracex_engine.extract import AttributionCode, IdKind, extract_case
from tracex_engine.ingest import SourceRef


def test_note_phone_is_used_by_person_attaches_phone_to_that_person() -> None:
    """Worked scenario, C-201/notes.txt:3. Without this the scenario falls to review."""
    files = {
        "notes.txt": notes_file("C-201", {3: note("Number 9000014471 is used by Irfan bhai.")})
    }

    records = extract_case("C-201", files)

    [person] = records.persons
    assert person.raw_text == "Irfan bhai"
    assert person.normalized == "irfan"
    assert person.source == SourceRef("C-201", "notes.txt", 3)
    assert person.confidence == 0.9
    [owns] = [a for a in records.attributions if a.holder is person]
    assert owns.code is AttributionCode.OWNS
    assert owns.hedged is False
    assert owns.identifier.kind is IdKind.PHONE
    assert owns.identifier.raw_text == "9000014471"
    assert owns.identifier.normalized == "9000014471"
    assert owns.source == SourceRef("C-201", "notes.txt", 3)
    assert "is used by Irfan bhai" in owns.raw_text


def test_fir_line_gives_owned_phone_and_account_with_ifsc_to_the_accused() -> None:
    """Worked scenario, C-101/fir.txt:12."""
    line = "The accused Mohd. Irfan, mobile 90000 14471, a/c 5010000019082 (IFSC SYNB0000123)."
    files = {"fir.txt": fir_file("C-101", {12: line}, last=16)}

    records = extract_case("C-101", files)

    accused = [p for p in records.persons if p.source.line == 12]
    [irfan] = accused
    assert irfan.raw_text == "Mohd. Irfan"
    assert irfan.normalized == "mohammad irfan"
    assert irfan.confidence == 0.9
    owned = {a.identifier.kind: a for a in records.attributions if a.holder is irfan}
    assert set(owned) == {IdKind.PHONE, IdKind.ACCOUNT}
    assert all(a.code is AttributionCode.OWNS for a in owned.values())
    phone = owned[IdKind.PHONE].identifier
    assert (phone.raw_text, phone.normalized) == ("90000 14471", "9000014471")
    assert phone.source == SourceRef("C-101", "fir.txt", 12)
    account = owned[IdKind.ACCOUNT].identifier
    assert account.normalized == "5010000019082"
    assert account.ifsc is not None
    assert account.ifsc.normalized == "SYNB0000123"


def test_bank_statement_holder_owns_the_account_and_counterparty_upi_is_a_phone() -> None:
    """Worked scenario, C-101/bank.csv:4 and :7."""
    row4 = (
        "TX4,2026-09-10,5010000019082,SYNB0000123,MOHD IRFAN,DR,9000021203@upi,upi,9500.00,100.00"
    )
    row7 = "TX7,2026-09-12,5010000019082,SYNB0000123,MOHD IRFAN,DR,9000028816@upi,upi,4500.00,50.00"
    text = pinned_file(
        {1: BANK_HEADER, 4: row4, 7: row7},
        lambda n: bank_row(n, account="5019000000001", holder="FILLER HOLDER"),
    )

    records = extract_case("C-101", {"bank.csv": text})

    holders = {p for p in records.persons if p.normalized == "mohammad irfan"}
    assert {p.source.line for p in holders} == {4, 7}
    owns = [
        a
        for a in records.attributions
        if a.identifier.normalized == "5010000019082" and a.code is AttributionCode.OWNS
    ]
    assert {a.source.line for a in owns} == {4, 7}
    assert all(a.holder.raw_text == "MOHD IRFAN" for a in owns)
    upi_phones = {
        i.normalized: i
        for i in records.identifiers
        if i.kind is IdKind.PHONE and i.source.file == "bank.csv"
    }
    assert upi_phones["9000021203"].raw_text == "9000021203@upi"
    assert upi_phones["9000028816"].source == SourceRef("C-101", "bank.csv", 7)
