"""Load order of a case's files and the sort key of entity ids (matching spec C5)."""

import re

# Load order (data-kit section 2): fir, notes, sdr, cdr, bank; later batches (`notes-02.txt`)
# after every baseline file, by number. Mirrors the extractor's reading order.
_KINDS = ("fir", "notes", "sdr", "cdr", "bank")
_FILE_NAME = re.compile(r"^(?P<kind>fir|notes|sdr|cdr|bank)(?:-(?P<batch>\d+))?\.(?:txt|csv)$")
_ENTITY_ID = re.compile(r"^C-(?P<district>\d)(?P<sequence>\d+):(?P<ordinal>\d+)$")


def file_load_key(name: str) -> tuple[int, int, str]:
    """Sort key of a file name in load order; unknown names last, by name."""
    match = _FILE_NAME.match(name)
    if match is None:
        return (10**6, 0, name)
    batch = int(match["batch"]) if match["batch"] else 1
    return (batch, _KINDS.index(match["kind"]), name)


def case_sort_key(case_id: str) -> tuple[int, int]:
    """Case ids compare numerically: district digit, then sequence (`C-150` < `C-1100`)."""
    match = _ENTITY_ID.match(f"{case_id}:0")
    if match is None:
        raise ValueError(f"not a case id: {case_id!r}")
    return (int(match["district"]), int(match["sequence"]))


def entity_sort_key(entity_id: str) -> tuple[int, int, int]:
    """Sort key that makes entity ids increase in load order (case, then first mention)."""
    case_id, separator, ordinal = entity_id.rpartition(":")
    if not separator or not ordinal.isdigit():
        raise ValueError(f"not an entity id: {entity_id!r}")
    district, sequence = case_sort_key(case_id)
    return (district, sequence, int(ordinal))
