"""Identifier flags (spec section 1) and the Tier 1 name guards."""

from decimal import Decimal

import pytest

from tests.engine.matching.support import (
    AttributionCode,
    account,
    build,
    owns,
    person,
    phone,
    store_of,
)
from tracex_engine.graph import EntityType
from tracex_engine.matching.corpus import Corpus
from tracex_engine.matching.flags import best_name_sim, identifier_flags
from tracex_engine.matching.names import is_placeholder

PHONE = "9000022310"
KEY = (EntityType.PHONE, PHONE)


def flags_of(*graphs: object) -> dict[tuple[EntityType, str], frozenset[str]]:
    return identifier_flags(Corpus.load(store_of(*graphs)))  # type: ignore[arg-type]


def test_two_owners_in_one_case_make_the_phone_shared_in_every_case() -> None:
    """AC-07: Ramesh and Sunita own the family phone in one case. Ramesh and Suresh (C-204)
    share only the common token `yadav`, so the phone is also MULTI_USER (errata 6)."""
    n = build(
        "C-109",
        attributions=[
            owns(person("Ramesh Yadav", line=3, file="notes.txt"), phone(PHONE, 3, "notes.txt")),
            owns(person("Sunita Yadav", line=4, file="notes.txt"), phone(PHONE, 4, "notes.txt")),
        ],
    )
    p = build("C-204", attributions=[owns(person("Suresh Yadav"), phone(PHONE))])

    assert flags_of(n, p)[KEY] == {"SHARED", "MULTI_USER"}


def test_shop_wording_makes_the_phone_shared() -> None:
    """SF-05: the note calls it a shop number."""
    shop = phone(PHONE)
    shop = type(shop)(shop.kind, shop.raw_text, shop.normalized, shop.source, 0.9, True)

    assert flags_of(build("C-132", attributions=[owns(person("Mahesh Gupta"), shop)]))[KEY] == {
        "SHARED"
    }


def test_registered_to_counts_toward_shared_but_mentioned_with_does_not() -> None:
    one = build(
        "C-110",
        attributions=[
            owns(person("Vikram Chauhan"), phone(PHONE)),
            owns(person("Kamla Devi", line=13), phone(PHONE), AttributionCode.REGISTERED_TO),
        ],
    )
    two = build(
        "C-111",
        attributions=[
            owns(person("Vikram Chauhan"), phone(PHONE)),
            owns(person("Kamla Devi", line=13), phone(PHONE), AttributionCode.MENTIONED_WITH),
        ],
    )

    assert flags_of(one).get(KEY) == frozenset({"SHARED"})
    assert flags_of(two).get(KEY) is None


def test_owners_with_unrelated_names_in_two_cases_make_a_multi_user_account() -> None:
    """AC-09 mule account and SF-08 recycled number."""
    acc = "5010000055501"
    graphs = [
        build(case, attributions=[owns(person(name), account(acc, ifsc="SYNB0000123"))])
        for case, name in (("C-112", "Ajay Pal"), ("C-205", "Imran Qureshi"))
    ]

    assert flags_of(*graphs)[(EntityType.ACCOUNT, acc)] == {"MULTI_USER"}


def test_the_same_name_in_two_cases_is_not_multi_user() -> None:
    """AC-01: `Mohd. Irfan` and `Irfan bhai` own the same phone."""
    graphs = [
        build("C-101", attributions=[owns(person("Mohd. Irfan"), phone("9000014471"))]),
        build(
            "C-201",
            attributions=[
                owns(person("Irfan bhai", 3, "notes.txt"), phone("9000014471", 3, "notes.txt"))
            ],
        ),
    ]

    assert flags_of(*graphs) == {}


def test_an_alias_counts_as_a_name_for_multi_user() -> None:
    """AC-14: `Monu` owns p2 in one case, `Rakesh Dubey urf Monu` in the other."""
    graphs = [
        build("C-119", attributions=[owns(person("Monu"), phone(PHONE))]),
        build(
            "C-209",
            attributions=[owns(person("Rakesh Dubey", aliases=("Monu",)), phone(PHONE))],
        ),
    ]

    assert flags_of(*graphs) == {}


@pytest.mark.parametrize(
    ("name", "placeholder"),
    [
        ("name not known", True),
        ("unknown male", True),
        ("not stated", True),
        ("unidentified person", True),
        ("", True),
        ("irfan", False),
        ("man singh", False),
        ("mohammad irfan", False),
    ],
)
def test_placeholder_names(name: str, placeholder: bool) -> None:
    assert is_placeholder(name) is placeholder


@pytest.mark.parametrize(
    ("a", "b", "sim"),
    [
        ({"mohammad irfan"}, {"irfan"}, "1.00"),
        ({"ajay pal"}, {"imran qureshi"}, "0"),
        ({"jaswinder bhullar"}, {"jasvinder bhullar"}, "0.94"),
        ({"harbajan sandhawalia"}, {"harbhajan sandhawaliya"}, "0.95"),
        ({"name not known"}, {"name not known"}, "0"),
        # errata 6: agreeing only by sound, or only on common tokens, is not one user
        ({"kamal"}, {"kamla"}, "0"),
        ({"kamal singh"}, {"kamla singh"}, "0"),
        ({"mohammad khan"}, {"mohammad khan"}, "0"),
    ],
)
def test_multi_user_reads_the_real_name_sim(a: set[str], b: set[str], sim: str) -> None:
    """MULTI_USER uses `name_sim` (errata 6): close spellings of one name are one user."""
    assert best_name_sim(a, b) == Decimal(sim)
