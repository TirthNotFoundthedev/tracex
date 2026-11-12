"""Builders for synthetic case files with content pinned to exact physical lines."""

from collections.abc import Callable, Mapping

BANNER = "SYNTHETIC DATA TRACEX-SYN/1 - NOT A REAL RECORD"

CDR_HEADER = "call_id,start_time,duration_sec,calling_no,called_no,call_type,cell_id,tower_place"
BANK_HEADER = (
    "txn_id,txn_date,account_no,ifsc,account_holder,direction,counterparty,narration,"
    "amount_inr,balance_inr"
)
SDR_HEADER = "msisdn,subscriber_name,relative_name,locality,district,activated_on"


def pinned_file(
    pins: Mapping[int, str], filler: Callable[[int], str], last: int | None = None
) -> str:
    """Return a file whose line `n` is `pins[n]`, with `filler(n)` on every other line."""
    end = last if last is not None else max(pins)
    lines = [pins.get(n, filler(n)) for n in range(1, end + 1)]
    return "\n".join(lines) + "\n"


def fir_file(case_id: str, narrative: Mapping[int, str], last: int | None = None) -> str:
    """FIR in the data-kit frame: header on lines 1-9, `NARRATIVE:` on 11, text from line 12."""
    frame = {
        1: BANNER,
        2: f"FIR No: SYN-{case_id}/2026",
        3: "Date of FIR: 2026-09-20",
        4: "Date of occurrence: 2026-09-18",
        5: "Police Station: PS Rivergate Central",
        6: "District: Rivergate",
        7: "State: Northvale",
        8: "Sections: 420, 406",
        9: "Complainant: Sunil Arora, aged 52",
        10: "",
        11: "NARRATIVE:",
    }
    return pinned_file({**frame, **narrative}, lambda n: "The matter is under inquiry.", last)


def notes_file(case_id: str, notes: Mapping[int, str], last: int | None = None) -> str:
    """Officer notes in the data-kit frame: banner, title, then one note per line from line 3."""
    frame = {1: BANNER, 2: f"# Officer notes, case {case_id}"}
    return pinned_file(
        {**frame, **notes},
        lambda n: "[2026-10-01] SI AB: Routine patrol, nothing further to report.",
        last,
    )


def note(text: str, date: str = "2026-10-02", author: str = "SI RV") -> str:
    return f"[{date}] {author}: {text}"


def cdr_row(
    n: int,
    calling: str = "9100000001",
    called: str = "9100000002",
    when: str = "2026-09-18T10:00:00+05:30",
    place: str = "Hillcrest Market",
    call_type: str = "VOICE",
) -> str:
    return f"SYN-C-201-{n},{when},60,{calling},{called},{call_type},CELL{n},{place}"


def bank_row(
    n: int,
    account: str = "5019000000001",
    ifsc: str = "SYNB0000123",
    holder: str = "FILLER HOLDER",
    direction: str = "DR",
    counterparty: str = "5019000000002",
) -> str:
    return (
        f"TX{n},2026-09-18,{account},{ifsc},{holder},{direction},{counterparty},"
        f"transfer,1500.00,20000.50"
    )
