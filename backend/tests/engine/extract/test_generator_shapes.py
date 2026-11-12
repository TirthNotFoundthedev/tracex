"""Review round 3: shapes the real data-kit generator writes (planted AC-05, AC-07, SF-05 lines)."""

import pytest

from tests.engine.extract.test_ownership_guards import attributions_of, in_fir, in_note, owners


def test_ka_number_with_trailing_hai_is_owns() -> None:
    line = "Ramesh Yadav ka number 9000022310 hai."

    for records in (in_note(line), in_fir(line)):
        assert owners(records, "9000022310") == {"ramesh yadav"}


@pytest.mark.parametrize("word", ["gram", "Gram", "ग्राम"])
def test_gram_is_a_locality_word(word: str) -> None:
    line = f"The accused Jaswinder Bhullar, aged 34, {word} Kherapur, fled the spot."
    [person] = [p for p in in_fir(line).persons if p.source.line == 12]

    assert person.locality is not None
    assert person.locality.normalized == "kherapur"
    assert person.locality.raw_text.endswith("Kherapur")


def test_an_alias_after_the_used_by_name_is_the_same_person() -> None:
    records = in_note("Number 9000022310 is used by Rakesh Dubey urf Monu.")

    assert owners(records, "9000022310") == {"rakesh dubey"}
    [person] = records.persons
    assert [a.normalized for a in person.aliases] == ["monu"]


def test_a_parenthetical_with_only_shared_wording_keeps_used_by_owns() -> None:
    records = in_note("Number 9000088120 is used by Mahesh Gupta (shop number, PCO).")

    assert owners(records, "9000088120") == {"mahesh gupta"}
    assert all(i.shared_wording for i in records.identifiers)


def test_a_parenthetical_naming_another_person_voids_used_by() -> None:
    records = in_note("Number 9000088120 is used by Mahesh Gupta (Salim Khan also).")

    assert owners(records, "9000088120") == set()
    assert attributions_of(records, "9000088120")


@pytest.mark.parametrize(
    ("text", "kind_value"),
    [
        ("Accused Ramesh Yadav, khata sankhya 5010000019082.", "5010000019082"),
        ("Accused Ramesh Yadav, vahan UP32AB1234.", "UP32AB1234"),
    ],
)
def test_romanised_account_and_vehicle_cues_are_owns(text: str, kind_value: str) -> None:
    assert owners(in_fir(text), kind_value) == {"ramesh yadav"}


def test_romanised_gender_and_birth_date_words() -> None:
    line = "Accused Ramesh Yadav, purush, janm tithi 12-04-1990, fled."
    [person] = [p for p in in_fir(line).persons if p.source.line == 12]

    assert person.gender is not None and person.gender.normalized == "male"
    assert person.dob is not None and person.dob.normalized == "1990-04-12"
    [woman] = [
        p for p in in_fir("Accused Sunita Devi, mahila, fled.").persons if p.source.line == 12
    ]
    assert woman.gender is not None and woman.gender.normalized == "female"


def test_a_devanagari_role_word_before_a_roman_name() -> None:
    [person] = [
        p
        for p in in_fir("आरोपी Mohd. Irfan, मोबाइल नंबर 9000051234 है।").persons
        if p.source.line == 12
    ]

    assert person.normalized == "mohammad irfan"


def test_devanagari_used_by_with_a_roman_name_and_upyog() -> None:
    records = in_note("नंबर 9000051234 Irfan bhai द्वारा उपयोग किया जाता है।")

    assert owners(records, "9000051234") == {"irfan"}


# --- shapes found by running the extractor over real generator output ---------------------------


@pytest.mark.parametrize(
    ("line", "owner", "values"),
    [
        (
            "अभियुक्त Nitin Sethi urf Anil, पुत्र Renu Sethi, उम्र 20 वर्ष, पुरुष, "
            "मोबाइल नंबर 9100202238, वाहन UP87ZZ5639।",
            "nitin sethi",
            {"9100202238", "UP87ZZ5639"},
        ),
        (
            "Witness Rahul Thakur urf Rajesh, aged 48, a/c 5019245368145 (IFSC SYNB0000123).",
            "rahul thakur",
            {"5019245368145"},
        ),
        (
            "गवाह Rajesh Srivastava, पुत्र Ravi Srivastava, ग्राम Yamunapar, खाता संख्या 5019437919770।",
            "rajesh srivastava",
            {"5019437919770"},
        ),
        (
            "Accused Ravi Saxena, male, Mohalla Peepal Wali Gali, mobile 91001 29857.",
            "ravi saxena",
            {"9100129857"},
        ),
        (
            "Witness Seema Garg urf Manoj, w/o Neelam Garg, village Bhagwanpur, mobile 9100861494.",
            "seema garg",
            {"9100861494"},
        ),
    ],
)
def test_alias_relative_and_locality_before_the_cue_keep_the_apposition(
    line: str, owner: str, values: set[str]
) -> None:
    records = in_fir(line)

    assert {p.normalized for p in records.persons if p.source.line == 12} == {owner}
    for value in values:
        assert owners(records, value) == {owner}


def test_a_three_word_locality_is_read_whole() -> None:
    line = "Accused Ravi Saxena, male, Mohalla Peepal Wali Gali, mobile 91001 29857."
    [person] = [p for p in in_fir(line).persons if p.source.line == 12]

    assert person.locality is not None and person.locality.normalized == "peepal wali gali"


def test_devanagari_used_by_with_a_roman_name_and_alias() -> None:
    records = in_note("नंबर 9100202238 Nitin Sethi urf Anil द्वारा उपयोग किया जाता है।")

    assert owners(records, "9100202238") == {"nitin sethi"}
