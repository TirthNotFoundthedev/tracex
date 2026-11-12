"""Within-case dedupe (docs/specs/engine-graph.md section 2): conservative, nothing lost."""

import pytest

from tests.engine.graph.support import (
    account,
    ident,
    org,
    person,
    phone,
    records,
    son_of,
)
from tracex_engine.extract import IdKind, OrgMention, PersonMention
from tracex_engine.graph import CaseGraph, EntityType, build_case_graph


def entity_groups(graph: CaseGraph, type_: EntityType) -> list[list[tuple[str, int]]]:
    """Per entity of the type, the (file, line) of each of its mentions, in mention order."""
    out = []
    for entity in graph.entities:
        if entity.type == type_:
            out.append(
                [(m.file, m.line) for m in graph.mentions if m.entity_id == entity.entity_id]
            )
    return out


def persons(*mentions: PersonMention) -> CaseGraph:
    return build_case_graph(records(persons=mentions))


def test_the_same_phone_written_three_ways_is_one_entity_with_three_mentions() -> None:
    graph = build_case_graph(
        records(
            identifiers=(
                phone("9000052210", 12, raw="90000 52210"),
                phone("9000052210", 3, "notes.txt", raw="+91-9000052210"),
                phone("9000052210", 6, "notes.txt", raw="09000052210"),
            )
        )
    )

    [entity] = graph.entities
    assert entity.display_value == "90000 52210"
    assert sorted(m.raw_text for m in graph.mentions) == [
        "+91-9000052210",
        "09000052210",
        "90000 52210",
    ]
    assert {m.entity_id for m in graph.mentions} == {entity.entity_id}


def test_different_phones_stay_separate_and_a_phone_is_not_an_account() -> None:
    graph = build_case_graph(
        records(
            identifiers=(
                phone("9000052210", 12),
                phone("9000052211", 13),
                ident(IdKind.ACCOUNT, "9000052210", "9000052210", 14),
            )
        )
    )

    assert len(graph.entities) == 3


def test_vehicle_writings_with_the_same_registration_join() -> None:
    graph = build_case_graph(
        records(
            identifiers=(
                ident(IdKind.VEHICLE, "UP32AD4567", "UP32AD4567", 15),
                ident(IdKind.VEHICLE, "up 32 ad 4567", "UP32AD4567", 9, "notes.txt"),
            )
        )
    )

    assert len(graph.entities) == 1


@pytest.mark.parametrize(
    ("ifscs", "entities"),
    [
        (("SYNB0000123", "SYNB0000123"), 1),
        (("SYNB0000123", None), 1),
        ((None, "SYNB0000123"), 1),
        ((None, None), 1),
        (("SYNB0000123", "FAKE0000456"), 2),
    ],
)
def test_accounts_join_on_digits_unless_both_ifscs_are_known_and_differ(
    ifscs: tuple[str | None, str | None], entities: int
) -> None:
    mentions = tuple(account("5010000019082", 12 + i, ifsc=ifsc) for i, ifsc in enumerate(ifscs))

    graph = build_case_graph(records(identifiers=mentions))

    assert len(graph.entities) == entities
    assert len(graph.mentions) == 2


def test_an_account_without_ifsc_that_fits_two_banks_starts_its_own_entity() -> None:
    graph = build_case_graph(
        records(
            identifiers=(
                account("5010000019082", 12, ifsc="SYNB0000123"),
                account("5010000019082", 13, ifsc="FAKE0000456"),
                account("5010000019082", 14),
            )
        )
    )

    assert entity_groups(graph, EntityType.ACCOUNT) == [
        [("fir.txt", 12)],
        [("fir.txt", 13)],
        [("fir.txt", 14)],
    ]


def test_an_account_without_ifsc_takes_the_ifsc_of_the_entity_it_joins() -> None:
    graph = build_case_graph(
        records(
            identifiers=(
                account("5010000019082", 12),
                account("5010000019082", 13, ifsc="synb0000123"),
            )
        )
    )

    [entity] = graph.entities
    assert entity.ifsc == "SYNB0000123"


def test_shared_wording_on_any_mention_marks_the_entity() -> None:
    graph = build_case_graph(
        records(
            identifiers=(
                phone("9000088120", 12),
                ident(
                    IdKind.PHONE, "9000088120", "9000088120", 3, "notes.txt", shared_wording=True
                ),
            )
        )
    )

    [entity] = graph.entities
    assert entity.shared_wording is True


def test_two_writings_of_a_multi_token_name_join_and_keep_their_own_text() -> None:
    graph = persons(
        person("Mohd. Irfan", 12),
        person("MOHD IRFAN", 4, "bank.csv"),
        person("MOHD IRFAN", 7, "bank.csv"),
    )

    [entity] = graph.entities
    assert entity.normalized == "mohammad irfan"
    assert entity.display_value == "Mohd. Irfan"
    assert [(m.raw_text, m.file, m.line) for m in graph.mentions] == [
        ("Mohd. Irfan", "fir.txt", 12),
        ("MOHD IRFAN", "bank.csv", 4),
        ("MOHD IRFAN", "bank.csv", 7),
    ]


