"""Tier 2 (fuzzy) evidence on hand-built cases, with the real comparators (spec 2, 3, 8).

Acceptance cases AC-01 (name part), AC-03, AC-05, AC-06, AC-10, AC-17, AC-21 and SF-07 run end to
end through the matcher; the other tests read the provider's blocking keys and items directly.
"""

import uuid
from decimal import Decimal
from itertools import count

import pytest

from tests.engine.graph.support import son_of
from tests.engine.matching.fixtures import ac01_graphs
from tests.engine.matching.support import (
    AttributionCode,
    account,
    build,
    clock,
    org,
    owns,
    person,
    phone,
    store_of,
)
from tracex_engine.graph import CaseGraph, Entity, EntityType
from tracex_engine.matching import InMemoryLinkStore, LinkState, Matcher, SameAsEdge
from tracex_engine.matching.corpus import Corpus
from tracex_engine.matching.evidence import Context
from tracex_engine.matching.providers import NotYetImplemented, default_providers
from tracex_engine.matching.tier2 import Tier2Provider, frequent_keys
from tracex_engine.scoring import Band, EvidenceItem, Severity, compose

_IDS = count(1)


def run(*graphs: CaseGraph, provider: Tier2Provider | None = None) -> list[SameAsEdge]:
    matcher = Matcher(
        store_of(*graphs),
        InMemoryLinkStore(),
        providers=(provider or Tier2Provider(),),
        clock=clock(),
        new_id=lambda: str(uuid.UUID(int=next(_IDS), version=4)),
    )
    matcher.run_matching(input_case_ids=(), triggered_by="u-admin")
    return list(matcher.links.edges())


def of_type(edges: list[SameAsEdge], type_: str) -> list[SameAsEdge]:
    return [e for e in edges if e.entity_type.value == type_]


def kinds(edge: SameAsEdge) -> set[str]:
    return {i["kind"] for t in edge.evidence["support"] for i in t["items"]} | {
        i["kind"] for i in edge.evidence["against"]
    }


def gates(edge: SameAsEdge) -> list[str]:
    return [g.gate for g in edge.gates_failed]


def pair_items(
    a: CaseGraph,
    b: CaseGraph,
    type_: EntityType = EntityType.PERSON,
    provider: Tier2Provider | None = None,
) -> list[EvidenceItem]:
    """Tier 2 items for the first entity of `type_` in each graph."""
    corpus = Corpus((a, b))
    first, second = (next(e for e in g.entities if e.type is type_) for g in (a, b))
    return list((provider or Tier2Provider()).items(Context.for_corpus(corpus), first, second))


def by_kind(items: list[EvidenceItem]) -> dict[str, EvidenceItem]:
    return {i.kind: i for i in items}


def person_case(case: str, raw: str, **facts: object) -> CaseGraph:
    return build(case, persons=[person(raw, **facts)])  # type: ignore[arg-type]


# --- acceptance cases ----------------------------------------------------------------------


def test_a_transposed_phone_is_suggested_at_55_never_high() -> None:
    """AC-03: PHONE_TRANSPOSED 55 -> Medium, SUGGESTED, found by B2 with no shared value."""
    edges = run(
        build("C-501", identifiers=[phone("9000081914")]),
        build("C-502", identifiers=[phone("9000081194", 3, "notes.txt")]),
    )

    [link] = edges
    assert (link.state, link.score, link.band) == (
        LinkState.SUGGESTED,
        Decimal("55.0"),
        Band.MEDIUM,
    )
    assert kinds(link) == {"PHONE_TRANSPOSED"} and gates(link) == ["G1"]
    [item] = link.evidence["support"][0]["items"]
    assert item["params"] == {"value_a": "9000081914", "value_b": "9000081194"}
    assert [(s["case_id"], s["document_id"], s["line"]) for s in item["sources"]] == [
        ("C-501", "fir.txt", 12),
        ("C-502", "notes.txt", 3),
    ]


