"""Hedge and shared-number wording (data-kit Q7, AC-19; matching spec section 1, SHARED flag).

All phrases are lowercase and matched as whole words, case-insensitively. These lists are the
single place to change the wording rules. They are ruleset inputs, not admin config.
"""

import re

# A sentence containing any of these does not assert ownership: its attributions are flagged
# `hedged` and are never OWNS.
HEDGE_PHRASES: tuple[str, ...] = (
    # English
    "possibly",
    "probably",
    "perhaps",
    "maybe",
    "may be",
    "might be",
    "could be",
    "suspected to be",
    "believed to be",
    "appears to be",
    "seems to be",
    "unverified",
    "unconfirmed",
    "not confirmed",
    "partly illegible",
    "illegible",
    "unclear",
    # romanised Hindi
    "shayad",
    "sambhavtah",
    "apusht",
    "aspasht",
    # Hindi (Devanagari)
    "शायद",
    "संभवतः",
    "हो सकता है",
    "अपुष्ट",
    "अस्पष्ट",
)

# The subset that says the text itself is unclear or unverified. Every mention in such a
# sentence gets CONFIDENCE_HEDGED, so a record that rests on it fails gate G5 (AC-19).
LEGIBILITY_HEDGE_PHRASES: tuple[str, ...] = (
    "unverified",
    "unconfirmed",
    "not confirmed",
    "partly illegible",
    "illegible",
    "unclear",
    "apusht",
    "aspasht",
    "अपुष्ट",
    "अस्पष्ट",
)

# Wording that calls a number a shop, PCO, office, family or landline number (SHARED flag).
SHARED_WORDING: tuple[str, ...] = (
    "shop number",
    "shop no",
    "shop phone",
    "pco",
    "office number",
    "office phone",
    "office no",
    "family number",
    "family phone",
    "landline",
    "ghar ka number",
    "dukaan ka number",
    "दुकान का नंबर",
    "घर का नंबर",
)

_WORD_EDGE = r"(?<![\wऀ-ॿ]){}(?![\wऀ-ॿ])"


def _compile(phrases: tuple[str, ...]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(p) for p in sorted(phrases, key=len, reverse=True))
    return re.compile(_WORD_EDGE.format(f"(?:{alternatives})"), re.IGNORECASE)


_HEDGE = _compile(HEDGE_PHRASES)
_LEGIBILITY = _compile(LEGIBILITY_HEDGE_PHRASES)
_SHARED = _compile(SHARED_WORDING)


def is_hedged(text: str) -> bool:
    return _HEDGE.search(text) is not None


def is_illegible(text: str) -> bool:
    return _LEGIBILITY.search(text) is not None


def has_shared_wording(text: str) -> bool:
    return _SHARED.search(text) is not None
