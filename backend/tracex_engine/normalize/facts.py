"""Comparisons of stated facts for Tier 2: phone transposition, age, DOB, locality.

Pure functions over normalized values (phone digits, ISO dates, age years, place text).
"""

from datetime import date

from tracex_engine.normalize.phonetic import phonetic_key
from tracex_engine.normalize.similarity import name_tokens

CLOSE_AGE_YEARS = 2
CONFLICT_AGE_YEARS = 5
HARD_CONFLICT_AGE_YEARS = 10


def phone_digitset_key(digits: str) -> str:
    """B2: the first two digits and the digits sorted. An adjacent swap keeps it."""
    return digits[:2] + "".join(sorted(digits))


def phones_transposed(a: str, b: str) -> bool:
    """Equal except that one pair of adjacent digits is swapped (the swapped digits differ)."""
    if len(a) != len(b) or a == b:
        return False
    differing = [i for i, (x, y) in enumerate(zip(a, b, strict=True)) if x != y]
    if len(differing) != 2 or differing[1] != differing[0] + 1:
        return False
    i, j = differing
    return a[i] == b[j] and a[j] == b[i]


def age_gap(ages_a: set[int], ages_b: set[int]) -> int | None:
    """Smallest difference in years between a stated age of one side and one of the other."""
    return min((abs(x - y) for x in ages_a for y in ages_b), default=None)


def parse_age(text: str) -> int | None:
    return int(text) if text.isdigit() else None


def parse_iso_date(text: str) -> date | None:
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def same_place(a: str, b: str) -> bool:
    """Same locality: equal text, or the same sequence of phonetic keys (a Hindi spelling and a
    Roman spelling of one village)."""
    if a == b:
        return True
    keys_a = [phonetic_key(t) for t in name_tokens(a)]
    keys_b = [phonetic_key(t) for t in name_tokens(b)]
    return keys_a == keys_b and all(len(k) >= 2 for k in keys_a)
