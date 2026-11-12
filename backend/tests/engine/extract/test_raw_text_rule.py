"""`raw_text` of a PERSON or ORG mention: the name as written, nothing else.

No role word before it, no leading `M/s`, no `urf`/alias clause (the alias goes to `aliases`),
and none of the facts written beside it (age, relative, locality). Honorifics and the spelling
stay as written.
"""

import pytest

from tests.engine.support import fir_file
from tracex_engine.extract import CaseRecords, extract_case


def _line(line: str) -> CaseRecords:
    return extract_case("C-209", {"fir.txt": fir_file("C-209", {12: line})})


@pytest.mark.parametrize(
    ("line", "raw", "alias"),
    [
        ("The accused Rakesh Dubey urf Monu, mobile 9000012345.", "Rakesh Dubey", "Monu"),
        ("Accused Rakesh Dubey alias Monu, mobile 9000012345.", "Rakesh Dubey", "Monu"),
        ("आरोपी राकेश दुबे उर्फ मोनू, मोबाइल 9000012345।", "राकेश दुबे", "मोनू"),
    ],
)
def test_person_raw_text_has_no_role_word_and_no_alias_clause(
    line: str, raw: str, alias: str
) -> None:
    [person] = [p for p in _line(line).persons if p.source.line == 12]

    assert person.raw_text == raw
    assert [a.raw_text for a in person.aliases] == [alias]


def test_person_raw_text_keeps_honorific_and_spelling_as_written() -> None:
    [person] = [
        p for p in _line("Accused Mohd. Irfan, mobile 9000012345.").persons if p.source.line == 12
    ]

    assert person.raw_text == "Mohd. Irfan"
    assert person.normalized == "mohammad irfan"


def test_person_raw_text_excludes_age_relative_and_locality() -> None:
    line = "The accused Parminder Atwal s/o Gurmeet Atwal, aged 34, village Kherapur, fled."

    [person] = [p for p in _line(line).persons if p.source.line == 12]

    assert person.raw_text == "Parminder Atwal"


@pytest.mark.parametrize("marker", ["M/s", "M/S", "M/s."])
def test_org_raw_text_has_no_leading_marker_and_no_role_word(marker: str) -> None:
    [org] = [
        o
        for o in _line(f"Complainant {marker} Shree Balaji Traders, Sector 4.").orgs
        if o.source.line == 12
    ]

    assert org.raw_text == "Shree Balaji Traders"


def test_org_raw_text_has_no_urf_clause() -> None:
    line = "M/s Shree Balaji Traders urf Balaji Stores, a/c 5010000066602."

    [org] = [o for o in _line(line).orgs if o.source.line == 12]

    assert org.raw_text == "Shree Balaji Traders"


def test_org_raw_text_keeps_the_legal_suffix_as_written_and_normalized_drops_it() -> None:
    [org] = [o for o in _line("M/s Om Traders Pvt Ltd, Sector 4.").orgs if o.source.line == 12]

    assert org.raw_text == "Om Traders Pvt Ltd"
    assert org.normalized == "om"


def test_complainant_header_raw_text_has_no_role_word() -> None:
    text = fir_file("C-209", {9: "Complainant: Rakesh Dubey urf Monu, aged 40"})

    records = extract_case("C-209", {"fir.txt": text})

    [person] = [p for p in records.persons if p.source.line == 9]
    assert person.raw_text == "Rakesh Dubey"
    assert [a.raw_text for a in person.aliases] == ["Monu"]
