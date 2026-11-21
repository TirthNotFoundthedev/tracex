"""Placeholder names.

`is_placeholder` keeps names that only say "unknown" out of person matching: two bank rows
whose holder reads `NAME NOT KNOWN` must not link two people through their account.
"""

# Words that, alone or together, say a name is not known (English, romanised Hindi).
PLACEHOLDER_TOKENS = frozenset(
    {
        "unknown",
        "unidentified",
        "not",
        "known",
        "name",
        "stated",
        "available",
        "given",
        "provided",
        "na",
        "nil",
        "none",
        "person",
        "male",
        "female",
        "man",
        "woman",
        "holder",
        "customer",
        "account",
        "agyat",
        "vyakti",
        "nahi",
        "pata",
        "naam",
    }
)


def tokens(name: str) -> list[str]:
    return name.split()


def is_placeholder(name: str) -> bool:
    """True for an empty name or one made only of placeholder words (`name not known`)."""
    words = tokens(name)
    return not words or all(w in PLACEHOLDER_TOKENS for w in words)
