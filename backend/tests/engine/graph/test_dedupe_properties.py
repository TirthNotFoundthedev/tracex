"""Dedupe is a function of the set of a case's mentions, never of their load order.

For a pool of hand-built cases (the review probes included), every order of the mentions gives
the same partition; and on random mentions, no entity ever holds two mentions that a stated
conflict (role, relative, gender, DOB, age, locality, district, IFSC) separates.
"""

import itertools
import random

import pytest

from tests.engine.graph.support import account, org, person, son_of
from tracex_engine.graph.dedupe import Extracted, group_mentions, separated

type Key = tuple[str, int, str]


def key(m: Extracted) -> Key:
    return (m.source.file, m.source.line, m.raw_text)


def partition(mentions: list[Extracted], groups: list[int]) -> frozenset[frozenset[Key]]:
    by_group: dict[int, set[Key]] = {}
    for mention, group in zip(mentions, groups, strict=True):
        by_group.setdefault(group, set()).add(key(mention))
    return frozenset(frozenset(keys) for keys in by_group.values())


def cases() -> dict[str, list[Extracted]]:
    return {
        "role-sides-and-witness": [
            person("Rajesh Kumar", 12, role="complainant"),
            person("Rajesh Kumar", 13, role="accused"),
            person("Rajesh Kumar", 14, role="witness"),
        ],
        "complainant-and-accused": [
            person("Rajesh Kumar", 9, role="complainant"),
            person("Rajesh Kumar", 12, role="accused"),
        ],
        "shared-bare-alias": [
            person("Kalu", 12, role="accused"),
            person("Ramesh Kasana", 13, aliases=("Kalu",)),
            person("Suresh Verma", 14, aliases=("Kalu",)),
        ],
        "alias-chain-with-competing-full-name": [
            person("Ramesh Kasana", 12, aliases=("Kalu",)),
            person("Kalu", 13, aliases=("Pappu",)),
            person("Pappu Sharma", 14),
            person("Pappu", 15),
        ],
        "plain-alias-chain": [
            person("Ramesh Kasana", 12, aliases=("Kalu",)),
            person("Kalu", 13, aliases=("Pappu",)),
            person("Pappu", 14),
        ],
        "attribute-conflicts": [
            person("Ramesh Yadav", 12, gender="M"),
            person("Ramesh Yadav", 13, age="30"),
            person("Ramesh Yadav", 14, gender="F"),
            person("Ramesh Yadav", 15, relative=son_of("Ram Lal")),
            person("Ramesh Yadav", 16, relative=son_of("Shyam Lal")),
        ],
        "single-tokens": [
            person("Irfan", 12),
            person("irfan", 13, age="30"),
            person("Irfan Khan", 14),
            person("Irfan bhai", 15),
        ],
        "ifsc-conflict": [
            account("5010000019082", 12),
            account("5010000019082", 13, ifsc="SYNB0000123"),
            account("5010000019082", 14, ifsc="FAKE0000456"),
            account("5010000019082", 15),
        ],
        "organisations": [
            org("M/s Shree Balaji Traders", 12),
            org("SHREE BALAJI TRADERS", 13),
            org("Shree Balaji Enterprises", 14),
            org("Shree Balaji Traders", 15, locality="Rampur"),
            org("Shree Balaji Traders", 16, locality="Lakeside"),
        ],
    }


@pytest.mark.parametrize("name", list(cases()))
def test_every_load_order_gives_the_same_partition(name: str) -> None:
    mentions = cases()[name]
    rng = random.Random(name)  # noqa: S311 - seeded test input
    orders: list[tuple[int, ...]] = (
        list(itertools.permutations(range(len(mentions))))
        if len(mentions) <= 5
        else [tuple(rng.sample(range(len(mentions)), len(mentions))) for _ in range(200)]
    )
    expected = partition(mentions, group_mentions(mentions))

    for order in orders:
        shuffled = [mentions[i] for i in order]
        assert partition(shuffled, group_mentions(shuffled)) == expected, order


def test_a_shared_bare_alias_never_joins_the_full_names_that_claim_it() -> None:
    mentions = cases()["shared-bare-alias"]

    assert len(set(group_mentions(mentions))) == 3


def test_a_witness_sharing_a_name_with_both_sides_stands_alone() -> None:
    mentions = cases()["role-sides-and-witness"]

    assert len(set(group_mentions(mentions))) == 3


def random_mentions(rng: random.Random) -> list[Extracted]:
    names = ["Ramesh Yadav", "Ramesh Yadav", "Kalu", "Pappu Sharma", "Pappu"]
    out: list[Extracted] = []
    for line in range(12, 12 + rng.randint(2, 7)):
        kind = rng.random()
        if kind < 0.7:
            out.append(
                person(
                    rng.choice(names),
                    line,
                    role=rng.choice([None, "witness", "complainant", "accused"]),
                    aliases=rng.choice([(), (), ("Kalu",), ("Pappu",)]),
                    relative=rng.choice([None, son_of("Ram Lal"), son_of("Shyam Lal")]),
                    age=rng.choice([None, "30", "31", "45"]),
                    gender=rng.choice([None, "M", "F"]),
                    locality=rng.choice([None, "Kherapur", "Sultanpur"]),
                    district=rng.choice([None, "Rivergate", "Hillcrest"]),
                )
            )
        elif kind < 0.85:
            ifsc = rng.choice([None, "SYNB0000123", "FAKE0000456"])
            out.append(account("5010000019082", line, ifsc=ifsc))
        else:
            locality = rng.choice([None, "Rampur", "Lakeside"])
            out.append(org("Shree Balaji Traders", line, locality=locality))
    return out


def test_no_entity_holds_two_mentions_a_stated_conflict_separates() -> None:
    rng = random.Random(20261112)  # noqa: S311 - seeded test input
    cases_with_joins = 0
    for _ in range(400):
        mentions = random_mentions(rng)
        groups = group_mentions(mentions)
        cases_with_joins += len(set(groups)) < len(groups)
        for (a, group_a), (b, group_b) in itertools.combinations(
            list(zip(mentions, groups, strict=True)), 2
        ):
            if group_a == group_b:
                assert not separated(a, b), (key(a), key(b))
    assert cases_with_joins >= 50, "generator rarely joins anything; the check would be vacuous"


def test_group_ids_count_up_in_order_of_first_appearance() -> None:
    groups = group_mentions(cases()["single-tokens"])

    firsts = [groups.index(g) for g in sorted(set(groups))]
    assert groups[0] == 0
    assert firsts == sorted(firsts)
