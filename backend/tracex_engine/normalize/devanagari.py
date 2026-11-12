"""Offline Devanagari to Roman transliteration for name matching.

Deliberately small (vertical slice, task P2.2): a deterministic rule table plus schwa deletion,
enough for the must-pass vectors of the matching spec. Long vowels are collapsed to short ones
because the output is only used to compare names, never to display them. Broader coverage and
phonetic keys belong to the Tier 2 comparator work (P3).
"""

import unicodedata

_INDEPENDENT_VOWELS = {
    "अ": "a",
    "आ": "a",
    "इ": "i",
    "ई": "i",
    "उ": "u",
    "ऊ": "u",
    "ऋ": "ri",
    "ए": "e",
    "ऐ": "ai",
    "ओ": "o",
    "औ": "au",
    "ऑ": "o",
}
_MATRAS = {
    "ा": "a",
    "ि": "i",
    "ी": "i",
    "ु": "u",
    "ू": "u",
    "ृ": "ri",
    "े": "e",
    "ै": "ai",
    "ो": "o",
    "ौ": "au",
    "ॉ": "o",
}
_CONSONANTS = {
    "क": "k",
    "ख": "kh",
    "ग": "g",
    "घ": "gh",
    "ङ": "n",
    "च": "ch",
    "छ": "chh",
    "ज": "j",
    "झ": "jh",
    "ञ": "n",
    "ट": "t",
    "ठ": "th",
    "ड": "d",
    "ढ": "dh",
    "ण": "n",
    "त": "t",
    "थ": "th",
    "द": "d",
    "ध": "dh",
    "न": "n",
    "प": "p",
    "फ": "ph",
    "ब": "b",
    "भ": "bh",
    "म": "m",
    "य": "y",
    "र": "r",
    "ल": "l",
    "व": "v",
    "श": "sh",
    "ष": "sh",
    "स": "s",
    "ह": "h",
}
_NUKTA = "़"
_NUKTA_FORMS = {
    "क": "q",
    "ख": "kh",
    "ग": "g",
    "ज": "z",
    "ड": "r",
    "ढ": "rh",
    "फ": "f",
}
_HALANT = "्"
_NASAL_MARKS = {"ं": "n", "ँ": "n"}
_VISARGA = "ः"
_DANDA = {"।", "॥"}


def _is_devanagari(char: str) -> bool:
    return "ऀ" <= char <= "ॿ"


class _Unit:
    """One consonant or independent vowel with what follows it inside the word."""

    __slots__ = ("consonant", "halant", "trail", "vowel")

    def __init__(self, consonant: str, vowel: str | None) -> None:
        self.consonant = consonant
        self.vowel = vowel
        self.halant = False
        self.trail = ""


def _units(word: str) -> list[_Unit]:
    units: list[_Unit] = []
    i = 0
    while i < len(word):
        char = word[i]
        i += 1
        if char in _INDEPENDENT_VOWELS:
            units.append(_Unit("", _INDEPENDENT_VOWELS[char]))
        elif char in _CONSONANTS:
            roman = _CONSONANTS[char]
            if i < len(word) and word[i] == _NUKTA:
                roman = _NUKTA_FORMS.get(char, roman)
                i += 1
            unit = _Unit(roman, None)
            if i < len(word) and word[i] in _MATRAS:
                unit.vowel = _MATRAS[word[i]]
                i += 1
            elif i < len(word) and word[i] == _HALANT:
                unit.halant = True
                i += 1
            units.append(unit)
        elif units and char in _NASAL_MARKS:
            units[-1].trail += _NASAL_MARKS[char]
        elif units and char == _VISARGA:
            units[-1].trail += "h"
    return units


def _keeps_schwa(units: list[_Unit], index: int) -> bool:
    """Schwa deletion: the inherent `a` goes at a word end and between two open syllables."""
    last = len(units) - 1
    if last == 0 or index == 0:
        return True
    if index == last:
        return False
    following = units[index + 1]
    return (
        units[index - 1].vowel is None
        or following.halant
        or (index + 1 == last and following.vowel is None)
    )


def _romanise_word(word: str) -> str:
    units = _units(word)
    parts: list[str] = []
    for index, unit in enumerate(units):
        if unit.vowel is not None:
            parts.append(unit.consonant + unit.vowel)
        elif unit.halant:
            parts.append(unit.consonant)
        elif _keeps_schwa(units, index):
            parts.append(unit.consonant + "a")
        else:
            parts.append(unit.consonant)
        parts.append(unit.trail)
    return "".join(parts)


def transliterate_devanagari(text: str) -> str:
    """Return `text` with every Devanagari word romanised; other characters pass through."""
    text = unicodedata.normalize("NFC", text)
    out: list[str] = []
    word: list[str] = []

    def flush() -> None:
        if word:
            out.append(_romanise_word("".join(word)))
            word.clear()

    for char in text:
        if _is_devanagari(char) and char not in _DANDA:
            word.append(char)
        else:
            flush()
            out.append("." if char in _DANDA else char)
    flush()
    return "".join(out)
