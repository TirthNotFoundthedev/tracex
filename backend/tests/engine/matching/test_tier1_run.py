"""Tier 1 runs on hand-built cases: identifier links, person and org links, traps and guards."""

from decimal import Decimal

from tests.engine.matching.fixtures import ac01_graphs, matcher
from tests.engine.matching.support import (
    AttributionCode,
    account,
    build,
    org,
    owns,
    person,
    phone,
    vehicle,
)
from tracex_engine.graph import CaseGraph
from tracex_engine.matching import LinkState, Matcher, SameAsEdge
from tracex_engine.scoring import Band

PHONE = "9000022310"
ACC = "5010000055501"


def run(*graphs: CaseGraph) -> tuple[Matcher, list[SameAsEdge]]:
    m = matcher(*graphs)
    m.run_matching(input_case_ids=(), triggered_by="u-admin")
    return m, list(m.links.edges())


def by_type(edges: list[SameAsEdge], type_: str) -> list[SameAsEdge]:
    return [e for e in edges if e.entity_type.value == type_]


def gates(edge: SameAsEdge) -> list[str]:
    return [g.gate for g in edge.gates_failed]


def kinds(edge: SameAsEdge) -> set[str]:
    return {i["kind"] for t in edge.evidence["support"] for i in t["items"]} | {
        i["kind"] for i in edge.evidence["against"]
    }


def test_worked_scenario_tier1_links_three_phones_and_suggests_the_person() -> None:
    """AC-01 with Tier 1 only: the phones are AUTO 100; the person pair has the SHARED_PHONE
    anchor (45.0) and waits for PER_NAME_SIM (Tier 2) and PER_SHARED_NETWORK (Tier 3)."""
    _, edges = run(*ac01_graphs())

    phones = by_type(edges, "PHONE")
    assert sorted(e.evidence["support"][0]["items"][0]["params"]["value"] for e in phones) == [
        "9000014471",
        "9000021203",
        "9000028816",
    ]
    assert all(
        (e.state, e.score, e.band) == (LinkState.AUTO, Decimal(100), Band.HIGH) for e in phones
    )
    [irfan] = by_type(edges, "PERSON")
    assert (irfan.state, irfan.score, irfan.band) == (
        LinkState.SUGGESTED,
        Decimal("45.0"),
        Band.MEDIUM,
    )
    assert gates(irfan) == ["G1", "G3"]
    [item] = irfan.evidence["support"][0]["items"]
    assert item["kind"] == "SHARED_PHONE" and item["is_anchor"]
    assert item["params"] == {
        "value": "9000014471",
        "how_a": "OWNS",
        "case_a": "C-101",
        "how_b": "OWNS",
        "case_b": "C-201",
    }
    assert item["sources"] == [
        {"case_id": "C-101", "document_id": "fir.txt", "line": 12},
        {"case_id": "C-201", "document_id": "notes.txt", "line": 3},
    ]
    assert len(edges) == 4


def test_identical_plates_link_automatically() -> None:
    """AC-02."""
    _, [edge] = run(
        build("C-103", [], [], [vehicle("UP32AB1234")]),
        build("C-104", [], [], [vehicle("UP32AB1234", 3, "notes.txt")]),
    )

    assert (edge.state, edge.score, gates(edge)) == (LinkState.AUTO, Decimal(100), [])


def test_same_account_at_two_banks_is_vetoed_and_stores_nothing() -> None:
    """AC-04."""
    m, edges = run(
        build("C-106", [], [], [account("5010000077345", ifsc="SYNB0000123")]),
        build("C-203", [], [], [account("5010000077345", 2, "bank.csv", ifsc="FAKE0000456")]),
    )

    assert edges == []


def test_a_hardly_legible_plate_waits_for_an_officer() -> None:
    """AC-19: score 100, G5 fails, SUGGESTED."""
    _, [edge] = run(
        build("C-121", [], [], [vehicle("UP32CD9021")]),
        build("C-211", [], [], [vehicle("UP32CD9021", 3, "notes.txt", confidence=0.5)]),
    )

    assert (edge.state, edge.band, gates(edge)) == (LinkState.SUGGESTED, Band.HIGH, ["G5"])


def test_veto_inside_a_cluster_holds_the_second_link_for_review() -> None:
    """AC-26: A1~A2 AUTO, A2~A3 SUGGESTED (cluster_conflict), no A1~A3 edge."""
    acc = "5010000088801"
    _, edges = run(
        build("C-124", [], [], [account(acc, 2, "bank.csv", ifsc="SYNB0000123")]),
        build("C-214", [], [], [account(acc, 2, "bank.csv")]),
        build("C-306", [], [], [account(acc, 2, "bank.csv", ifsc="FAKE0000456")]),
    )

    states = {
        (e.case_a, e.case_b): (e.state, [g.template_key for g in e.gates_failed]) for e in edges
    }
    assert states == {
        ("C-124", "C-214"): (LinkState.AUTO, []),
        ("C-214", "C-306"): (LinkState.SUGGESTED, ["match.gate.cluster_conflict"]),
    }


