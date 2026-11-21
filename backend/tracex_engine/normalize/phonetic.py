"""Phonetic key and string ratio for name tokens (matching spec section 2, name comparator).

`phonetic_key` folds the spelling differences that Indian names show in Roman letters (and in
Devanagari-to-Roman output): `w`/`v`, `sh`/`s`, `x`/`ks`, doubled letters, and vowel changes.
Two tokens with the same key are treated as the same sound. It is built for comparing names and
for blocking, never for display.

`ratio` is the RapidFuzz `fuzz.ratio` score (as a fraction from 0 to 1): the normalized indel similarity, which is
twice the longest common subsequence over the two lengths. RapidFuzz is not a dependency of this
project, so the same measure is computed here.
"""

import re
from fractions import Fraction
from functools import lru_cache

_DIGRAPHS = re.compile(r"chh|ch|sh|kh|gh|jh|th|dh|bh|ph|ck")
_DIGRAPH_SOUND = {
    "chh": "c",
    "ch": "c",
    "sh": "s",
    "kh": "k",
    "gh": "g",
    "jh": "j",
    "th": "t",
    "dh": "d",
    "bh": "b",
    "ph": "f",
    "ck": "k",
}
_SINGLE_SOUND = str.maketrans({"x": "ks", "q": "k", "w": "v", "z": "j", "c": "k"})
_VOWELS = frozenset("aeiou")
_NOT_LETTER = re.compile(r"[^a-z]")

# The spellings of one given name that must read as one token (spec: mohd and md expand to
# mohammad; the rest are the usual variants). Used before comparison only.
CANONICAL_TOKENS = {
    "mohd": "mohammad",
    "md": "mohammad",
    "mohammed": "mohammad",
    "muhammad": "mohammad",
    "muhammed": "mohammad",
    "mohamed": "mohammad",
    "mohamad": "mohammad",
    "mohammad": "mohammad",
}


def canonical_token(token: str) -> str:
    return CANONICAL_TOKENS.get(token, token)


@lru_cache(maxsize=65536)
def phonetic_key(token: str) -> str:
    """Consonant skeleton of a lowercase Roman token; a leading vowel is kept as `a`.

    `jaswinder`, `jasvinder` and the Devanagari output `jasavindar` give `jsvndr`; `shaikh`,
    `sheikh` and `shekh` give `sk`; `saksena` and `saxena` give `sksn`; `salim` and `saleem` give
    `slm`; `ramesh` (`rms`) and `suresh` (`srs`) differ.
    """
    word = _NOT_LETTER.sub("", token.lower())
    word = _DIGRAPHS.sub(lambda m: _DIGRAPH_SOUND[m.group()], word).translate(_SINGLE_SOUND)
    folded: list[str] = []
    for index, char in enumerate(word):
        if char == "y" and index > 0:
            char = "i"
        if folded and folded[-1] == char:
            continue
        folded.append(char)
    if len(folded) > 1 and folded[-1] == "h" and folded[-2] in _VOWELS:
        folded.pop()
    if not folded:
        return ""
    head = "a" if folded[0] in _VOWELS else folded[0]
    return head + "".join(c for c in folded[1:] if c not in _VOWELS)


@lru_cache(maxsize=65536)
def _lcs_length(a: str, b: str) -> int:
    previous = [0] * (len(b) + 1)
    for char in a:
        current = [0]
        for j, other in enumerate(b, start=1):
            current.append(
                previous[j - 1] + 1 if char == other else max(previous[j], current[j - 1])
            )
        previous = current
    return previous[-1]


def ratio(a: str, b: str) -> Fraction:
    """RapidFuzz-style `fuzz.ratio` divided by 100, exact (0 to 1)."""
    total = len(a) + len(b)
    if total == 0:
        return Fraction(1)
    return Fraction(2 * _lcs_length(a, b), total)
