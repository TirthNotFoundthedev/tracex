"""Tier 3 contextual evidence: B6, PER_SHARED_NETWORK, PER_CO_LOCATION and the spec traps.

Cases are written as case files and read by the real extractor and graph builder. Tier 2
values (name, locality, DOB) are fixtures where a spec row needs them (spec section 8).
"""

import uuid
from collections.abc import Sequence
from decimal import Decimal
from itertools import count

import pytest

from tests.engine.matching.fixtures import FixtureProvider, Who
from tests.engine.matching.support import clock, from_files, store_of
from tests.engine.support import BANK_HEADER, CDR_HEADER, SDR_HEADER, note, notes_file
from tracex_engine.graph import CaseGraph, Entity, EntityType
from tracex_engine.matching import InMemoryLinkStore, LinkState, Matcher, SameAsEdge
from tracex_engine.matching.corpus import Corpus
from tracex_engine.matching.tier3 import Tier3Provider

Call = tuple[str, str, str, str]  # (calling, called, "YYYY-MM-DD", place)
_IDS = count(1)


def case(
    case_id: str,
    owners: Sequence[tuple[str, str]] = (),
    calls: Sequence[Call] = (),
    accounts: Sequence[tuple[str, str, Sequence[str]]] = (),
    registered: Sequence[tuple[str, str]] = (),
) -> CaseGraph:
    """Notes say who uses which phone; `calls` are CDR rows; `accounts` are bank rows
    (holder, account number, numbers paid); `registered` are SIM subscriber rows."""
    files: dict[str, str] = {}
    if owners:
        lines = {
            3 + i: note(f"Number {phone} is used by {name}.")
            for i, (name, phone) in enumerate(owners)
        }
        files["notes.txt"] = notes_file(case_id, lines)
    if calls:
        rows = [
            f"SYN-{case_id}-{n},{day}T10:00:00+05:30,60,{caller},{called},VOICE,CELL{n},{place}"
            for n, (caller, called, day, place) in enumerate(calls, start=1)
        ]
        files["cdr.csv"] = "\n".join([CDR_HEADER, *rows]) + "\n"
    if accounts:
        rows = [
            f"TX{n},2026-09-10,{number},SYNB0000123,{holder.upper()},DR,{paid}@upi,pay,100.00,900.00"
            for n, (holder, number, payees) in enumerate(accounts, start=1)
            for paid in payees
        ]
        files["bank.csv"] = "\n".join([BANK_HEADER, *rows]) + "\n"
    if registered:
        rows = [f"{phone},{name},,,,2024-01-05" for name, phone in registered]
        files["sdr.csv"] = "\n".join([SDR_HEADER, *rows]) + "\n"
    return from_files(case_id, files)


def matcher(
    *graphs: CaseGraph, fixture: dict[frozenset[Who], list[tuple[str, str]]] | None = None
) -> Matcher:
    providers = (*((FixtureProvider(fixture),) if fixture else ()), Tier3Provider())
    return Matcher(
        store_of(*graphs),
        InMemoryLinkStore(),
        providers=providers,
        clock=clock(),
        new_id=lambda: str(uuid.UUID(int=next(_IDS), version=4)),
    )


def person_of(corpus: Corpus, case_id: str, name: str) -> Entity:
    [found] = [
        e
        for e in corpus.entities.values()
        if e.type is EntityType.PERSON and e.case_id == case_id and e.normalized == name
    ]
    return found


def tier3(*graphs: CaseGraph, a: Who, b: Who) -> list[tuple[str, dict[str, object], Decimal]]:
    """Tier 3 items (kind, params, strength) between two named persons."""
    corpus = Corpus(graphs)
    first, second = person_of(corpus, *a), person_of(corpus, *b)
    items = Tier3Provider().items(corpus, first, second)
    return [(i.kind, dict(i.params), i.strength) for i in items]


def numbers(n: int, start: int = 100) -> list[str]:
    return [f"90000{start + i:05d}" for i in range(n)]


