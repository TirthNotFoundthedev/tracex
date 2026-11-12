"""Review round 1 (Iyer, PR #15): wrong OWNS is the costly error, so every doubtful statement
must give no OWNS. Probe sentences are the ones quoted in the review."""

import pytest

from tests.engine.support import fir_file, note, notes_file
from tracex_engine.extract import (
    CONFIDENCE_CLEAR,
    CONFIDENCE_HEDGED,
    HEDGE_PHRASES,
    LEGIBILITY_HEDGE_PHRASES,
    Attribution,
    AttributionCode,
    CaseRecords,
    extract_case,
)

PHONE = "9000014471"
FAMILY = "9000022310"


def in_note(text: str) -> CaseRecords:
    return extract_case("C-1", {"notes.txt": notes_file("C-1", {3: note(text)})})


def in_fir(text: str) -> CaseRecords:
    return extract_case("C-1", {"fir.txt": fir_file("C-1", {12: text})})


def owners(records: CaseRecords, value: str) -> set[str]:
    return {
        a.holder.normalized
        for a in records.attributions
        if a.identifier.normalized == value and a.code is AttributionCode.OWNS
    }


def attributions_of(records: CaseRecords, value: str) -> list[Attribution]:
    return [a for a in records.attributions if a.identifier.normalized == value]


# --- 1. hedge scope --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        f"Number {PHONE} is used by Irfan bhai; unverified.",
        f"Number {PHONE} is used by Irfan bhai. (unverified)",
        f"Number {PHONE} is used by Irfan bhai. Not confirmed.",
        f"मोबाइल नंबर {PHONE} इरफ़ान द्वारा इस्तेमाल। अपुष्ट।",
        f"Unverified. Number {PHONE} is used by Irfan bhai.",
    ],
)
def test_a_note_hedge_anywhere_on_the_line_hedges_the_ownership(text: str) -> None:
    records = in_note(text)

    assert owners(records, PHONE) == set()
    [attribution] = attributions_of(records, PHONE)
    assert attribution.hedged is True
    assert attribution.code is AttributionCode.MENTIONED_WITH


@pytest.mark.parametrize(
    "text",
    [
        f"Number {PHONE} is used by Irfan bhai; unverified.",
        f"Number {PHONE} is used by Irfan bhai. (unverified)",
        f"Number {PHONE} is used by Irfan bhai. Not confirmed.",
    ],
)
def test_a_fir_hedge_in_a_following_fragment_hedges_the_ownership(text: str) -> None:
    records = in_fir(text)

    assert owners(records, PHONE) == set()
    assert all(a.hedged for a in attributions_of(records, PHONE))


def test_a_fir_hedge_in_a_later_sentence_with_its_own_identifier_does_not_spread_back() -> None:
    records = in_fir(f"Number {PHONE} is used by Irfan bhai. Plate UP32AB1234 is unverified.")

    assert owners(records, PHONE) == {"irfan"}
    phone = next(i for i in records.identifiers if i.normalized == PHONE)
    plate = next(i for i in records.identifiers if i.normalized == "UP32AB1234")
    assert (phone.confidence, plate.confidence) == (CONFIDENCE_CLEAR, CONFIDENCE_HEDGED)


def test_a_question_is_hedged() -> None:
    records = in_fir(f"Is number {PHONE} used by Irfan bhai?")

    assert owners(records, PHONE) == set()
    assert all(a.hedged for a in attributions_of(records, PHONE))


def test_legibility_hedge_in_the_previous_sentence_of_a_note_lowers_the_plate() -> None:
    records = in_note("Plate partly illegible. Noted as UP32CD9021.")

    [plate] = records.identifiers
    assert plate.confidence == CONFIDENCE_HEDGED


def test_legibility_hedge_in_a_following_fir_fragment_lowers_the_plate() -> None:
    records = in_fir("Plate noted as UP32CD9021; partly illegible.")

    [plate] = records.identifiers
    assert plate.confidence == CONFIDENCE_HEDGED


# --- 2. negation -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        f"The accused Mohd. Irfan does not use mobile {PHONE}.",
        f"The accused Mohd. Irfan denied that mobile {PHONE} is his.",
        f"Irfan bhai ka number {PHONE} nahi hai.",
        f"नंबर {PHONE} इरफ़ान द्वारा इस्तेमाल नहीं किया जाता।",
        f"Number {PHONE} is not used by Irfan bhai.",
        f"Irfan bhai ka number {PHONE} nahin hai.",
        f"Irfan bhai doesn't use number {PHONE}.",
    ],
)
def test_a_negated_sentence_gives_no_owns(text: str) -> None:
    for records in (in_note(text), in_fir(text)):
        assert owners(records, PHONE) == set()


# --- 3. binding ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "value"),
    [
        (f"Complainant Ramesh Kumar received a call from mobile {PHONE} on 5 September.", PHONE),
        (
            "Complainant Ramesh Kumar transferred Rs 50000 to a/c 5010000019082 on the same day.",
            "5010000019082",
        ),
        (f"Witness Salim Khan was called on number {PHONE} by the accused.", PHONE),
        (f"Accused Ramesh Yadav and witness Suresh Yadav, mobile {FAMILY}, were present.", FAMILY),
    ],
)
def test_a_cue_far_from_the_person_or_after_two_people_is_not_owns(text: str, value: str) -> None:
    records = in_fir(text)

    assert owners(records, value) == set()
    assert attributions_of(records, value)
    assert all(a.code is AttributionCode.MENTIONED_WITH for a in attributions_of(records, value))


