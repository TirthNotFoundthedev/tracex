"""Load order of a case's files: the order mentions are extracted in, and entity ids follow."""

import re

# Load order (data-kit section 2): fir, notes, sdr, cdr, bank; later batches (`notes-02.txt`,
# `cdr-02.csv`) after every baseline file, by number.
KINDS = ("fir", "notes", "sdr", "cdr", "bank")
FILE_NAME = re.compile(r"^(?P<kind>fir|notes|sdr|cdr|bank)(?:-(?P<batch>\d+))?\.(?:txt|csv)$")


def file_load_key(name: str) -> tuple[int, int, str]:
    """Sort key of a file name in load order; unknown names last, by name."""
    match = FILE_NAME.match(name)
    if match is None:
        return (10**6, 0, name)
    batch = int(match["batch"]) if match["batch"] else 1
    return (batch, KINDS.index(match["kind"]), name)
