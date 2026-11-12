"""Review round 4 (Iyer, re-review 2): the identifier's right-hand side is part of the pattern."""

import pytest

from tests.engine.extract.test_ownership_guards import attributions_of, in_fir, in_note, owners
from tests.engine.support import BANK_HEADER, bank_row, pinned_file
from tracex_engine.extract import AttributionCode, extract_case

PHONE = "9000014471"
ACCOUNT = "5010000019082"

# --- blocker: what follows the identifier ------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "value"),
    [
        (f"Shikayatkarta Ramesh Kumar, mobile number {PHONE} se dhamki mili.", PHONE),
        (f"Shikayatkarta Ramesh Kumar, mobile number {PHONE} par call aaya.", PHONE),
        (f"शिकायतकर्ता रमेश कुमार, मोबाइल नंबर {PHONE} से धमकी मिली।", PHONE),
        (f"शिकायतकर्ता रमेश कुमार, खाता संख्या {ACCOUNT} में पैसे भेजे।", ACCOUNT),
        (f"Complainant Ramesh Kumar, mobile {PHONE} of the accused, was threatened.", PHONE),
        (f"Complainant Ramesh Kumar, mobile {PHONE} belonging to the accused, was cheated.", PHONE),
        (f"Complainant Ramesh Kumar, a/c {ACCOUNT} to which he sent money, filed a case.", ACCOUNT),
    ],
)
def test_words_after_the_identifier_that_can_reverse_ownership_void_it(
    text: str, value: str
) -> None:
    records = in_fir(text)

    assert owners(records, value) == set()
    assert attributions_of(records, value)
    assert all(a.code is AttributionCode.MENTIONED_WITH for a in attributions_of(records, value))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (f"The accused Ramesh Yadav, mobile {PHONE}.", {PHONE}),
        (f"The accused Ramesh Yadav, mobile {PHONE} hai.", {PHONE}),
        (f"आरोपी रमेश यादव, मोबाइल नंबर {PHONE} है।", {PHONE}),
        (f"The accused Ramesh Yadav, mobile {PHONE}, a/c {ACCOUNT}.", {PHONE, ACCOUNT}),
        (f"The accused Ramesh Yadav, mobile {PHONE}, aged 34, a/c {ACCOUNT}.", {PHONE, ACCOUNT}),
        (f"The accused Ramesh Yadav (mobile {PHONE}).", {PHONE}),
        (
            f"The accused Ramesh Yadav, a/c {ACCOUNT} (IFSC SYNB0000123), mobile {PHONE}.",
            {PHONE, ACCOUNT},
        ),
        (
            f"The accused Ramesh Yadav, mobile {PHONE}, and witness Sunil Verma, "
            "mobile 9000022311.",
            {PHONE, "9000022311"},
        ),
    ],
)
def test_clean_endings_keep_owns(text: str, expected: set[str]) -> None:
    records = in_fir(text)

    for value in expected:
        assert owners(records, value), value


def test_a_verb_after_the_identifier_is_not_a_clean_ending() -> None:
    records = in_fir(f"The accused Ramesh Yadav, mobile {PHONE}, absconded.")

    assert owners(records, PHONE) == set()


@pytest.mark.parametrize(
    "tail",
    ["se", "par", "में", "से", "को", "का", "of", "belonging to", "to", "from", "which", "owned by"],
)
def test_any_word_directly_after_the_identifier_voids_apposition(tail: str) -> None:
    for value, cue in ((PHONE, "mobile"), (ACCOUNT, "a/c")):
        records = in_fir(f"The accused Ramesh Yadav, {cue} {value} {tail} someone.")

        assert owners(records, value) == set(), (value, tail)


def test_his_number_with_trailing_words_is_void() -> None:
    records = in_fir(f"The accused Ramesh Yadav fled. His number is {PHONE} se call aaya.")

    assert owners(records, PHONE) == set()


# --- follow-ups --------------------------------------------------------------------------------


@pytest.mark.parametrize("holder", ["-", "UNKNOWN", "N/A", "NA", "nil", "अज्ञात", "  "])
def test_a_placeholder_bank_holder_is_blank(holder: str) -> None:
    text = pinned_file({1: BANK_HEADER, 2: bank_row(2, holder=holder)}, lambda n: "")

    records = extract_case("C-1", {"bank.csv": text})

    assert records.attributions == () and records.persons == () and records.orgs == ()
    assert any(i.normalized == "5019000000001" for i in records.identifiers)


def test_also_by_adds_a_person_to_the_used_by_list() -> None:
    records = in_note("Number 9000022310 is used by Irfan bhai and also by Salim Khan.")

    assert owners(records, "9000022310") == {"irfan", "salim khan"}


@pytest.mark.parametrize(
    "text",
    [
        f"The accused Ramesh Yadav, male. Her number is {PHONE}.",
        f"The accused Sunita Devi, female. His number is {PHONE}.",
        f"The accused Ramesh Yadav, male, her mobile {PHONE}.",
    ],
)
def test_a_pronoun_of_the_other_gender_does_not_bind(text: str) -> None:
    assert owners(in_fir(text), PHONE) == set()


def test_the_matching_pronoun_still_binds() -> None:
    records = in_fir(f"The accused Ramesh Yadav, male. His number is {PHONE}.")

    assert owners(records, PHONE) == {"ramesh yadav"}


def test_urf_followed_by_a_role_word_is_a_new_person_and_void() -> None:
    records = in_fir(f"Accused Mohd. Irfan urf witness Salim Khan, mobile {PHONE}.")

    assert owners(records, PHONE) == set()


# --- property: a non-allowed token after the identifier never yields OWNS ------------------------

TRAILING_TOKENS = ("se", "par", "में", "से", "of the accused", "belonging to", "to", "ko", "told")
STARTS = (
    "The accused Ramesh Yadav, mobile {v}",
    "The accused Ramesh Yadav, aged 34, mobile {v}",
    "आरोपी रमेश यादव, मोबाइल नंबर {v}",
    "The accused Ramesh Yadav, a/c {a}",
)


@pytest.mark.parametrize("start", STARTS)
@pytest.mark.parametrize("token", TRAILING_TOKENS)
def test_appending_a_non_allowed_token_after_the_identifier_never_yields_owns(
    start: str, token: str
) -> None:
    sentence = start.format(v=PHONE, a=ACCOUNT) + f" {token} someone."

    records = in_fir(sentence)

    for value in (PHONE, ACCOUNT):
        assert owners(records, value) == set(), sentence