def test_two_people_before_one_shared_identifier_each_get_mentioned_with() -> None:
    records = in_fir(
        f"Accused Ramesh Yadav and witness Suresh Yadav, mobile {FAMILY}, were present."
    )

    assert {a.holder.normalized for a in attributions_of(records, FAMILY)} == {
        "ramesh yadav",
        "suresh yadav",
    }


def test_sim_in_another_name_with_the_user_named_later_is_the_users_not_the_registrants() -> None:
    line = f"A SIM in the name of Kamla Devi, mobile {PHONE}, was used by accused Vikram Chauhan."
    records = in_fir(line)

    assert owners(records, PHONE) == {"vikram chauhan"}
    kamla = [a for a in attributions_of(records, PHONE) if a.holder.normalized == "kamla devi"]
    assert [a.code for a in kamla] == [AttributionCode.MENTIONED_WITH]


def test_facts_between_the_person_and_the_cue_keep_apposition() -> None:
    line = (
        f"The accused Ramesh Yadav s/o Gurmeet Yadav, aged 34, village Kherapur, mobile {FAMILY}."
    )

    assert owners(in_fir(line), FAMILY) == {"ramesh yadav"}


def test_two_separate_cue_identifier_pairs_after_one_person_are_both_owns() -> None:
    line = "The accused Ramesh Yadav, mobile 9000041001, a/c 5010000019082 and mobile 9000041002."

    records = in_fir(line)

    assert owners(records, "9000041001") == {"ramesh yadav"}
    assert owners(records, "5010000019082") == {"ramesh yadav"}
    assert owners(records, "9000041002") == {"ramesh yadav"}


# --- 4. used-by lists ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        f"Number {FAMILY} is used by Ramesh Yadav and Sunita Yadav.",
        f"Number {FAMILY} is used by Ramesh Yadav, Sunita Yadav and their son.",
    ],
)
def test_every_named_person_in_a_used_by_list_owns_the_identifier(text: str) -> None:
    assert owners(in_note(text), FAMILY) == {"ramesh yadav", "sunita yadav"}


@pytest.mark.parametrize(
    "text",
    [
        f"Number {FAMILY} is used by Ramesh Yadav or his brother.",
        f"Number {FAMILY} is used by Ramesh Yadav or Sunita Yadav.",
    ],
)
def test_or_in_a_used_by_list_is_a_hedge(text: str) -> None:
    records = in_note(text)

    assert owners(records, FAMILY) == set()
    assert attributions_of(records, FAMILY)
    assert all(a.hedged for a in attributions_of(records, FAMILY))


@pytest.mark.parametrize("who", ["accused Vikram Chauhan", "his brother Salim"])
def test_a_role_word_between_by_and_the_name_is_read(who: str) -> None:
    assert len(owners(in_note(f"Number {PHONE} is used by {who}."), PHONE)) == 1


# --- 5. pronoun ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        f"Accused Ramesh Yadav met witness Suresh Yadav. His number is {FAMILY}.",
        f"Accused Ramesh Yadav met witness Suresh Yadav, his number is {FAMILY}.",
    ],
)
def test_his_number_with_two_candidate_people_gives_no_owns(text: str) -> None:
    assert owners(in_fir(text), FAMILY) == set()


def test_his_number_never_crosses_lines() -> None:
    files = {
        "fir.txt": fir_file(
            "C-1", {12: "The accused Ramesh Yadav fled.", 13: f"His number is {FAMILY}."}
        )
    }

    assert owners(extract_case("C-1", files), FAMILY) == set()


# --- 6. hedge list ---------------------------------------------------------------------------

REQUIRED_HEDGES = (
    "allegedly",
    "reportedly",
    "suspected",
    "likely",
    "claims",
    "claimed",
    "doubtful",
    "to be verified",
    "not verified",
    "yet to be verified",
    "yet to be confirmed",
    "kathit",
    "sandeh",
    "कथित",
    "संभावित",
    "संदेह",
)


@pytest.mark.parametrize("phrase", REQUIRED_HEDGES)
def test_the_ruled_hedge_phrases_are_in_the_list(phrase: str) -> None:
    assert phrase in HEDGE_PHRASES


@pytest.mark.parametrize("phrase", HEDGE_PHRASES)
def test_every_hedge_phrase_removes_owns(phrase: str) -> None:
    records = in_note(f"Number {PHONE} is used by Irfan bhai, {phrase}.")

    assert owners(records, PHONE) == set()
    assert all(a.hedged for a in attributions_of(records, PHONE))


@pytest.mark.parametrize(
    "phrase",
    ["to be verified", "not verified", "yet to be verified", "yet to be confirmed", "unverified"],
)
def test_verification_wording_lowers_confidence(phrase: str) -> None:
    assert phrase in LEGIBILITY_HEDGE_PHRASES
    [plate] = in_note(f"Plate UP32CD9021 ({phrase}).").identifiers
    assert plate.confidence == CONFIDENCE_HEDGED