def test_phones_that_differ_in_two_non_adjacent_digits_are_not_compared() -> None:
    edges = run(
        build("C-501", identifiers=[phone("9000081914")]),
        build("C-502", identifiers=[phone("9000081419")]),
    )

    assert edges == []


def test_similar_names_with_close_age_and_same_village_are_medium_without_an_anchor() -> None:
    """AC-05: 28.2 (name_sim 0.94) + 10 + 10 = 48.2, SUGGESTED, found by B4 alone."""
    edges = run(
        person_case("C-107", "Jaswinder Bhullar", age="34", locality="Kherapur"),
        person_case("C-108", "Jasvinder Bhullar", age="35", locality="Kherapur"),
    )

    [link] = edges
    assert (link.state, link.score, link.band) == (
        LinkState.SUGGESTED,
        Decimal("48.2"),
        Band.MEDIUM,
    )
    assert kinds(link) == {"PER_NAME_SIM", "PER_AGE_CLOSE", "PER_LOCALITY"}
    assert gates(link) == ["G1", "G2", "G3"]
    name = link.evidence["support"][0]["items"][0]
    assert name["params"] == {
        "name_a": "jaswinder bhullar",
        "name_b": "jasvinder bhullar",
        "sim": 0.94,
    }


def test_common_name_in_one_district_stays_low_with_no_edge() -> None:
    """AC-06: name_sim 1.0 x rarity 0.4 = 12.0, district only 4.0, total 16.0, Low."""
    a = person_case("C-601", "Mohammed Khan", district="Rampur")
    b = person_case("C-602", "Mohd Khan", district="Rampur")

    items = pair_items(a, b)

    assert {i.kind: i.contribution for i in items} == {
        "PER_NAME_SIM": Decimal("12.0"),
        "PER_LOCALITY": Decimal("4.0"),
    }
    breakdown = compose(EntityType.PERSON, items)
    assert (breakdown.score, breakdown.vetoed) == (Decimal("16.0"), False)
    assert run(a, b) == []


def test_common_names_are_compared_only_through_the_same_district() -> None:
    provider = Tier2Provider()
    same = Corpus(
        (
            person_case("C-601", "Mohammed Khan", district="Rampur"),
            person_case("C-602", "Mohd Khan", district="Rampur"),
        )
    )
    elsewhere = Corpus(
        (
            person_case("C-601", "Mohammed Khan", district="Rampur"),
            person_case("C-602", "Mohd Khan", district="Sultanpur"),
        )
    )
    unstated = Corpus((person_case("C-601", "Mohd Khan"), person_case("C-602", "Mohd Khan")))

    assert len(list(provider.candidates(same))) == 1
    assert list(provider.candidates(elsewhere)) == []
    assert list(provider.candidates(unstated)) == []


def test_same_name_different_dob_on_a_shared_phone_is_medium_but_never_auto() -> None:
    """AC-10: 45 + 30 + 10 - 40 = 45.0, Medium (boundary inclusive), G4 fails."""
    edges = run(
        build(
            "C-113",
            attributions=[
                owns(
                    person("Arjun Mehra", dob="1990-04-12", locality="Ward 7"), phone("9000046120")
                )
            ],
        ),
        build(
            "C-114",
            attributions=[
                owns(
                    person("Arjun Mehra", dob="1978-09-30", locality="Ward 7"), phone("9000046120")
                )
            ],
        ),
    )

    [link] = of_type(edges, "PERSON")
    assert (link.state, link.score, link.band) == (
        LinkState.SUGGESTED,
        Decimal("45.0"),
        Band.MEDIUM,
    )
    assert "G4" in gates(link)
    assert kinds(link) == {"SHARED_PHONE", "PER_NAME_SIM", "PER_LOCALITY", "PER_DOB_CONFLICT"}


def test_devanagari_and_roman_spellings_of_one_name_share_a_phone() -> None:
    """AC-17: name_sim 1.0 -> 30.0 + 45.0 = 75.0, Medium, SUGGESTED."""
    edges = run(
        build("C-120", attributions=[owns(person("मोहम्मद इरफ़ान"), phone("9000051234"))]),
        build("C-210", attributions=[owns(person("Mohd Irfan"), phone("9000051234"))]),
    )

    [link] = of_type(edges, "PERSON")
    assert (link.state, link.score, link.band) == (
        LinkState.SUGGESTED,
        Decimal("75.0"),
        Band.MEDIUM,
    )
    assert gates(link) == ["G1"]


