"""A role word followed by an organisation marker names the organisation, never a person.

Generated cases C-122 and C-126 write `Complainant M/s Shree Balaji Traders, ...`; the role
word used to swallow the `M` of `M/s` as a PERSON.
"""

import pytest

from tests.engine.support import fir_file, note, notes_file
from tracex_engine.extract import AttributionCode, CaseRecords, extract_case

ROLE_WORDS = [
    "Complainant",
    "complainant",
    "Accused",
    "accused",
    "Suspect",
    "Witness",
    "Victim",
    "Informant",
    "Informer",
    "Arrested",
    "Aaropi",
    "Abhiyukt",
    "Shikayatkarta",
    "Gawah",
    "Sandigdh",
    "आरोपी",
    "अभियुक्त",
    "शिकायतकर्ता",
    "गवाह",
    "संदिग्ध",
    "मुखबिर",
    "पीड़ित",
]
MARKERS = ["M/s", "M/S", "M/s.", "Messrs", "Messrs."]


def _line(line: str, case_id: str = "C-122") -> CaseRecords:
    return extract_case(case_id, {"fir.txt": fir_file(case_id, {12: line})})


def _on_line_12(records: CaseRecords) -> tuple[list[str], list[str]]:
    persons = [p.raw_text for p in records.persons if p.source.line == 12]
    orgs = [o.raw_text for o in records.orgs if o.source.line == 12]
    return persons, orgs


@pytest.mark.parametrize("marker", MARKERS)
@pytest.mark.parametrize("role", ROLE_WORDS)
def test_role_word_then_org_marker_gives_the_org_and_no_person(role: str, marker: str) -> None:
    records = _line(f"{role} {marker} Shree Balaji Traders, Mohalla Subhash Nagar.")

    assert _on_line_12(records) == ([], ["Shree Balaji Traders"])


@pytest.mark.parametrize("separator", [": ", ", ", " - ", " named ", " namely "])
def test_separator_or_named_between_role_and_marker_still_gives_the_org_only(
    separator: str,
) -> None:
    records = _line(f"The accused{separator}M/s Om Traders, Sector 9.")

    assert _on_line_12(records) == ([], ["Om Traders"])


def test_complainant_header_line_naming_an_org_gives_the_org_only() -> None:
    text = fir_file("C-122", {9: "Complainant: M/s Shree Balaji Traders, Mohalla Subhash Nagar"})

    records = extract_case("C-122", {"fir.txt": text})

    assert [p.raw_text for p in records.persons if p.source.line == 9] == []
    [org] = [o for o in records.orgs if o.source.line == 9]
    assert org.raw_text == "Shree Balaji Traders"
    assert org.normalized == "shree balaji"
    assert org.source.file == "fir.txt"


def test_generated_c122_line_gives_the_org_and_its_account_and_no_junk_person() -> None:
    line = (
        "Complainant M/s Shree Balaji Traders, Mohalla Subhash Nagar, "
        "a/c 5010000066602 (IFSC SYNB0000123)."
    )

    records = _line(line)

    assert _on_line_12(records) == ([], ["Shree Balaji Traders"])
    [owns] = [a for a in records.attributions if a.source.line == 12]
    assert owns.code is AttributionCode.OWNS
    assert owns.holder.normalized == "shree balaji"
    assert owns.identifier.normalized == "5010000066602"


def test_org_after_role_word_keeps_the_ownership_of_its_phone() -> None:
    records = _line("Accused M/s Om Traders Pvt Ltd, mobile 9000012345.")

    assert _on_line_12(records) == ([], ["Om Traders Pvt Ltd"])
    [owns] = [a for a in records.attributions if a.source.line == 12]
    assert owns.code is AttributionCode.OWNS
    assert owns.holder.normalized == "om"


def test_romanised_hindi_role_then_org_with_ka_number_owns_the_number() -> None:
    records = _line("Aaropi M/s Om Traders ka number 9000012345.")

    assert _on_line_12(records) == ([], ["Om Traders"])
    [owns] = [a for a in records.attributions if a.source.line == 12]
    assert owns.code is AttributionCode.OWNS


def test_role_word_then_org_in_officer_notes_gives_the_org_only() -> None:
    text = notes_file("C-122", {3: note("Witness M/s Om Traders confirmed the visit.")})

    records = extract_case("C-122", {"notes.txt": text})

    assert [p.raw_text for p in records.persons if p.source.line == 3] == []
    assert [o.raw_text for o in records.orgs if o.source.line == 3] == ["Om Traders"]


def test_person_and_org_in_one_sentence_each_keep_their_own_role() -> None:
    records = _line("The accused Ramesh Kumar and witness M/s Om Traders were questioned.")

    assert _on_line_12(records) == (["Ramesh Kumar"], ["Om Traders"])


@pytest.mark.parametrize(
    "line",
    [
        "Complainant Om Traders Pvt Ltd, mobile 9000012345.",
        "Complainant: Om Traders Pvt Ltd, mobile 9000012345.",
        "Accused Shree Ram Enterprises LLP, mobile 9000012345.",
        "Witness Gupta Trading Co, Sector 9.",
        "Victim Om Traders Private Limited.",
    ],
)
def test_legal_suffix_after_a_role_word_is_an_org_not_a_person(line: str) -> None:
    records = _line(line)

    persons, orgs = _on_line_12(records)
    assert persons == []
    assert len(orgs) == 1


def test_role_word_then_ordinary_name_is_still_a_person() -> None:
    records = _line("Complainant Ramesh Kumar, mobile 9000012345.")

    assert _on_line_12(records) == (["Ramesh Kumar"], [])
    [owns] = [a for a in records.attributions if a.source.line == 12]
    assert owns.code is AttributionCode.OWNS


@pytest.mark.parametrize(
    "line",
    [
        "Complainant M/s, mobile 9000012345.",
        "Accused M/s",
        "Witness Messrs.",
    ],
)
def test_bare_marker_with_no_name_gives_no_mention_at_all(line: str) -> None:
    records = _line(line)

    assert _on_line_12(records) == ([], [])
    assert all(a.code is not AttributionCode.OWNS for a in records.attributions)
