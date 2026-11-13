"""Extractor follow-ups from the P2.2 review (Naidu): the matcher makes no wrong link from what
the extractor emits today. Each case runs the real extractor on hand-written files.

- multi-word placeholder holders (`NAME NOT KNOWN`) come out as persons that OWN the account;
- a name directly after a locality with no comma is not extracted at all;
- family-note owners in parentheses come out as hedged MENTIONED_WITH, the number SHARED.
"""

import pytest

from tests.engine.matching.fixtures import matcher
from tests.engine.matching.support import from_files
from tests.engine.support import (
    BANK_HEADER,
    bank_row,
    fir_file,
    note,
    notes_file,
    pinned_file,
)
from tracex_engine.graph import CaseGraph
from tracex_engine.matching import SameAsEdge

PHONE = "9000022310"


def links(*graphs: CaseGraph) -> list[SameAsEdge]:
    m = matcher(*graphs)
    m.run_matching(input_case_ids=(), triggered_by="u-admin")
    return list(m.links.edges())


def types(edges: list[SameAsEdge]) -> set[str]:
    return {e.entity_type.value for e in edges}


def bank_case(case_id: str, holder: str) -> CaseGraph:
    text = pinned_file(
        {1: BANK_HEADER, 2: bank_row(2, account="5019000000077", holder=holder)}, lambda n: ""
    )
    return from_files(case_id, {"bank.csv": text})


@pytest.mark.parametrize(
    "holder",
    ["NAME NOT KNOWN", "UNKNOWN MALE", "NOT STATED", "UNIDENTIFIED PERSON", "Not Known"],
)
def test_two_placeholder_holders_of_one_account_are_never_linked(holder: str) -> None:
    edges = links(bank_case("C-151", holder), bank_case("C-252", holder))

    assert types(edges) == {"ACCOUNT"}


def test_a_placeholder_holder_is_never_linked_to_a_named_holder() -> None:
    edges = links(bank_case("C-151", "NAME NOT KNOWN"), bank_case("C-252", "RAJAN GUPTA"))

    assert types(edges) == {"ACCOUNT"}


def test_a_named_holder_pair_on_one_account_is_suggested_not_auto() -> None:
    """Control: the same rows with a real holder give the Tier 1 person edge (45.0, SUGGESTED)."""
    edges = links(bank_case("C-151", "RAJAN GUPTA"), bank_case("C-252", "RAJAN GUPTA"))

    assert types(edges) == {"ACCOUNT", "PERSON"}
    assert {e.state.value for e in edges if e.entity_type.value == "PERSON"} == {"SUGGESTED"}


@pytest.mark.parametrize(
    "line",
    [
        f"Accused resident of village Kherapur Ramesh Yadav, mobile {PHONE}, was seen.",
        f"The accused of Mohalla Shivpuri Ramesh Yadav, mobile {PHONE}.",
    ],
)
def test_a_name_right_after_a_locality_makes_no_person_link(line: str) -> None:
    edges = links(
        from_files("C-153", {"fir.txt": fir_file("C-153", {12: line})}),
        from_files(
            "C-254", {"fir.txt": fir_file("C-254", {12: f"Accused Ramesh Yadav, mobile {PHONE}."})}
        ),
    )

    assert types(edges) == {"PHONE"}


@pytest.mark.parametrize(
    "text",
    [
        f"Number {PHONE} is the family number (used by Ramesh Yadav and Sunita Yadav).",
        f"Number {PHONE} ghar ka number hai (Ramesh Yadav aur Sunita Yadav upyog karte hain).",
    ],
)
def test_family_note_owners_in_parentheses_are_never_linked_through_the_number(text: str) -> None:
    family = from_files("C-155", {"notes.txt": notes_file("C-155", {3: note(text)})})
    other = from_files(
        "C-256", {"fir.txt": fir_file("C-256", {12: f"Accused Ramesh Yadav, mobile {PHONE}."})}
    )

    edges = links(family, other)

    assert types(edges) == {"PHONE"}
