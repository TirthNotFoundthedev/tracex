"""Normalization: pure functions that make extracted values comparable without altering them.

Every function takes the text as written and returns the comparable form (or None when the text
is not a valid value of that kind). Callers keep the original beside the result using `Value`.

Exposed:
    Value                    raw text as written + normalized form
    normalize_phone          10-digit mobile, no country code or leading zero
    phone_from_upi           the phone behind a UPI handle such as `9000021203@upi`
    normalize_account        account digits, leading zeros kept
    normalize_ifsc           uppercase IFSC
    normalize_vehicle        `UP32AB1234`
    normalize_name           romanised lowercase person name, honorifics dropped, mohd expanded
    normalize_org_name       organisation name without legal and generic suffixes
    normalize_place          lowercase place text
    parse_date               the date formats the data kit writes
    transliterate_devanagari offline Devanagari to Roman (vertical-slice coverage only)
    phonetic_key, ratio      sound-alike key of a name token; RapidFuzz-style string ratio
    name_similarity          `name_sim` with completeness and rarity (Tier 2)
    org_name_similarity      `name_sim` of reduced organisation names
    phones_transposed        phones equal except one adjacent pair of digits swapped
"""

from tracex_engine.normalize.dates import DATE_PATTERN, parse_date
from tracex_engine.normalize.devanagari import transliterate_devanagari
from tracex_engine.normalize.facts import phone_digitset_key, phones_transposed
from tracex_engine.normalize.identifiers import (
    normalize_account,
    normalize_ifsc,
    normalize_phone,
    normalize_vehicle,
    phone_from_upi,
)
from tracex_engine.normalize.names import (
    DEV_ORG_SUFFIXES,
    HONORIFICS,
    ORG_SUFFIXES,
    normalize_name,
    normalize_org_name,
    normalize_place,
)
from tracex_engine.normalize.phonetic import phonetic_key, ratio
from tracex_engine.normalize.similarity import (
    NameSimilarity,
    name_similarity,
    org_name_similarity,
)
from tracex_engine.normalize.values import Value

__all__ = [
    "DATE_PATTERN",
    "DEV_ORG_SUFFIXES",
    "HONORIFICS",
    "ORG_SUFFIXES",
    "NameSimilarity",
    "Value",
    "normalize_account",
    "normalize_ifsc",
    "normalize_name",
    "normalize_org_name",
    "normalize_phone",
    "normalize_place",
    "normalize_vehicle",
    "name_similarity",
    "org_name_similarity",
    "parse_date",
    "phone_digitset_key",
    "phones_transposed",
    "phone_from_upi",
    "phonetic_key",
    "ratio",
    "transliterate_devanagari",
]