def callers_of(phone: str, others: Sequence[str], day: str = "2026-09-10") -> list[Call]:
    return [(other, phone, day, "Hillcrest Market") for other in others]


X: Who = ("C-301", "irfan")
Y: Who = ("C-302", "irfan")


def pair(common: Sequence[str]) -> tuple[CaseGraph, CaseGraph]:
    """Irfan in two cases, each on his own phone, called by the same `common` numbers."""
    return (
        case("C-301", [("Irfan", "9000000001")], callers_of("9000000001", common)),
        case("C-302", [("Irfan", "9000000002")], callers_of("9000000002", common)),
    )


@pytest.mark.parametrize(
    ("k", "strength"),
    [(2, "0.6"), (3, "0.8"), (4, "1.0"), (6, "1.0")],
)
def test_shared_network_strength_follows_k(k: int, strength: str) -> None:
    graphs = pair(numbers(k))

    [(kind, params, got)] = tier3(*graphs, a=X, b=Y)

    assert (kind, got) == ("PER_SHARED_NETWORK", Decimal(strength))
    assert params == {"k": k, "list": numbers(k)}


def test_one_common_number_is_no_network() -> None:
    assert tier3(*pair(numbers(1)), a=X, b=Y) == []


def test_a_hub_number_does_not_count() -> None:
    hub = "9000099999"
    crowd = [f"91000{n:05d}" for n in range(25)]
    graphs = (
        case(
            "C-301",
            [("Irfan", "9000000001")],
            callers_of("9000000001", [hub, "9000000101"]) + callers_of(hub, crowd),
        ),
        case("C-302", [("Irfan", "9000000002")], callers_of("9000000002", [hub, "9000000101"])),
    )

    assert tier3(*graphs, a=X, b=Y) == []


def test_a_family_number_does_not_count_but_a_path_through_it_does() -> None:
    """The family phone is SHARED: not counted, yet the numbers behind it are reachable."""
    family = "9000000001"
    graphs = (
        case(
            "C-301",
            [("Irfan", family), ("Sunita", family)],
            callers_of(family, numbers(2)),
        ),
        case("C-302", [("Irfan", "9000000002")], callers_of("9000000002", numbers(2))),
    )

    [(kind, params, _)] = tier3(*graphs, a=X, b=Y)

    assert (kind, params["k"]) == ("PER_SHARED_NETWORK", 2)


def test_a_phone_both_own_is_tier_1_and_is_left_out_of_the_count() -> None:
    both = "9000000001"
    graphs = (
        case("C-301", [("Irfan", both)], callers_of(both, numbers(2))),
        case("C-302", [("Irfan", both)], callers_of(both, numbers(2))),
    )

    [(_, params, strength)] = tier3(*graphs, a=X, b=Y)

    assert params["list"] == numbers(2) and strength == Decimal("0.6")


def test_calls_in_either_direction_count() -> None:
    out = [("9000000001", n, "2026-09-10", "Hillcrest Market") for n in numbers(2)]
    graphs = (
        case("C-301", [("Irfan", "9000000001")], out),
        case("C-302", [("Irfan", "9000000002")], callers_of("9000000002", numbers(2))),
    )

    [(kind, params, _)] = tier3(*graphs, a=X, b=Y)

    assert (kind, params["k"]) == ("PER_SHARED_NETWORK", 2)


def test_a_sim_registered_in_a_name_is_not_a_hop() -> None:
    """Kamla Devi is only the subscriber of the phone, so its callers are not her network."""
    graphs = (
        case("C-301", [("Irfan", "9000000001")], callers_of("9000000001", numbers(2))),
        case(
            "C-302",
            calls=callers_of("9000000002", numbers(2)),
            registered=[("Kamla Devi", "9000000002")],
        ),
    )

    assert tier3(*graphs, a=X, b=("C-302", "kamla devi")) == []


