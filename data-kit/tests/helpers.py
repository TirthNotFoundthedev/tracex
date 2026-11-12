from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

CASE_RE = re.compile(r"^C-[1-4]\d{2,}$")
PHONE_RE = re.compile(r"(?<!\d)(?:\+91[- ]?|0)?(\d{5}) ?(\d{5})(?!\d)")
ACCOUNT_RE = re.compile(r"(?<!\d)(50[01]\d{10})(?!\d)")
PLATE_RE = re.compile(
    r"(?<![A-Za-z0-9])([A-Za-z]{2})[ -]?(\d{2})[ -]?([A-Za-z]{1,3})[ -]?(\d{4})(?!\d)"
)

PLANTED_PHONE_RE = re.compile(r"^9000\d{6}$")
NOISE_PHONE_RE = re.compile(r"^9100\d{6}$")


def case_files(root: Path, batch: str = "b01") -> Iterator[tuple[str, str, Path]]:
    """Yield (case_id, file name, path) for every file of a batch, sorted."""
    base = root / "batches" / batch / "cases"
    if not base.is_dir():
        return
    for case_dir in sorted(base.iterdir()):
        for path in sorted(case_dir.iterdir()):
            yield case_dir.name, path.name, path


def all_files(root: Path) -> Iterator[tuple[str, str, str, Path]]:
    for batch in ("b01", "b02"):
        for case_id, name, path in case_files(root, batch):
            yield batch, case_id, name, path


def normalize_phone(text: str) -> str:
    return "".join(text.split("-")).replace("+91", "").replace(" ", "").lstrip("0")


def phones_in(line: str) -> list[str]:
    found: list[str] = []
    for match in PHONE_RE.finditer(line):
        found.append(match.group(1) + match.group(2))
    return found


def accounts_in(line: str) -> list[str]:
    return ACCOUNT_RE.findall(line)


def plates_in(line: str) -> list[str]:
    return ["".join(m).upper() for m in PLATE_RE.findall(line) if m[0].upper() != "IN"]


def numbered_lines(path: Path) -> list[tuple[int, str]]:
    return list(enumerate(path.read_text("utf-8").split("\n")[:-1], start=1))
