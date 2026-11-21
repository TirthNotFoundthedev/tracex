"""Kamal and Kamla: two names that sound alike but are two people (errata 6, review of P3.3).

The phonetic key drops vowels, so `kamal` and `kamla` share the key `kml` and match with ratio
0.80, which meets the PER_NAME_SIM trigger. A husband and wife who use one family phone in two
cases, with the same contacts, must never be linked automatically.
"""

import uuid
from decimal import Decimal
from itertools import count

import pytest

from tests.engine.matching.support import clock, store_of
from tests.engine.matching.test_tier2 import by_kind, pair_items, person_case
from tests.engine.matching.test_tier3 import callers_of, case, edges_between, numbers
from tracex_engine.matching import InMemoryLinkStore, LinkState, Matcher

_IDS = count(1)


def test_a_family_phone_used_by_kamal_and_kamla_is_never_an_automatic_link() -> None:
    """MULTI_USER: the owners agree only by sound and on a common token, so the phone is a
    trap (t = 0.2), there is no anchor (G2) and the pair is at most SUGGESTED."""
    phone = "9000077001"
    m = Matcher(
        store_of(
            case("C-501", [("Kamal Singh", phone)], callers_of(phone, numbers(3))),
            case("C-502", [("Kamla Singh", phone)], callers_of(phone, numbers(3))),
        ),
        InMemoryLinkStore(),
        clock=clock(),
        new_id=lambda: str(uuid.UUID(int=next(_IDS), version=4)),
    )

    m.run_matching(triggered_by="u-hari")

    persons = edges_between(m, "C-501", "C-502")
    assert all(e.state is not LinkState.AUTO for e in persons)
    for edge in persons:
        assert "G2" in [g.gate for g in edge.gates_failed]


@pytest.mark.xfail(
    strict=True,
    reason="errata 6: a token matched only by sound never makes a name rare; comparator change "
    "in normalize/similarity.py (Naidu), routed by Fable",
)
def test_a_name_that_agrees_only_by_sound_is_not_rare() -> None:
    """`kamal singh` / `kamla singh`: name_sim 0.90, rarity 0.4 (kamal~kamla only sound alike,
    singh is common): 0.90 x 0.4 x 30 = 10.8, not 27.0."""
    item = by_kind(
        pair_items(person_case("C-101", "Kamal Singh"), person_case("C-102", "Kamla Singh"))
    )["PER_NAME_SIM"]

    assert item.contribution == Decimal("10.8")