def test_sources_are_lines_of_the_two_end_cases_and_name_no_third_case() -> None:
    corpus = Corpus(
        (
            *pair(numbers(3)),
            case("C-303", [("Irfan", "9000000003")], callers_of("9000000003", numbers(3))),
        )
    )
    first, second = person_of(corpus, "C-301", "irfan"), person_of(corpus, "C-302", "irfan")

    [item] = Tier3Provider().items(corpus, first, second)

    assert {s.case_id for s in item.sources} == {"C-301", "C-302"}
    assert {s.document_id for s in item.sources} == {"notes.txt", "cdr.csv"}
    assert all("C-303" not in str(v) for v in item.params.values())


def test_blocking_pairs_persons_sharing_two_network_numbers_across_cases() -> None:
    graphs = (
        *pair(numbers(2)),
        case("C-303", [("Irfan", "9000000003")], callers_of("9000000003", numbers(1))),
    )
    corpus = Corpus(graphs)

    found = {
        tuple(sorted(corpus.entities[e].case_id for e in p))
        for p in Tier3Provider().candidates(corpus)
    }

    assert found == {("C-301", "C-302")}


def test_blocking_drops_hub_numbers_and_same_case_pairs() -> None:
    hub = "9000099999"
    crowd = [f"91000{n:05d}" for n in range(25)]
    graphs = (
        case(
            "C-301",
            [("Irfan", "9000000001"), ("Salim", "9000000004")],
            callers_of("9000000001", [hub, "9000000101"])
            + callers_of("9000000004", [hub, "9000000101"])
            + callers_of(hub, crowd),
        ),
        case("C-302", [("Irfan", "9000000002")], callers_of("9000000002", [hub, "9000000101"])),
    )

    assert list(Tier3Provider().candidates(Corpus(graphs))) == []


def seen(phone: str, units: Sequence[tuple[str, str]]) -> list[Call]:
    return [(phone, f"910000{n:04d}", day, place) for n, (place, day) in enumerate(units)]


@pytest.mark.parametrize(
    ("a_units", "b_units", "k", "strength"),
    [
        (
            [("Market", "2026-09-10"), ("Station", "2026-09-12")],
            [("Market", "2026-09-10"), ("Station", "2026-09-12")],
            2,
            "0.7",
        ),
        (
            [("Market", "2026-09-10"), ("Station", "2026-09-12")],
            [("Market", "2026-09-11"), ("Temple", "2026-09-11")],
            None,
            None,
        ),
        (
            [("Market", "2026-09-10"), ("Station", "2026-09-12"), ("Temple", "2026-09-14")],
            [("Market", "2026-09-11"), ("Station", "2026-09-12"), ("Temple", "2026-09-13")],
            3,
            "1.0",
        ),
        (
            [("Market", "2026-09-10"), ("Market", "2026-09-10")],
            [("Market", "2026-09-10"), ("Market", "2026-09-10")],
            None,
            None,
        ),
        (
            [("Market", "2026-09-10"), ("Market", "2026-09-11")],
            [("Market", "2026-09-10")],
            None,
            None,
        ),
        (
            [("Market", "2026-09-10"), ("Station", "2026-09-12")],
            [("Market", "2026-09-12"), ("Station", "2026-09-10")],
            None,
            None,
        ),
    ],
    ids=[
        "two",
        "wrong-place-for-one",
        "three-within-a-day",
        "same-unit-twice",
        "one-to-one",
        "dates-too-far",
    ],
)
def test_co_location_counts_place_date_pairs_within_a_day(
    a_units: list[tuple[str, str]],
    b_units: list[tuple[str, str]],
    k: int | None,
    strength: str | None,
) -> None:
    graphs = (
        case("C-301", [("Irfan", "9000000001")], seen("9000000001", a_units)),
        case("C-302", [("Irfan", "9000000002")], seen("9000000002", b_units)),
    )

    got = [(p, s) for kind, p, s in tier3(*graphs, a=X, b=Y) if kind == "PER_CO_LOCATION"]

    assert got == ([] if k is None else [({"k": k}, Decimal(str(strength)))])