def test_family_phone_links_the_phone_but_never_the_people() -> None:
    """AC-07: SHARED, factor 0.2: 9.0, Low, no person edge."""
    _, edges = run(
        build(
            "C-109",
            attributions=[
                owns(person("Ramesh Yadav", 3, "notes.txt"), phone(PHONE, 3, "notes.txt")),
                owns(person("Sunita Yadav", 4, "notes.txt"), phone(PHONE, 4, "notes.txt")),
            ],
        ),
        build("C-204", attributions=[owns(person("Suresh Yadav"), phone(PHONE))]),
    )

    assert [e.entity_type.value for e in edges] == ["PHONE"]


def test_sim_registered_to_someone_else_is_low_on_tier1() -> None:
    """AC-08: REGISTERED_TO gives a = 0.5: 22.5, Low, no edge, never an anchor."""
    _, edges = run(
        build("C-110", attributions=[owns(person("Vikram Chauhan"), phone(PHONE))]),
        build(
            "C-111",
            attributions=[
                owns(
                    person("Kamla Devi", 2, "sdr.csv"),
                    phone(PHONE, 2, "sdr.csv"),
                    AttributionCode.REGISTERED_TO,
                )
            ],
        ),
    )

    assert [e.entity_type.value for e in edges] == ["PHONE"]


def test_mule_account_links_the_accounts_but_none_of_the_owners() -> None:
    """AC-09: MULTI_USER, factor 0.2: 10.0, Low."""
    graphs = [
        build(
            case,
            attributions=[
                owns(person(name, 2, "bank.csv"), account(ACC, 2, "bank.csv", ifsc="SYNB0000123"))
            ],
        )
        for case, name in (
            ("C-112", "Ajay Pal"),
            ("C-205", "Imran Qureshi"),
            ("C-303", "Deepak Rawat"),
        )
    ]
    _, edges = run(*graphs)

    assert [e.entity_type.value for e in edges] == ["ACCOUNT"] * 3
    assert all(e.state is LinkState.AUTO for e in edges)


def test_a_dob_conflict_takes_the_shared_phone_pair_below_medium() -> None:
    """AC-10 on Tier 1: 45 - 40 = 5.0, Low, no person edge."""
    _, edges = run(
        build(
            "C-113",
            attributions=[owns(person("Arjun Mehra", dob="1990-04-12"), phone("9000046120"))],
        ),
        build(
            "C-114",
            attributions=[owns(person("Arjun Mehra", dob="1978-09-30"), phone("9000046120"))],
        ),
    )

    assert [e.entity_type.value for e in edges] == ["PHONE"]


def test_a_gender_conflict_takes_the_shared_phone_pair_below_medium() -> None:
    """SF-06 on Tier 1: 45 - 50, clamped to 0, no person edge."""
    _, edges = run(
        build(
            "C-133",
            attributions=[owns(person("Pooja Verma", gender="female"), phone("9000088555"))],
        ),
        build(
            "C-217", attributions=[owns(person("Pooja Verma", gender="male"), phone("9000088555"))]
        ),
    )

    assert [e.entity_type.value for e in edges] == ["PHONE"]


def test_mentioned_together_is_weak_and_stores_no_person_edge() -> None:
    """MENTIONED_WITH on both sides: a = 0.2: 9.0, Low."""
    _, edges = run(
        build(
            "C-140",
            attributions=[
                owns(person("Kishore Lal"), phone(PHONE), AttributionCode.MENTIONED_WITH)
            ],
        ),
        build(
            "C-240",
            attributions=[
                owns(person("Kishore Lal"), phone(PHONE), AttributionCode.MENTIONED_WITH)
            ],
        ),
    )

    assert [e.entity_type.value for e in edges] == ["PHONE"]


def test_org_pair_on_a_shared_account_is_review_only() -> None:
    """AC-21 on Tier 1: SHARED_ACCOUNT 50, Medium, G1 and G7."""
    _, edges = run(
        build(
            "C-122",
            attributions=[
                owns(org("M/s Shree Balaji Traders"), account("5010000066602", ifsc="SYNB0000123"))
            ],
        ),
        build(
            "C-126",
            attributions=[
                owns(
                    org("M/s Shri Balaji Trading Co"), account("5010000066602", ifsc="SYNB0000123")
                )
            ],
        ),
    )

    [link] = by_type(edges, "ORG")
    assert (link.state, link.score, gates(link)) == (
        LinkState.SUGGESTED,
        Decimal("50.0"),
        ["G1", "G7"],
    )
    assert kinds(link) == {"SHARED_ACCOUNT"}


def test_a_run_compares_only_pairs_with_an_end_in_scope() -> None:
    graphs = [build(c, [], [], [vehicle("UP32AB1234")]) for c in ("C-103", "C-104", "C-105")]
    m = matcher(*graphs)

    m.run_matching(input_case_ids=("C-105",), triggered_by="u-admin")

    assert {(e.case_a, e.case_b) for e in m.links.edges()} == {
        ("C-103", "C-105"),
        ("C-104", "C-105"),
    }


def test_entities_are_never_touched_by_a_run() -> None:
    graphs = ac01_graphs()
    m = matcher(*graphs)

    m.run_matching(input_case_ids=(), triggered_by="u-admin")

    assert [m.graphs.read_case(g.case_id) for g in graphs] == list(graphs)