def test_org_names_match_but_an_org_link_is_never_automatic() -> None:
    """AC-21: ORG_NAME_SIM and PER_LOCALITY on top of the shared account; G7 keeps it SUGGESTED."""
    edges = run(
        build(
            "C-122",
            attributions=[
                owns(
                    org("M/s Shree Balaji Traders", locality="Gandhi Nagar"),
                    account("5010000066602", ifsc="SYNB0000123"),
                )
            ],
        ),
        build(
            "C-126",
            attributions=[
                owns(
                    org("M/s Shri Balaji Trading Co", locality="Gandhi Nagar"),
                    account("5010000066602", ifsc="SYNB0000123"),
                )
            ],
        ),
    )

    [link] = of_type(edges, "ORG")
    assert link.state is LinkState.SUGGESTED and link.band is Band.HIGH
    assert link.score >= Decimal(80) and gates(link) == ["G7"]
    assert kinds(link) == {"SHARED_ACCOUNT", "ORG_NAME_SIM", "PER_LOCALITY"}


def test_worked_scenario_person_pair_gets_name_sim_22_5() -> None:
    """AC-01 name part: 'mohammad irfan' vs 'irfan', one token, completeness 0.75."""
    edges = run(*ac01_graphs())

    [irfan] = of_type(edges, "PERSON")
    name = irfan.evidence["support"][1]["items"][0]
    assert (name["kind"], name["contribution"], name["strength"]) == ("PER_NAME_SIM", 22.5, 0.75)
    assert irfan.score == Decimal("67.5")
    assert len(of_type(edges, "PHONE")) == 3


def test_a_similar_name_pair_with_relative_and_locality_is_found_by_name_key() -> None:
    """SF-07 before the shared phone: name, relative name and locality, 55 Medium."""
    edges = run(
        person_case(
            "C-134",
            "Dinesh Pathania",
            relative=son_of("Surjit Pathania"),
            locality="Rampur Khas",
        ),
        person_case(
            "C-135",
            "Dinesh Pathaniya",
            relative=son_of("Surjeet Pathania"),
            locality="Rampur Khas",
        ),
    )

    [link] = edges
    assert kinds(link) == {"PER_NAME_SIM", "PER_RELATIVE_NAME", "PER_LOCALITY"}
    assert (link.state, link.band) == (LinkState.SUGGESTED, Band.MEDIUM)


# --- blocking ------------------------------------------------------------------------------


def test_org_keys_pair_organisations_with_no_shared_identifier() -> None:
    corpus = Corpus(
        (
            build("C-101", orgs=[org("M/s Shree Balaji Traders")]),
            build("C-102", orgs=[org("M/s Shri Balaji Trading Co")]),
            build("C-103", orgs=[org("M/s Gupta Enterprises")]),
        )
    )

    pairs = list(Tier2Provider().candidates(corpus))

    assert [(corpus.entities[a].case_id, corpus.entities[b].case_id) for a, b in pairs] == [
        ("C-101", "C-102")
    ]


def test_a_person_with_only_a_placeholder_name_is_never_a_candidate_or_evidence() -> None:
    a = person_case("C-101", "Name Not Known")
    b = person_case("C-102", "Name Not Known")

    assert list(Tier2Provider().candidates(Corpus((a, b)))) == []
    assert pair_items(a, b) == []


def test_a_person_pair_needs_distinct_cases_and_aliases_count_for_blocking() -> None:
    a = build("C-101", persons=[person("Jasvinder Bhullar"), person("Jasvinder Bhullar", 14)])
    b = build("C-102", persons=[person("Ramesh Gupta", aliases=("Jaswinder Bhullar",))])
    corpus = Corpus((a, b))

    pairs = list(Tier2Provider().candidates(corpus))

    assert len(pairs) == 1
    assert {corpus.entities[x].case_id for x in pairs[0]} == {"C-101", "C-102"}