def test_different_names_stay_separate() -> None:
    graph = persons(
        person("Ramesh Kumar", 12), person("Ramesh Kumari", 13), person("Suresh Kumar", 14)
    )

    assert len(graph.entities) == 3


def test_a_single_token_name_joins_only_when_written_the_same() -> None:
    graph = persons(
        person("Irfan", 12),
        person("irfan  ", 13),
        person("Irfan bhai", 14, "notes.txt"),
    )

    assert entity_groups(graph, EntityType.PERSON) == [
        [("fir.txt", 12), ("fir.txt", 13)],
        [("notes.txt", 14)],
    ]


def test_a_bare_alias_joins_the_person_who_states_it() -> None:
    graph = persons(
        person("Ramesh Kasana", 18, aliases=("Kalu",)),
        person("Kalu", 12, "notes.txt"),
    )

    [entity] = graph.entities
    assert entity.aliases == ("kalu",)
    assert len(graph.mentions) == 2


def test_an_alias_stated_later_joins_the_earlier_bare_name() -> None:
    graph = persons(
        person("Kalu", 12),
        person("Ramesh Kasana", 18, aliases=("Kalu",)),
    )

    assert len(graph.entities) == 1


def test_an_alias_shared_by_two_people_is_ambiguous_so_the_bare_name_stands_alone() -> None:
    graph = persons(
        person("Ramesh Kasana", 12, aliases=("Kalu",)),
        person("Suresh Pal", 13, aliases=("Kalu",)),
        person("Kalu", 14),
    )

    assert len(graph.entities) == 3


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ({"relative": son_of("Ram Lal")}, {"relative": son_of("Shyam Lal")}),
        ({"gender": "M"}, {"gender": "F"}),
        ({"dob": "1990-04-12"}, {"dob": "1991-04-12"}),
        ({"age": "30"}, {"age": "34"}),
        ({"locality": "Kherapur"}, {"locality": "Sultanpur"}),
        ({"district": "Rivergate"}, {"district": "Hillcrest"}),
    ],
    ids=["relative", "gender", "dob", "age", "locality", "district"],
)
def test_a_stated_conflict_keeps_same_named_people_apart(
    first: dict[str, object], second: dict[str, object]
) -> None:
    graph = persons(
        person("Ramesh Yadav", 12, **first),  # type: ignore[arg-type]
        person("Ramesh Yadav", 13, **second),  # type: ignore[arg-type]
    )

    assert len(graph.entities) == 2


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ({"relative": son_of("Ram Lal")}, {}),
        ({"relative": son_of("Ram Lal")}, {"relative": son_of("Ram Lal")}),
        ({"relative": son_of("Ram Lal", "son")}, {"relative": son_of("Shyam Lal", "relative")}),
        ({"age": "30"}, {"age": "31"}),
        ({"locality": "Kherapur"}, {"locality": "Kherapur"}),
        ({"gender": "M"}, {}),
    ],
    ids=[
        "one-side-silent",
        "same-relative",
        "unknown-relation",
        "age-within-2",
        "same-place",
        "gender-silent",
    ],
)
def test_agreeing_or_silent_attributes_do_not_stop_a_join(
    first: dict[str, object], second: dict[str, object]
) -> None:
    graph = persons(
        person("Ramesh Yadav", 12, **first),  # type: ignore[arg-type]
        person("Ramesh Yadav", 13, **second),  # type: ignore[arg-type]
    )

    assert len(graph.entities) == 1


def test_two_conflicting_writings_chained_through_a_silent_one_are_not_joined() -> None:
    graph = persons(
        person("Ramesh Yadav", 12, gender="M"),
        person("Ramesh Yadav", 13, age="30"),
        person("Ramesh Yadav", 14, gender="F"),
    )

    assert len(graph.entities) == 3


def test_a_mention_that_fits_two_separate_people_starts_its_own_entity() -> None:
    graph = persons(
        person("Ramesh Yadav", 12, gender="M"),
        person("Ramesh Yadav", 13, gender="F"),
        person("Ramesh Yadav", 14),
    )

    assert len(graph.entities) == 3


def test_a_mention_equal_to_an_earlier_one_goes_to_the_same_entity_even_when_ambiguous() -> None:
    twin = person("Ramesh Yadav", 14)
    graph = persons(
        person("Ramesh Yadav", 12, gender="M"),
        person("Ramesh Yadav", 13, gender="F"),
        twin,
        twin,
    )

    assert entity_groups(graph, EntityType.PERSON)[2] == [("fir.txt", 14), ("fir.txt", 14)]


def test_entity_confidence_is_the_highest_mention_confidence_and_each_mention_keeps_its_own() -> (
    None
):
    graph = persons(
        person("Ramesh Yadav", 12, confidence=0.5),
        person("Ramesh Yadav", 13, confidence=0.9),
    )

    [entity] = graph.entities
    assert entity.confidence == 0.9
    assert [m.confidence for m in graph.mentions] == [0.5, 0.9]