def test_co_location_ignores_a_family_phone() -> None:
    units = [("Market", "2026-09-10"), ("Station", "2026-09-12")]
    graphs = (
        case(
            "C-301",
            [("Irfan", "9000000001"), ("Sunita", "9000000001")],
            seen("9000000001", units),
        ),
        case("C-302", [("Irfan", "9000000002")], seen("9000000002", units)),
    )

    assert [i for i in tier3(*graphs, a=X, b=Y) if i[0] == "PER_CO_LOCATION"] == []


def test_co_location_cites_one_row_per_place_date_on_each_side() -> None:
    units = [("Market", "2026-09-10"), ("Station", "2026-09-12")]
    graphs = (
        case("C-301", [("Irfan", "9000000001")], seen("9000000001", units)),
        case("C-302", [("Irfan", "9000000002")], seen("9000000002", units)),
    )
    corpus = Corpus(graphs)
    items = Tier3Provider().items(
        corpus, person_of(corpus, "C-301", "irfan"), person_of(corpus, "C-302", "irfan")
    )

    [co] = [i for i in items if i.kind == "PER_CO_LOCATION"]

    assert sorted((s.case_id, s.document_id, s.line) for s in co.sources) == [
        ("C-301", "cdr.csv", 2),
        ("C-301", "cdr.csv", 3),
        ("C-302", "cdr.csv", 2),
        ("C-302", "cdr.csv", 3),
    ]


def edges_between(m: Matcher, *cases: str) -> list[SameAsEdge]:
    return [
        e
        for e in m.links.edges()
        if e.entity_type is EntityType.PERSON and {e.case_a, e.case_b} == set(cases)
    ]


def kinds(edge: SameAsEdge) -> list[str]:
    return [i["kind"] for t in edge.evidence["support"] for i in t["items"]]


def test_ac01_with_real_tier_3_the_network_is_18_and_the_person_is_auto_85_5() -> None:
    """The worked scenario on hand-written cases; only the name similarity is a fixture."""
    c101 = case(
        "C-101",
        [("Mohd Irfan", "9000014471")],
        accounts=[("Mohd Irfan", "5010000019082", ["9000021203", "9000028816"])],
    )
    c201 = case(
        "C-201",
        [("Irfan bhai", "9000014471")],
        [
            ("9000021203", "9000014471", "2026-09-18", "Hillcrest Market"),
            ("9000028816", "9000014471", "2026-09-19", "Hillcrest Market"),
        ],
    )
    m = matcher(
        c101,
        c201,
        fixture={
            frozenset({("C-101", "mohammad irfan"), ("C-201", "irfan")}): [("PER_NAME_SIM", "0.75")]
        },
    )

    m.run_matching(triggered_by="u-hari")

    [edge] = edges_between(m, "C-101", "C-201")
    network = next(
        i for t in edge.evidence["support"] for i in t["items"] if i["kind"] == "PER_SHARED_NETWORK"
    )
    assert (edge.state, edge.score) == (LinkState.AUTO, Decimal("85.5"))
    assert (network["strength"], network["contribution"]) == (0.6, 18.0)
    assert network["params"] == {"k": 2, "list": ["9000021203", "9000028816"]}


def test_ac07_family_phone_gives_33_low_and_no_person_edge() -> None:
    phone = "9000022310"
    m = matcher(
        case(
            "C-109",
            [("Ramesh Yadav", phone), ("Sunita Yadav", phone)],
            callers_of(phone, numbers(3)),
        ),
        case("C-204", [("Suresh Yadav", phone)], callers_of(phone, numbers(3))),
    )

    m.run_matching(triggered_by="u-hari")

    assert edges_between(m, "C-109", "C-204") == []
    corpus = Corpus.load(m.graphs)
    ramesh, suresh = (
        person_of(corpus, "C-109", "ramesh yadav"),
        person_of(corpus, "C-204", "suresh yadav"),
    )
    assert [i.kind for i in Tier3Provider().items(corpus, ramesh, suresh)] == ["PER_SHARED_NETWORK"]