def test_candidates_are_deterministic() -> None:
    graphs = (
        person_case("C-101", "Jasvinder Bhullar"),
        person_case("C-102", "Jaswinder Bhullar"),
        person_case("C-103", "Jaswinder Bhular"),
    )

    assert list(Tier2Provider().candidates(Corpus(graphs))) == list(
        Tier2Provider().candidates(Corpus(graphs))
    )


def test_a_name_in_one_percent_of_persons_and_twenty_entities_is_common() -> None:
    crowd = [person_case(f"C-{100 + n}", f"Rajesh Name{n}x") for n in range(1, 21)]
    corpus = Corpus((*crowd, person_case("C-190", "Mukesh Aroraa")))
    few = Corpus(crowd[:19])

    assert "rjs" in frequent_keys(corpus)
    assert frequent_keys(few) == frozenset()


def test_a_frequent_given_name_gets_the_common_name_rarity() -> None:
    crowd = [person_case(f"C-{100 + n}", f"Rajesh Name{n}x") for n in range(1, 21)]
    a, b = person_case("C-191", "Rajesh"), person_case("C-192", "Rajesh")

    alone = by_kind(pair_items(a, b))["PER_NAME_SIM"]
    corpus = Corpus((*crowd, a, b))
    first, second = corpus.entities["C-191:00001"], corpus.entities["C-192:00001"]
    crowded = by_kind(list(Tier2Provider().items(Context.for_corpus(corpus), first, second)))[
        "PER_NAME_SIM"
    ]

    assert alone.strength == Decimal("0.75")
    assert crowded.strength == Decimal("0.75") * Decimal("0.4")


# --- items ---------------------------------------------------------------------------------


def test_relative_names_that_match_support_and_cite_both_lines() -> None:
    items = by_kind(
        pair_items(
            person_case("C-101", "Sunil Mittal", relative=son_of("Ram Avtar Mittal")),
            person_case("C-102", "Sunil Mittal", relative=son_of("Ram Avatar Mittal")),
        )
    )

    item = items["PER_RELATIVE_NAME"]
    assert item.spec.weight * item.strength == Decimal("15") * item.strength
    assert item.params == {"rel_a": "ram avtar mittal", "rel_b": "ram avatar mittal"}
    assert {s.case_id for s in item.sources} == {"C-101", "C-102"}
    assert "PER_RELATIVE_CONFLICT" not in items


def test_different_relative_names_of_the_same_relation_oppose_softly() -> None:
    items = by_kind(
        pair_items(
            person_case("C-101", "Sunil Mittal", relative=son_of("Ram Avtar Mittal")),
            person_case("C-102", "Sunil Mittal", relative=son_of("Gopal Das Verma")),
        )
    )

    item = items["PER_RELATIVE_CONFLICT"]
    assert (item.contribution, item.severity) == (Decimal("-20.0"), Severity.SOFT)
    assert "PER_RELATIVE_NAME" not in items


@pytest.mark.parametrize(
    ("relation_a", "relation_b"),
    [("son", "daughter"), ("relative", "relative"), ("son", "relative")],
)
def test_a_different_or_unknown_relation_is_never_compared(
    relation_a: str, relation_b: str
) -> None:
    items = by_kind(
        pair_items(
            person_case("C-101", "Sunil Mittal", relative=son_of("Ram Avtar Mittal", relation_a)),
            person_case("C-102", "Sunil Mittal", relative=son_of("Gopal Das Verma", relation_b)),
        )
    )

    assert "PER_RELATIVE_NAME" not in items and "PER_RELATIVE_CONFLICT" not in items


def test_identical_full_dob_supports_and_cites_both_lines() -> None:
    items = by_kind(
        pair_items(
            person_case("C-101", "Shyam Siddiqui", dob="1988-03-02"),
            person_case("C-102", "Shyam Siddiqui", dob="1988-03-02"),
        )
    )

    item = items["PER_DOB_MATCH"]
    assert (item.contribution, item.params) == (Decimal("20.0"), {"dob": "1988-03-02"})


