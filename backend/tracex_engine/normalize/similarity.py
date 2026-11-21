"""Name comparator `name_sim` with completeness and rarity (matching spec section 2).

    name_sim     = (mean ratio of matched token pairs) x |matched| / |tokens of the shorter name|
    completeness = 0.75 if the shorter name has one token, else 1.0
    rarity       = 1.0 if any matched token is non-common, else 0.4

Two tokens match when they are equal, their phonetic keys are equal, or their ratio is at
least 0.85. Names are the normalized (romanised, lowercase, honorifics dropped) forms produced
by `normalize_name` and `normalize_org_name`. `name_sim` is rounded half up to two decimals:
it is a value shown to the officer ("match 0.94 out of 1") and the only rounding before the
weight is applied.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from tracex_engine.normalize.phonetic import canonical_token, phonetic_key, ratio

MATCH_RATIO = Fraction(85, 100)
RARITY_COMMON = Decimal("0.4")
COMPLETENESS_ONE_TOKEN = Decimal("0.75")
TWO_PLACES = Decimal("0.01")

# Ruleset list of common name tokens (spec section 2; mohammad covers mohd, md and variants).
COMMON_TOKENS = frozenset(
    {
        "mohammad",
        "kumar",
        "kumari",
        "singh",
        "kaur",
        "devi",
        "lal",
        "ram",
        "prasad",
        "chand",
        "das",
        "khan",
        "ali",
        "ahmed",
        "shaikh",
        "ansari",
        "sharma",
        "yadav",
        "begum",
        "bai",
        "ben",
    }
)
COMMON_KEYS = frozenset(key for token in COMMON_TOKENS if len(key := phonetic_key(token)) >= 2)
# Respectful prefixes of an organisation name (`Shree Balaji`, `Shri Balaji`): decoration, not
# part of the name, so they are left out when two organisation names are compared.
ORG_PREFIXES = frozenset({"shri", "shree", "sri", "sree", "shrii"})


def token_is_common(token: str, frequent_keys: frozenset[str] = frozenset()) -> bool:
    """On the ruleset list (by spelling or sound), or its key is frequent in the corpus."""
    token = canonical_token(token)
    key = phonetic_key(token)
    return token in COMMON_TOKENS or (len(key) >= 2 and key in COMMON_KEYS | frequent_keys)


def name_tokens(name: str) -> list[str]:
    return [canonical_token(t) for t in name.split()]


def org_tokens(name: str) -> list[str]:
    return [t for t in name_tokens(name) if t not in ORG_PREFIXES]


def token_match(a: str, b: str) -> Fraction | None:
    """The ratio of two tokens if they match, else None.

    Equal tokens score 1 and tokens with ratio >= 0.85 score their ratio. Tokens that only sound
    alike (equal phonetic keys, a lower ratio: `salim` and `saleem`, or a Hindi and a Roman
    spelling) score 0.85, the lowest ratio that counts as a match, so a spelling difference does
    not make a matching token count for less than a near miss.
    """
    if a == b:
        return Fraction(1)
    score = ratio(a, b)
    if score >= MATCH_RATIO:
        return score
    key = phonetic_key(a)
    if min(len(a), len(b)) >= 2 and len(key) >= 2 and key == phonetic_key(b):
        return MATCH_RATIO
    return None


@dataclass(frozen=True)
class NameSimilarity:
    name_sim: Decimal
    completeness: Decimal
    rarity: Decimal

    @property
    def strength(self) -> Decimal:
        return self.name_sim * self.completeness * self.rarity


NO_SIMILARITY = NameSimilarity(Decimal(0), Decimal(1), Decimal(1))


def _tokens_similarity(
    left: list[str], right: list[str], frequent_keys: frozenset[str]
) -> NameSimilarity:
    if not left or not right:
        return NO_SIMILARITY
    options = []
    for i, x in enumerate(left):
        for j, y in enumerate(right):
            score = token_match(x, y)
            if score is not None:
                options.append((-score, x, y, i, j))
    used_left: set[int] = set()
    used_right: set[int] = set()
    matched: list[tuple[Fraction, str]] = []
    for negative, x, _, i, j in sorted(options):
        if i not in used_left and j not in used_right:
            used_left.add(i)
            used_right.add(j)
            matched.append((-negative, x))
    if not matched:
        return NO_SIMILARITY
    shorter = min(len(left), len(right))
    mean = sum((score for score, _ in matched), Fraction(0)) / len(matched)
    sim = mean * len(matched) / shorter
    name_sim = (Decimal(sim.numerator) / Decimal(sim.denominator)).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )
    completeness = COMPLETENESS_ONE_TOKEN if shorter == 1 else Decimal(1)
    rare = any(not token_is_common(token, frequent_keys) for _, token in matched)
    return NameSimilarity(name_sim, completeness, Decimal(1) if rare else RARITY_COMMON)


def name_similarity(a: str, b: str, frequent_keys: frozenset[str] = frozenset()) -> NameSimilarity:
    """`name_sim`, completeness and rarity of two normalized person names."""
    return _tokens_similarity(name_tokens(a), name_tokens(b), frequent_keys)


def org_name_similarity(a: str, b: str) -> NameSimilarity | None:
    """`name_sim` of two reduced organisation names; None when either is empty after reduction."""
    left, right = org_tokens(a), org_tokens(b)
    if not left or not right:
        return None
    return _tokens_similarity(left, right, frozenset())


def name_key(name: str) -> str:
    """Whole-name phonetic key (B5): the sorted phonetic keys of its tokens."""
    return " ".join(sorted(phonetic_key(t) for t in name_tokens(name)))


def org_name_key(name: str) -> str:
    """Phonetic key of a reduced organisation name (B7); empty if nothing is left."""
    return " ".join(sorted(phonetic_key(t) for t in org_tokens(name)))
