"""Review round 2 (Iyer, PR #15): OWNS only from a closed set of clean patterns.

Every probe sentence quoted in the round-2 review is a test, plus a property-style check that
inserting an extra name, hedge or negation word anywhere never gives OWNS to a new person.
"""

import pytest

from tests.engine.extract.test_ownership_guards import (
    PHONE,
    attributions_of,
    in_fir,
    in_note,
    owners,
)
from tracex_engine.extract import (
    CONFIDENCE_CLEAR,
    HEDGE_PHRASES,
    AttributionCode,
)

FAMILY = "9000022310"

# --- blocker 1: a used-by list member counts only if it ends the clause ------------------------


@pytest.mark.parametrize(
    "text",
    [
        f"Number {PHONE} is used by Irfan bhai, Salim Khan's brother.",
        f"Number {PHONE} is used by Irfan bhai, Rakesh Kumar told police.",
        f"Number {PHONE} is used by Irfan bhai and Salim Khan visited him.",
    ],
)
def test_a_name_that_does_not_end_the_used_by_list_makes_the_whole_list_ambiguous(
    text: str,
) -> None:
    for records in (in_note(text), in_fir(text)):
        assert owners(records, PHONE) == set()
        assert attributions_of(records, PHONE)
        assert all(a.hedged for a in attributions_of(records, PHONE))


def test_a_possessive_is_never_part_of_a_name() -> None:
    records = in_note(f"Number {PHONE} is used by Irfan bhai, Salim Khan's brother.")

    assert all("'" not in p.raw_text for p in records.persons)


def test_a_dangling_connector_after_a_clean_list_still_gives_owns() -> None:
    records = in_note(f"Number {FAMILY} is used by Ramesh Yadav, Sunita Yadav and their son.")

    assert owners(records, FAMILY) == {"ramesh yadav", "sunita yadav"}


# --- blocker 2: connectors and role words in Hindi ---------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        f"आरोपी रमेश यादव और गवाह सुरेश यादव, मोबाइल {FAMILY}, मौजूद थे।",
        f"आरोपी रमेश यादव तथा गवाह सुरेश यादव, मोबाइल {FAMILY}, मौजूद थे।",
        f"Aaropi Ramesh Yadav aur gawah Suresh Yadav, mobile {FAMILY}, maujood the.",
        f"Aaropi Ramesh Yadav tatha gawah Suresh Yadav, mobile {FAMILY}, maujood the.",
    ],
)
def test_two_people_joined_in_hindi_before_one_identifier_are_ambiguous(text: str) -> None:
    records = in_fir(text)

    assert owners(records, FAMILY) == set()
    assert len({a.holder.normalized for a in attributions_of(records, FAMILY)}) == 2


# --- blocker 3: a hedge-only fragment covers both sides ----------------------------------------


def test_a_hedge_only_fragment_before_the_sentence_hedges_it() -> None:
    records = in_fir(f"Not verified. Accused Mohd. Irfan, mobile {PHONE}, absconding.")

    assert owners(records, PHONE) == set()
    assert all(a.hedged for a in attributions_of(records, PHONE))


# --- blocker 4: hedge variants, and no hedge word inside a name ---------------------------------

NEW_HEDGES = (
    "thought to be",
    "presumably",
    "rumoured",
    "rumored",
    "cannot be confirmed",
    "could not be confirmed",
    "could not be verified",
    "संभवत",
    "लगता है",
    "शक",
    "sambhavat",
    "shaayad",
    "shak",
    "lagta hai",
)


@pytest.mark.parametrize("phrase", NEW_HEDGES)
def test_round_2_hedge_phrases_are_listed_and_remove_owns(phrase: str) -> None:
    assert phrase in HEDGE_PHRASES
    records = in_note(f"Number {PHONE} is used by Irfan bhai, {phrase}.")

    assert owners(records, PHONE) == set()


@pytest.mark.parametrize(
    "text",
    [
        f"नंबर {PHONE} संभवत इरफ़ान द्वारा इस्तेमाल",
        f"लगता है नंबर {PHONE} इरफ़ान द्वारा इस्तेमाल किया जाता है",
        f"नंबर {PHONE} शक है इरफ़ान द्वारा इस्तेमाल",
        f"नंबर {PHONE} कथित रूप से इरफ़ान द्वारा इस्तेमाल",
        f"नंबर {PHONE} संभावित इरफ़ान द्वारा इस्तेमाल",
    ],
)
def test_a_devanagari_hedge_word_is_never_part_of_a_name_and_gives_no_owns(text: str) -> None:
    for records in (in_note(text), in_fir(text)):
        assert owners(records, PHONE) == set()
        assert all(
            "sambhav" not in p.normalized and "lagta" not in p.normalized for p in records.persons
        )


def test_a_devanagari_name_never_starts_mid_word() -> None:
    records = in_fir("रमेश और सुरेश का नंबर 9000022310 है।")

    assert all(not p.normalized.startswith("r suresh") for p in records.persons)
    assert owners(records, "9000022310") == set()