@pytest.mark.parametrize(
    ("age_a", "age_b", "kind", "contribution"),
    [
        ("34", "34", "PER_AGE_CLOSE", "10.0"),
        ("34", "35", "PER_AGE_CLOSE", "10.0"),
        ("34", "36", "PER_AGE_CLOSE", "5.0"),
        ("34", "37", None, None),
        ("34", "39", None, None),
        ("34", "40", "PER_AGE_CONFLICT", "-20.0"),
        ("34", "44", "PER_AGE_CONFLICT", "-20.0"),
        ("34", "45", "PER_AGE_CONFLICT", "-40.0"),
    ],
)
def test_age_comparison_table(
    age_a: str, age_b: str, kind: str | None, contribution: str | None
) -> None:
    found = {
        i.kind: i
        for i in pair_items(
            person_case("C-101", "Ravi Verma", age=age_a),
            person_case("C-102", "Ravi Verma", age=age_b),
        )
        if i.kind.startswith("PER_AGE")
    }

    if kind is None:
        assert found == {}
    else:
        assert {k: v.contribution for k, v in found.items()} == {kind: Decimal(contribution or 0)}


def test_an_age_gap_over_ten_years_is_a_hard_conflict() -> None:
    items = by_kind(
        pair_items(
            person_case("C-101", "Ravi Verma", age="30"),
            person_case("C-102", "Ravi Verma", age="52"),
        )
    )

    conflict = items["PER_AGE_CONFLICT"]
    assert conflict.severity is Severity.HARD and conflict.params == {"age_a": 30, "age_b": 52}


def test_age_close_needs_a_side_without_a_full_dob() -> None:
    items = by_kind(
        pair_items(
            person_case("C-101", "Ravi Verma", age="34", dob="1991-01-01"),
            person_case("C-102", "Ravi Verma", age="34", dob="1991-02-01"),
        )
    )

    assert "PER_AGE_CLOSE" not in items


def test_same_village_counts_in_full_and_same_district_only_in_part() -> None:
    village = by_kind(
        pair_items(
            person_case("C-101", "Ravi Verma", locality="Kherapur", district="Rampur"),
            person_case("C-102", "Ravi Verma", locality="Kheerapur", district="Rampur"),
        )
    )["PER_LOCALITY"]
    district = by_kind(
        pair_items(
            person_case("C-101", "Ravi Verma", locality="Kherapur", district="Rampur"),
            person_case("C-102", "Ravi Verma", locality="Dhanipur", district="Rampur"),
        )
    )["PER_LOCALITY"]
    nowhere = pair_items(
        person_case("C-101", "Ravi Verma", locality="Kherapur", district="Rampur"),
        person_case("C-102", "Ravi Verma", locality="Dhanipur", district="Sultanpur"),
    )

    assert (village.contribution, village.params) == (Decimal("10.0"), {"place": "kherapur"})
    assert (district.contribution, district.params) == (Decimal("4.0"), {"place": "rampur"})
    assert "PER_LOCALITY" not in by_kind(nowhere)


def test_a_phone_pair_whose_numbers_are_confirmed_transposed_links_the_owners() -> None:
    """PER_NEAR_PHONE: min attribution factor, only with a confirmed PHONE_TRANSPOSED link."""
    a = build("C-101", attributions=[owns(person("Anil Rana"), phone("9000081914"))])
    b = build("C-102", attributions=[owns(person("Anil Raana"), phone("9000081194"))])
    corpus = Corpus((a, b))
    first, second = (next(e for e in g.entities if e.type is EntityType.PERSON) for g in (a, b))
    phones = {
        e.normalized: e.entity_id for e in corpus.entities.values() if e.type is EntityType.PHONE
    }
    confirmed = {frozenset(phones.values())}

    def lookup(x: str, y: str) -> bool:
        return frozenset({x, y}) in confirmed

    found = by_kind(
        list(
            Tier2Provider().items(Context.for_corpus(corpus, confirmed_link=lookup), first, second)
        )
    )
    unlinked = by_kind(list(Tier2Provider().items(Context.for_corpus(corpus), first, second)))

    assert found["PER_NEAR_PHONE"].contribution == Decimal("15.0")
    assert found["PER_NEAR_PHONE"].params == {}
    assert {s.case_id for s in found["PER_NEAR_PHONE"].sources} == {"C-101", "C-102"}
    assert "PER_NEAR_PHONE" not in unlinked


