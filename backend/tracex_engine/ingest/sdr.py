"""SIM subscriber record parser: `sdr.csv` of the data kit (docs/specs/data-kit.md section 4.3)."""

from datetime import date

from tracex_engine.ingest.records import ParseResult, SdrRow, SourceRef
from tracex_engine.ingest.tabular import parse_csv_rows
from tracex_engine.normalize import Value, normalize_phone

SDR_HEADER = (
    "msisdn",
    "subscriber_name",
    "relative_name",
    "locality",
    "district",
    "activated_on",
)


def _build(source: SourceRef, raw_line: str, cells: dict[str, str]) -> SdrRow | str:
    phone = normalize_phone(cells["msisdn"])
    if phone is None:
        return f"msisdn {cells['msisdn']!r} is not a valid mobile number"
    if not cells["subscriber_name"].strip():
        return "subscriber_name is empty"
    activated = cells["activated_on"].strip()
    activated_on: date | None = None
    if activated:
        try:
            activated_on = date.fromisoformat(activated)
        except ValueError:
            return f"activated_on {cells['activated_on']!r} is not an ISO date (YYYY-MM-DD)"
    return SdrRow(
        source=source,
        raw_line=raw_line,
        msisdn=Value(cells["msisdn"], phone),
        subscriber_name=cells["subscriber_name"],
        relative_name=cells["relative_name"],
        locality=cells["locality"],
        district=cells["district"],
        activated_on=activated_on,
    )


def parse_sdr(case_id: str, file: str, text: str) -> ParseResult[SdrRow]:
    """Parse a subscriber file. Bad rows are reported in `errors` with line number and reason."""
    return parse_csv_rows(case_id, file, text, SDR_HEADER, _build)
