"""Tier 2 comparators: phonetic key, ratio, name_sim, phone transposition, facts (spec 2, 3)."""

from decimal import Decimal
from fractions import Fraction

import pytest

from tracex_engine.normalize import (
    name_similarity,
    normalize_name,
    org_name_similarity,
    phone_digitset_key,
    phones_transposed,
    phonetic_key,
    ratio,
)
from tracex_engine.normalize.facts import age_gap, same_place
from tracex_engine.normalize.similarity import name_key, org_name_key, token_is_common


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("jaswinder", "jasvinder"),
        ("shaikh", "sheikh"),
        ("salim", "saleem"),
        ("saksena", "saxena"),
        ("irfan", "irfaan"),
        ("jasvinder", "jasavindar"),
        ("laxman", "lakshman"),
    ],
)
def test_spelling_variants_share_a_phonetic_key(a: str, b: str) -> None:
    assert phonetic_key(a) == phonetic_key(b) != ""


@pytest.mark.parametrize(
    ("a", "b"), [("ramesh", "suresh"), ("irfan", "imran"), ("sunil", "sushil"), ("ravi", "raju")]
)
def test_different_names_have_different_phonetic_keys(a: str, b: str) -> None:
    assert phonetic_key(a) != phonetic_key(b)


@pytest.mark.parametrize(
    ("written_a", "written_b"),
    [
        ("Mohd. Irfan", "मोहम्मद इरफ़ान"),
        ("सक्सेना", "Saxena"),
        ("जसविंदर भुल्लर", "Jasvinder Bhullar"),
        ("सलीम", "Saleem"),
        ("शेख", "Sheikh"),
    ],
)
def test_devanagari_and_roman_spellings_compare_as_matching_tokens(
    written_a: str, written_b: str
) -> None:
    result = name_similarity(normalize_name(written_a), normalize_name(written_b))

    assert result.name_sim >= Decimal("0.64")


def test_mohd_irfan_and_its_devanagari_spelling_are_equal() -> None:
    assert normalize_name("Mohd. Irfan") == normalize_name("मोहम्मद इरफ़ान") == "mohammad irfan"
    result = name_similarity("mohammad irfan", normalize_name("मोहम्मद इरफ़ान"))
    assert (result.name_sim, result.completeness, result.rarity) == (1, 1, 1)


def test_irfan_bhai_drops_the_kinship_word() -> None:
    assert normalize_name("Irfan bhai") == "irfan"


@pytest.mark.parametrize(
    ("a", "b", "name_sim", "completeness", "rarity"),
    [
        ("mohammad irfan", "irfan", "1.00", "0.75", "1"),
        ("jaswinder bhullar", "jasvinder bhullar", "0.94", "1", "1"),
        ("mohammed khan", "mohd khan", "1.00", "1", "0.4"),
        ("ramesh yadav", "suresh yadav", "0.50", "1", "0.4"),
        ("arjun mehra", "arjun mehra", "1.00", "1", "1"),
        ("ramesh", "suresh", "0", "1", "1"),
        ("sunil kumar", "kumar sunil", "1.00", "1", "1"),
    ],
)
def test_name_sim_completeness_and_rarity(
    a: str, b: str, name_sim: str, completeness: str, rarity: str
) -> None:
    result = name_similarity(a, b)

    assert (result.name_sim, result.completeness, result.rarity) == (
        Decimal(name_sim),
        Decimal(completeness),
        Decimal(rarity),
    )


def test_name_sim_is_symmetric_and_deterministic() -> None:
    names = ["mohammad irfan", "irfan", "jasvinder bhullar", "jaswinder singh bhullar", "ram lal"]
    for a in names:
        for b in names:
            assert name_similarity(a, b) == name_similarity(b, a)


def test_ratio_is_the_indel_ratio() -> None:
    assert ratio("abcd", "abcd") == 1
    assert ratio("jaswinder", "jasvinder") == Fraction(16, 18)
    assert ratio("", "") == 1
    assert ratio("abc", "xyz") == 0


def test_a_corpus_frequent_sound_makes_a_rare_name_common() -> None:
    frequent = frozenset({phonetic_key("rajesh")})

    assert not token_is_common("rajesh")
    assert token_is_common("rajesh", frequent)
    assert name_similarity("rajesh patel", "rajesh patel", frequent).rarity == 1
    assert name_similarity("rajesh", "rajesh", frequent).rarity == Decimal("0.4")


def test_common_tokens_include_every_ruleset_spelling() -> None:
    for token in ("mohd", "md", "muhammad", "khan", "sheikh", "shaikh", "kumar", "devi", "begum"):
        assert token_is_common(token), token


def test_org_names_ignore_a_respectful_prefix_and_need_something_left() -> None:
    both = org_name_similarity("shree balaji", "shri balaji")
    assert both is not None and both.name_sim == 1
    assert org_name_similarity("shree", "shri balaji") is None
    assert org_name_similarity("", "balaji") is None
    assert org_name_key("shree balaji") == org_name_key("shri balaji") == phonetic_key("balaji")
    assert org_name_key("shree") == ""


def test_whole_name_key_ignores_order_and_spelling() -> None:
    assert name_key("mohd khan") == name_key("khan mohammed")


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("9000081914", "9000081194", True),
        ("9000081194", "9000081914", True),
        ("9000014471", "9000014471", False),
        ("9000014471", "9000014741", True),
        ("9000014471", "9000041174", False),
        ("9000014471", "9000014417", True),
        ("9000081914", "9000081941", True),
        ("9000081914", "900008191", False),
        ("1122", "1122", False),
        ("9000081914", "9000081419", False),
    ],
)
def test_phones_transposed_only_for_one_adjacent_swap(a: str, b: str, expected: bool) -> None:
    assert phones_transposed(a, b) is expected


def test_adjacent_swaps_share_a_digit_set_key() -> None:
    assert phone_digitset_key("9000081914") == phone_digitset_key("9000081194")
    assert phone_digitset_key("9000081914") != phone_digitset_key("9000081915")


def test_age_gap_is_the_smallest_difference() -> None:
    assert age_gap({34}, {35}) == 1
    assert age_gap({34, 50}, {36}) == 2
    assert age_gap({34}, set()) is None


def test_same_place_by_text_or_by_sound() -> None:
    assert same_place("kherapur", "kherapur")
    assert same_place("kherapur", "kheerapur")
    assert not same_place("kherapur", "rampur")
    assert not same_place("ward 5", "ward 7")