# --- minor 1: ka number is an ownership shape --------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        f"Irfan bhai ka number {PHONE} hai.",
        f"Irfan bhai ka mobile number {PHONE} hai.",
        f"इरफ़ान का नंबर {PHONE} है।",
        f"इरफ़ान का मोबाइल नंबर {PHONE} है।",
    ],
)
def test_name_ka_number_identifier_is_owns(text: str) -> None:
    for records in (in_note(text), in_fir(text)):
        assert owners(records, PHONE) == {"irfan"}
        [attribution] = attributions_of(records, PHONE)
        assert attribution.hedged is False


@pytest.mark.parametrize(
    "text",
    [
        f"Irfan bhai ka number {PHONE} hai, Salim Khan visited him.",
        f"Accused Ramesh Yadav aur Suresh Yadav ka number {FAMILY} hai.",
        f"Irfan bhai ka number shayad {PHONE} hai.",
        f"Irfan bhai ka number {PHONE} nahi hai.",
    ],
)
def test_ka_number_with_anything_extra_is_not_owns(text: str) -> None:
    assert owners(in_fir(text), PHONE) == set()
    assert owners(in_fir(text), FAMILY) == set()


# --- minor 3: copula between the name and the cue ----------------------------------------------


def test_a_verb_between_the_name_and_the_cue_is_not_owns() -> None:
    records = in_fir("Complainant Ramesh Kumar is mobile 9000014471 caller's target.")

    assert owners(records, "9000014471") == set()


# --- the worked scenario keeps its OWNS at 0.9 ---------------------------------------------------


def test_worked_scenario_lines_still_give_owns_at_full_confidence() -> None:
    note_records = in_note(f"Number {PHONE} is used by Irfan bhai.")
    fir_records = in_fir(
        "The accused Mohd. Irfan, mobile 90000 14471, a/c 5010000019082 (IFSC SYNB0000123), "
        "is alleged to have collected money through a fake investment link."
    )

    assert owners(note_records, PHONE) == {"irfan"}
    assert owners(fir_records, PHONE) == {"mohammad irfan"}
    assert owners(fir_records, "5010000019082") == {"mohammad irfan"}
    mentions = [*note_records.identifiers, *fir_records.identifiers]
    assert all(m.confidence == CONFIDENCE_CLEAR for m in mentions)
    assert all(
        a.code is AttributionCode.OWNS
        for a in [*note_records.attributions, *fir_records.attributions]
    )


# --- property: an inserted extra name, hedge or negation never creates a new owner ---------------

PATTERNS = (
    ("The accused Ramesh Yadav, mobile 9000022310, a/c 5010000019082 fled.", {"ramesh yadav"}),
    ("Number 9000022310 is used by Ramesh Yadav.", {"ramesh yadav"}),
    (
        "Number 9000022310 is used by Ramesh Yadav and Sunita Yadav.",
        {"ramesh yadav", "sunita yadav"},
    ),
    ("Ramesh Yadav ka number 9000022310 hai.", {"ramesh yadav"}),
    ("रमेश यादव का नंबर 9000022310 है।", {"ramesh yadav"}),
    ("मोबाइल नंबर 9000022310 रमेश यादव द्वारा इस्तेमाल किया जाता है।", {"ramesh yadav"}),
)
INSERTIONS = (
    "Salim Khan",
    "Accused Salim Khan",
    "witness Salim Khan",
    "सलीम खान",
    "आरोपी सलीम खान",
    "possibly",
    "शायद",
    "not",
    "नहीं",
    "and",
    "told police",
)


def _is_name_token(token: str) -> bool:
    letters = token.strip(".,;()")
    return bool(letters) and (letters[0].isupper() or "ऀ" <= letters[0] <= "ॿ")


NAME_INSERTIONS = frozenset(INSERTIONS[:5])


def _variants(sentence: str, insertion: str) -> list[str]:
    tokens = sentence.split(" ")
    variants = []
    for position in range(len(tokens) + 1):
        left = tokens[position - 1] if position else ""
        right = tokens[position] if position < len(tokens) else ""
        touches = _is_name_token(left) or _is_name_token(right)
        inside = _is_name_token(left) and _is_name_token(right)
        if inside or (touches and insertion in NAME_INSERTIONS):
            continue  # the written name itself would change
        variants.append(" ".join([*tokens[:position], insertion, *tokens[position:]]))
    return variants


@pytest.mark.parametrize(("sentence", "original"), PATTERNS)
@pytest.mark.parametrize("insertion", INSERTIONS)
def test_an_insertion_never_creates_an_owner_outside_the_original_list(
    sentence: str, original: set[str], insertion: str
) -> None:
    identifiers = {"9000022310", "5010000019082"}
    for variant in _variants(sentence, insertion):
        records = in_fir(variant)
        for value in identifiers:
            assert owners(records, value) <= original, variant
