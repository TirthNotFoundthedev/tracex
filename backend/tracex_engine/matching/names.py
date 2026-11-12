"""Name checks the Tier 1 matcher needs before the Tier 2 name comparator exists.

`exact_token_similarity` is a stand-in for `name_sim` used only by the MULTI_USER flag. It
counts whole equal tokens only, so it is never above the real `name_sim` (an equal token has
equal phonetic keys and ratio 100). A lower similarity flags more identifiers as MULTI_USER,
which only weakens person evidence: the safe side. It is never used as positive evidence.

`is_placeholder` keeps names that only say "unknown" out of person matching: two bank rows
whose holder reads `NAME NOT KNOWN` must not link two people through their account.
"""

from decimal import Decimal

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


def exact_token_similarity(a: str, b: str) -> Decimal:
    """Share of the shorter name's tokens found, as whole equal tokens, in the other name."""
    left, right = tokens(a), tokens(b)
    if not left or not right:
        return Decimal(0)
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    pool = list(longer)
    matched = 0
    for token in shorter:
        if token in pool:
            pool.remove(token)
            matched += 1
    return Decimal(matched) / Decimal(len(shorter))


def best_exact_similarity(names_a: set[str], names_b: set[str]) -> Decimal:
    """Highest stand-in similarity over main names and aliases of both sides."""
    return max(
        (exact_token_similarity(a, b) for a in names_a for b in names_b),
        default=Decimal(0),
    )
