"""The pairing every extracted value carries: what was written, and its comparable form."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Value:
    """A value as written (`raw_text`, never altered) next to its normalized form."""

    raw_text: str
    normalized: str
