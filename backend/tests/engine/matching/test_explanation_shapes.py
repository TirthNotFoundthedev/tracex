"""Payload shapes the kit does not produce yet: caps, clamp, a hard opposing item, a trap
modifier (review of PR #28, minor 6). Tier 2 and 3 values are fixture comparators. Also checks
the contract's own example payloads against its schema."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from tests.engine.matching.fixtures import matcher
from tests.engine.matching.support import build, owns, person, phone
from tracex_engine.matching import build_explanation

CONTRACTS = Path(__file__).resolve().parents[4] / "contracts"
VALIDATOR = Draft202012Validator(
    json.loads((CONTRACTS / "explanation.schema.json").read_text("utf-8")),
    format_checker=FormatChecker(),
)
EXAMPLES = sorted((CONTRACTS / "examples").glob("*.json"))


def pair(name: str, cases: tuple[str, str]) -> frozenset[tuple[str, str]]:
    return frozenset({(cases[0], name), (cases[1], name)})


def shapes() -> dict[str, dict[str, Any]]:
    """One person pair per shape, keyed by its first case."""
    arjun = [
        build(c, attributions=[owns(person("Arjun Mehra", dob=d), phone("9000046120"))])
        for c, d in (("C-113", "1990-04-12"), ("C-114", "1978-09-30"))
    ]
    parminder = [build(c, [person("Parminder Atwal")]) for c in ("C-115", "C-125")]
    rich = [
        build(
            c,
            attributions=[
                owns(person("Harnam Gill"), phone("9000060001")),
                owns(person("Harnam Gill", 13), phone("9000060002", 13)),
            ],
        )
        for c in ("C-160", "C-260")
    ]
    family = [
        build(
            "C-109",
            attributions=[
                owns(person("Ramesh Yadav", 3, "notes.txt"), phone("9000022310", 3, "notes.txt")),
                owns(person("Sunita Yadav", 4, "notes.txt"), phone("9000022310", 4, "notes.txt")),
            ],
        ),
        build("C-204", attributions=[owns(person("Ramesh Yadav"), phone("9000022310"))]),
    ]
    fixture = {
        pair("arjun mehra", ("C-113", "C-114")): [("PER_NAME_SIM", "1.0"), ("PER_LOCALITY", "1.0")],
        pair("parminder atwal", ("C-115", "C-125")): [
            ("PER_NAME_SIM", "0.95"),
            ("PER_DOB_MATCH", "1.0"),
            ("PER_LOCALITY", "1.0"),
            ("PER_RELATIVE_NAME", "0.9"),
            ("PER_SHARED_NETWORK", "1.0"),
            ("PER_CO_LOCATION", "1.0"),
        ],
        pair("harnam gill", ("C-160", "C-260")): [
            ("PER_NAME_SIM", "1.0"),
            ("PER_RELATIVE_NAME", "1.0"),
            ("PER_LOCALITY", "1.0"),
            ("PER_SHARED_NETWORK", "1.0"),
            ("PER_CO_LOCATION", "1.0"),
        ],
        pair("ramesh yadav", ("C-109", "C-204")): [
            ("PER_NAME_SIM", "1.0"),
            ("PER_SHARED_NETWORK", "0.8"),
        ],
    }
    m = matcher(*arjun, *parminder, *rich, *family, fixture=fixture)
    m.run_matching(input_case_ids=(), triggered_by="u-admin")
    return {
        e.case_a: build_explanation(e) for e in m.links.edges() if e.entity_type.value == "PERSON"
    }


def test_ac10_conflict_payload_is_45_suggested_with_a_hard_item() -> None:
    p = shapes()["C-113"]

    assert (p["score"], p["state"]) == (45.0, "SUGGESTED")
    assert [(i["kind"], i["severity"], i["contribution"]) for i in p["against"]] == [
        ("PER_DOB_CONFLICT", "hard", -40.0)
    ]
    assert [g["gate"] for g in p["gates"]["failed"]] == ["G1", "G4"]


def test_ac11_caps_payload_is_90_suggested_with_cap_lines() -> None:
    p = shapes()["C-115"]

    tiers = {t["tier"]: t for t in p["support"]}
    assert (tiers[2]["raw"], tiers[2]["cap_adjustment"]["value"], tiers[2]["subtotal"]) == (
        72.0,
        -17.0,
        55.0,
    )
    assert (tiers[3]["raw"], tiers[3]["cap_adjustment"]["value"]) == (50.0, -15.0)
    assert (p["score"], p["state"], [g["gate"] for g in p["gates"]["failed"]]) == (
        90.0,
        "SUGGESTED",
        ["G2"],
    )


def test_a_pile_over_100_is_clamped_on_its_own_line() -> None:
    p = shapes()["C-160"]

    assert (p["clamp_adjustment"]["value"], p["score"], p["state"]) == (-50.0, 100.0, "AUTO")


def test_a_trap_identifier_item_carries_its_modifier() -> None:
    p = shapes()["C-109"]

    [item] = p["support"][0]["items"]
    assert (item["kind"], item["contribution"], item["is_anchor"]) == ("SHARED_PHONE", 9.0, False)
    assert item["modifiers"] == [
        {"code": "SHARED", "factor": 0.2, "template_key": "match.modifier.trap_identifier"}
    ]


def test_every_shape_validates_and_keeps_the_invariant() -> None:
    found = shapes()
    assert set(found) == {"C-113", "C-115", "C-160", "C-109"}
    for p in found.values():
        assert list(VALIDATOR.iter_errors(p)) == [], p["link_id"]
        total = sum((Decimal(str(t["subtotal"])) for t in p["support"]), Decimal(0))
        total += sum((Decimal(str(i["contribution"])) for i in p["against"]), Decimal(0))
        assert total + Decimal(str(p["clamp_adjustment"]["value"])) == Decimal(str(p["score"]))


@pytest.mark.parametrize("example", EXAMPLES, ids=[e.name for e in EXAMPLES])
def test_contract_examples_validate_against_the_schema(example: Path) -> None:
    assert len(EXAMPLES) == 4
    assert list(VALIDATOR.iter_errors(json.loads(example.read_text("utf-8")))) == []