def test_near_phone_is_weaker_when_a_number_is_only_registered_to_the_person() -> None:
    a = build("C-101", attributions=[owns(person("Anil Rana"), phone("9000081914"))])
    b = build(
        "C-102",
        attributions=[
            owns(person("Anil Rana"), phone("9000081194"), AttributionCode.REGISTERED_TO)
        ],
    )
    corpus = Corpus((a, b))
    first, second = (next(e for e in g.entities if e.type is EntityType.PERSON) for g in (a, b))

    found = by_kind(
        list(
            Tier2Provider().items(
                Context.for_corpus(corpus, confirmed_link=lambda x, y: True), first, second
            )
        )
    )

    assert found["PER_NEAR_PHONE"].contribution == Decimal("7.5")


def test_every_item_cites_only_the_two_end_cases_and_at_least_one_line() -> None:
    a = person_case(
        "C-101",
        "Jasvinder Bhullar",
        age="34",
        locality="Kherapur",
        dob="1990-04-12",
        relative=son_of("Gurmeet Bhullar"),
    )
    b = person_case(
        "C-102",
        "Jaswinder Bhullar",
        age="35",
        locality="Kherapur",
        dob="1990-04-12",
        relative=son_of("Gurmeet Bhullar"),
    )

    items = pair_items(a, b)

    assert {i.kind for i in items} == {
        "PER_NAME_SIM",
        "PER_RELATIVE_NAME",
        "PER_DOB_MATCH",
        "PER_LOCALITY",
    }
    for item in items:
        assert item.sources and {s.case_id for s in item.sources} <= {"C-101", "C-102"}


def test_default_providers_run_tier2_and_leave_no_seams() -> None:
    providers = default_providers()

    assert any(isinstance(p, Tier2Provider) for p in providers)
    assert not any(isinstance(p, NotYetImplemented) for p in providers)


def test_the_provider_never_adds_items_for_pairs_of_other_types() -> None:
    a = build("C-101", identifiers=[account("5010000012345")])
    b = build("C-102", identifiers=[account("5010000012345")])

    assert pair_items(a, b, EntityType.ACCOUNT) == []


def test_entities_are_unchanged_by_a_tier2_run() -> None:
    graphs = (
        person_case("C-107", "Jaswinder Bhullar", age="34", locality="Kherapur"),
        person_case("C-108", "Jasvinder Bhullar", age="35", locality="Kherapur"),
    )
    store = store_of(*graphs)
    before: list[Entity] = [e for g in graphs for e in g.entities]

    Matcher(store, InMemoryLinkStore(), providers=(Tier2Provider(),)).run_matching((), "u")

    assert [
        e for case in store.case_ids() for e in (store.read_case(case) or graphs[0]).entities
    ] == before


def test_a_devanagari_org_name_matches_its_roman_spelling() -> None:
    a = build("C-101", orgs=[org("श्री बालाजी ट्रेडर्स")])
    b = build("C-102", orgs=[org("M/s Shree Balaji Traders")])

    items = by_kind(pair_items(a, b, EntityType.ORG))

    assert items["ORG_NAME_SIM"].contribution == Decimal("40.0")
    assert len(list(Tier2Provider().candidates(Corpus((a, b))))) == 1


def test_one_token_names_that_only_sound_alike_give_no_name_sim_item() -> None:
    for left, right in (("Sunil", "Sonal"), ("Salim", "Saleem")):
        items = by_kind(pair_items(person_case("C-101", left), person_case("C-102", right)))

        assert "PER_NAME_SIM" not in items, (left, right)