def test_ac08_sim_in_another_name_is_suggested_56_5_never_auto() -> None:
    phone = "9000035562"
    common = numbers(4)
    m = matcher(
        case("C-110", [("Vikram Chauhan", phone)], callers_of(phone, common)),
        case(
            "C-111",
            accounts=[("Kamla Devi", "5010000012345", common)],
            registered=[("Kamla Devi", phone)],
        ),
        fixture={
            frozenset({("C-110", "vikram chauhan"), ("C-111", "kamla devi")}): [
                ("PER_LOCALITY", "0.4")
            ]
        },
    )

    m.run_matching(triggered_by="u-hari")

    [edge] = edges_between(m, "C-110", "C-111")
    assert (edge.state, edge.score) == (LinkState.SUGGESTED, Decimal("56.5"))
    assert sorted(kinds(edge)) == ["PER_LOCALITY", "PER_SHARED_NETWORK", "SHARED_PHONE"]


def test_ac09_mule_account_gives_34_low() -> None:
    acc = "5010000055501"
    common = numbers(3)
    m = matcher(
        case("C-401", accounts=[("Ajay Pal", acc, common)]),
        case("C-402", accounts=[("Imran Qureshi", acc, common)]),
        case("C-403", accounts=[("Deepak Rawat", acc, [])]),
    )

    m.run_matching(triggered_by="u-hari")

    assert edges_between(m, "C-401", "C-402") == []
    corpus = Corpus.load(m.graphs)
    ajay, imran = (
        person_of(corpus, "C-401", "ajay pal"),
        person_of(corpus, "C-402", "imran qureshi"),
    )
    [item] = Tier3Provider().items(corpus, ajay, imran)
    assert (item.kind, item.params["k"], item.contribution) == (
        "PER_SHARED_NETWORK",
        3,
        Decimal("24.0"),
    )


def test_ac22_cross_district_same_name_same_phone_is_auto_99() -> None:
    phone = "9000062201"
    common = numbers(3)
    m = matcher(
        case("C-123", [("Naveen Tomar", phone)], callers_of(phone, common)),
        case("C-213", [("Naveen Tomar", phone)], callers_of(phone, common)),
        fixture={
            frozenset({("C-123", "naveen tomar"), ("C-213", "naveen tomar")}): [
                ("PER_NAME_SIM", "1.0")
            ]
        },
    )

    m.run_matching(triggered_by="u-hari")

    [edge] = edges_between(m, "C-123", "C-213")
    assert (edge.state, edge.score) == (LinkState.AUTO, Decimal("99.0"))


def test_ac11_pile_of_weak_evidence_is_capped_at_90_and_waits_for_an_officer() -> None:
    """Tier 2 items are fixtures (raw 72.0); real Tier 3 gives network k=4 and co-location k=3."""
    common = numbers(4)
    places = [
        ("Market", "2026-09-10"),
        ("Market", "2026-09-11"),
        ("Station", "2026-09-12"),
        ("Station", "2026-09-12"),
    ]
    calls_a = [
        ("9000000001", n, day, place) for n, (place, day) in zip(common, places, strict=True)
    ]
    calls_b = [
        ("9000000002", n, day, place) for n, (place, day) in zip(common, places, strict=True)
    ]
    k1, k2 = ("C-117", "rare namesake"), ("C-125", "rare namesake")
    m = matcher(
        case("C-117", [("Rare Namesake", "9000000001")], calls_a),
        case("C-125", [("Rare Namesake", "9000000002")], calls_b),
        fixture={
            frozenset({k1, k2}): [
                ("PER_NAME_SIM", "0.95"),
                ("PER_DOB_MATCH", "1.0"),
                ("PER_LOCALITY", "1.0"),
                ("PER_RELATIVE_NAME", "0.9"),
            ]
        },
    )

    m.run_matching(triggered_by="u-hari")

    [edge] = edges_between(m, "C-117", "C-125")
    assert (edge.state, edge.score) == (LinkState.SUGGESTED, Decimal("90.0"))
    assert [g.gate for g in edge.gates_failed] == ["G2"]
    assert {t["tier"]: (t["raw"], t["subtotal"]) for t in edge.evidence["support"]} == {
        2: (72.0, 55.0),
        3: (50.0, 35.0),
    }
