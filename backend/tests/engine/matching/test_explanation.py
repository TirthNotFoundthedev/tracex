"""Explanation payloads against `contracts/explanation.schema.json`, and AC-20 on every edge."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from tests.engine.matching.fixtures import AC01_FIXTURE, ac01_graphs, matcher
from tests.engine.matching.support import account, build, owns, person, phone, vehicle
from tracex_engine.matching import (
    LinkState,
    Matcher,
    NotYetImplemented,
    build_explanation,
    pending_seams,
)
from tracex_engine.matching.corpus import Corpus
from tracex_engine.matching.evidence import Context
from tracex_engine.scoring import pending_kinds

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[4] / "contracts" / "explanation.schema.json").read_text(
        "utf-8"
    )
)
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
ATTRIBUTION_CODES = {"OWNS", "REGISTERED_TO", "MENTIONED_WITH"}


def scenario() -> Matcher:
    """AC-01 with fixture comparators, plus vehicles (one hardly legible), a veto cluster and a
    person pair with a soft opposing item."""
    m = matcher(
        *ac01_graphs(),
        build("C-103", [], [], [vehicle("UP32AB1234")]),
        build("C-211", [], [], [vehicle("UP32AB1234", 3, "notes.txt", confidence=0.5)]),
        build("C-124", [], [], [account("5010000088801", 2, "bank.csv", ifsc="SYNB0000123")]),
        build("C-214", [], [], [account("5010000088801", 2, "bank.csv")]),
        build("C-306", [], [], [account("5010000088801", 2, "bank.csv", ifsc="FAKE0000456")]),
        build(
            "C-150",
            attributions=[owns(person("Lakhan Bisht", dob="1990-01-01"), phone("9000070001"))],
        ),
        build(
            "C-250",
            attributions=[owns(person("Lakhan Bisht", dob="1990-06-01"), phone("9000070001"))],
        ),
        fixture={
            **AC01_FIXTURE,
            frozenset({("C-150", "lakhan bisht"), ("C-250", "lakhan bisht")}): [
                ("PER_NAME_SIM", "1.0")
            ],
        },
    )
    m.run_matching(input_case_ids=(), triggered_by="u-admin")
    return m


def payloads(m: Matcher) -> list[dict[str, Any]]:
    return [build_explanation(e) for e in m.links.edges()]


def test_every_payload_validates_against_the_contract() -> None:
    m = scenario()
    edge = next(e for e in m.links.edges() if e.entity_type.value == "PERSON")
    m.apply_decision(edge.link_id, LinkState.AUTO, LinkState.UNDONE, "u-sup", "d-1", "WRONG", "x")

    found = payloads(m)

    assert {p["entity_type"] for p in found} == {"PHONE", "VEHICLE", "ACCOUNT", "PERSON"}
    for payload in found:
        errors = sorted(VALIDATOR.iter_errors(payload), key=str)
        assert errors == [], (payload["link_id"], [e.message for e in errors][:3])


def test_invariant_holds_by_decimal_equality_on_every_edge() -> None:
    """AC-20."""
    for p in payloads(scenario()):
        subtotal = sum((Decimal(str(t["subtotal"])) for t in p["support"]), Decimal(0))
        against = sum((Decimal(str(i["contribution"])) for i in p["against"]), Decimal(0))
        clamp = Decimal(str(p["clamp_adjustment"]["value"]))
        assert subtotal + against + clamp == Decimal(str(p["score"])), p["link_id"]
        for tier in p["support"]:
            assert Decimal(str(tier["raw"])) + Decimal(
                str(tier["cap_adjustment"]["value"])
            ) == Decimal(str(tier["subtotal"]))


def test_every_item_cites_lines_of_the_two_end_cases_only() -> None:
    """AC-20: at least one source, all in the end cases; `how_*` are attribution codes."""
    for p in payloads(scenario()):
        ends = {r["case_id"] for r in p["records"]}
        items = [i for t in p["support"] for i in t["items"]] + p["against"]
        for item in items:
            assert item["sources"], item["kind"]
            assert {s["case_id"] for s in item["sources"]} <= ends
            for key in ("how_a", "how_b"):
                if key in item["params"]:
                    assert item["params"][key] in ATTRIBUTION_CODES


def test_the_payload_carries_no_english() -> None:
    """AC-20: every line renders from a template key; no free text reaches the payload."""
    m = scenario()
    edge = next(e for e in m.links.edges() if e.entity_type.value == "PERSON")
    m.apply_decision(
        edge.link_id, LinkState.AUTO, LinkState.UNDONE, "u-sup", "d-1", "WRONG", "not him"
    )

    for p in payloads(m):
        text = json.dumps(p)
        assert "not him" not in text and "u-sup" not in text
        items = [i for t in p["support"] for i in t["items"]] + p["against"]
        for item in items:
            assert item["template_key"] == f"match.evidence.{item['kind'].lower()}"
        for entry in p["history"]:
            assert set(entry) == {"from", "to", "at", "reason_code"}


def test_a_soft_opposing_item_is_listed_against_with_its_severity() -> None:
    m = scenario()
    [lakhan] = [
        build_explanation(e)
        for e in m.links.edges()
        if e.entity_type.value == "PERSON" and e.case_a == "C-150"
    ]

    [against] = lakhan["against"]
    assert (against["kind"], against["severity"], against["contribution"]) == (
        "PER_DOB_MISMATCH",
        "soft",
        -15.0,
    )
    assert (lakhan["score"], lakhan["state"]) == (60.0, "SUGGESTED")


def test_every_pending_item_has_a_seam_that_yields_nothing() -> None:
    corpus = Corpus(ac01_graphs())
    a, b = sorted(corpus.entities.values(), key=lambda e: e.entity_id)[:2]
    seams = pending_seams()

    assert {(s.kind, s.tier) for s in seams} == set(pending_kinds().items())
    for seam in (*seams, NotYetImplemented("PER_FUTURE_ITEM", 4)):
        assert (
            list(seam.candidates(corpus)) == []
            and list(seam.items(Context.for_corpus(corpus), a, b)) == []
        )
        assert "not yet implemented" in seam.name


@pytest.mark.parametrize("state", ["AUTO", "SUGGESTED"])
def test_history_of_a_new_link_has_one_creation_entry(state: str) -> None:
    for p in payloads(scenario()):
        if p["state"] == state:
            assert p["history"][0]["from"] is None and p["history"][0]["to"] == state
            assert p["history"][0]["reason_code"] is None
