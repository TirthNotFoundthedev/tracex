"""Date parsing for the formats the data kit writes."""

import re
from datetime import date

_MONTH_NAMES = (
    ("jan", "january"),
    ("feb", "february"),
    ("mar", "march"),
    ("apr", "april"),
    ("may",),
    ("jun", "june"),
    ("jul", "july"),
    ("aug", "august"),
    ("sep", "sept", "september"),
    ("oct", "october"),
    ("nov", "november"),
    ("dec", "december"),
)
_MONTHS = {name: number for number, names in enumerate(_MONTH_NAMES, start=1) for name in names}
_ISO = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_DMY = re.compile(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})")
_DAY_MONTH_YEAR = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\.?,?\s+(\d{4})")

DATE_PATTERN = (
    r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}|\d{1,2}\s+[A-Za-z]{3,9}\.?,?\s+\d{4}"
)


def _build(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_date(text: str) -> date | None:
    """Parse `YYYY-MM-DD`, `DD-MM-YYYY`, `DD/MM/YYYY` or `12 April 1990`, else None."""
    text = text.strip()
    if match := _ISO.fullmatch(text):
        return _build(int(match[1]), int(match[2]), int(match[3]))
    if match := _DMY.fullmatch(text):
        return _build(int(match[3]), int(match[2]), int(match[1]))
    if match := _DAY_MONTH_YEAR.fullmatch(text):
        month = _MONTHS.get(match[2].lower())
        return _build(int(match[3]), month, int(match[1])) if month else None
    return None