def test_mention_attributes_keep_what_was_written() -> None:
    graph = persons(
        person(
            "Ramesh Yadav",
            12,
            aliases=("Monu",),
            relative=son_of("Ram Lal"),
            age="34",
            locality="Kherapur",
        )
    )

    [mention] = graph.mentions
    attributes = dict(mention.attributes)
    assert attributes["age"] == "34"
    assert attributes["locality"] == "kherapur"
    assert attributes["locality_raw"] == "Kherapur"
    assert attributes["relative_relation"] == "son"
    assert attributes["relative_name"] == "ram lal"
    assert attributes["aliases"] == ("monu",)


def test_organisations_join_on_equal_name_and_writing_ignoring_case_and_m_s() -> None:
    graph = build_case_graph(
        records(
            orgs=(
                org("M/s Shree Balaji Traders", 12),
                org("SHREE BALAJI TRADERS", 4, "bank.csv"),
                org("Shri Balaji Traders", 13),
            )
        )
    )

    assert entity_groups(graph, EntityType.ORG) == [
        [("fir.txt", 12), ("bank.csv", 4)],
        [("fir.txt", 13)],
    ]


def test_organisations_with_different_suffixes_are_not_joined() -> None:
    graph = build_case_graph(
        records(
            orgs=(
                org("Shree Balaji Traders", 12),
                org("Shree Balaji Enterprises", 13),
                org("Shree Balaji Traders Pvt Ltd", 14),
            )
        )
    )

    assert len(graph.entities) == 3


def test_organisations_in_different_localities_are_not_joined() -> None:
    first: OrgMention = org("Shree Balaji Traders", 12, locality="Rampur")
    second: OrgMention = org("Shree Balaji Traders", 13, locality="Lakeside")

    graph = build_case_graph(records(orgs=(first, second)))

    assert len(graph.entities) == 2


def test_a_person_and_an_organisation_with_one_name_never_join() -> None:
    graph = build_case_graph(
        records(persons=(person("Shree Balaji", 12),), orgs=(org("Shree Balaji Traders", 13),))
    )

    assert {e.type for e in graph.entities} == {EntityType.PERSON, EntityType.ORG}


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("complainant", "accused"),
        ("victim", "suspect"),
        ("informant", "arrested"),
        ("accused", "complainant"),
        ("शिकायतकर्ता", "अभियुक्त"),
        ("पीड़ित", "आरोपी"),
        ("shikayatkarta", "aaropi"),
    ],
)
def test_a_complainant_side_and_an_accused_side_role_never_join(first: str, second: str) -> None:
    graph = persons(
        person("Rajesh Kumar", 12, role=first),
        person("Rajesh Kumar", 13, role=second),
    )

    assert len(graph.entities) == 2


def test_the_same_side_or_a_witness_does_not_stop_a_join() -> None:
    graph = persons(
        person("Rajesh Kumar", 9, role="complainant"),
        person("Rajesh Kumar", 12, role="Complainant"),
        person("Rajesh Kumar", 13, role="witness"),
    )

    assert len(graph.entities) == 1


def test_a_single_token_alias_is_ambiguous_when_a_full_name_in_the_case_holds_the_token() -> None:
    graph = persons(
        person("Ramesh Kasana", 12, aliases=("Kalu",)),
        person("Kalu", 13, aliases=("Pappu",)),
        person("Pappu Sharma", 14),
        person("Pappu", 3, "notes.txt"),
    )

    assert entity_groups(graph, EntityType.PERSON) == [
        [("fir.txt", 12), ("fir.txt", 13)],
        [("fir.txt", 14)],
        [("notes.txt", 3)],
    ]


def test_the_competing_full_name_may_arrive_after_the_bare_name() -> None:
    graph = persons(
        person("Ramesh Kasana", 12, aliases=("Pappu",)),
        person("Pappu", 3, "notes.txt"),
        person("Pappu Sharma", 4, "notes.txt"),
    )

    assert len(graph.entities) == 3


def test_a_plain_alias_chain_stays_transitive() -> None:
    graph = persons(
        person("Ramesh Kasana", 12, aliases=("Kalu",)),
        person("Kalu", 13, aliases=("Pappu",)),
        person("Pappu", 14),
    )

    assert len(graph.entities) == 1


@pytest.mark.parametrize("order", [(0, 1, 2), (2, 0, 1), (1, 2, 0), (2, 1, 0)])
def test_an_account_without_ifsc_is_ambiguous_whatever_the_load_order(
    order: tuple[int, int, int],
) -> None:
    writings = [None, "SYNB0000123", "FAKE0000456"]
    graph = build_case_graph(
        records(
            identifiers=tuple(
                account("5010000019082", 12 + i, ifsc=writings[k]) for i, k in enumerate(order)
            )
        )
    )

    by_ifsc = {e.ifsc: e.entity_id for e in graph.entities}
    assert set(by_ifsc) == {None, "SYNB0000123", "FAKE0000456"}
    assert len(graph.entities) == 3
