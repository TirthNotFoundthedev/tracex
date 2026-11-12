"""Name, organisation and place normalization (matching spec section 2, name comparator contract).

The normalized form is for comparison only; the text as written is always kept beside it.
"""

import re
import unicodedata

from tracex_engine.normalize.devanagari import transliterate_devanagari

# Honorifics and kinship words dropped from person names (spec section 2), plus the spellings
# Devanagari transliteration produces for the same words.
HONORIFICS = frozenset(
    {
        "bhai",
        "ji",
        "sahab",
        "sahib",
        "shri",
        "smt",
        "shrimati",
        "shrimti",
        "mr",
        "bhaiya",
        "chacha",
        "urf",
    }
)
# Abbreviations expanded to the full name token (spec section 2).
ABBREVIATIONS = {"mohd": "mohammad", "md": "mohammad"}
# Legal and generic suffixes dropped from organisation names (spec section 1, ORG).
ORG_SUFFIXES = frozenset(
    {
        "pvt",
        "private",
        "ltd",
        "limited",
        "llp",
        "traders",
        "trading",
        "enterprises",
        "enterprise",
        "co",
        "company",
    }
)

_NON_WORD = re.compile(r"[^a-z0-9\s]")


def _tokens(text: str) -> list[str]:
    romanised = transliterate_devanagari(unicodedata.normalize("NFC", text)).lower()
    return _NON_WORD.sub(" ", romanised).split()


def normalize_name(text: str) -> str:
    """Romanised, lowercase, punctuation stripped, honorifics dropped, `mohd`/`md` expanded."""
    tokens = [ABBREVIATIONS.get(t, t) for t in _tokens(text) if t not in HONORIFICS]
    return " ".join(tokens)


def normalize_org_name(text: str) -> str:
    """Organisation name without `M/s`, legal or generic suffixes. May be empty."""
    tokens = _tokens(text)
    if tokens[:2] == ["m", "s"]:
        tokens = tokens[2:]
    elif tokens[:1] == ["ms"]:
        tokens = tokens[1:]
    return " ".join(t for t in tokens if t not in ORG_SUFFIXES)


def normalize_place(text: str) -> str:
    """Lowercase, romanised place text with punctuation as single spaces."""
    return " ".join(_tokens(text))
