"""Gates G1-G7 and the High rule (matching spec section 5), table-driven."""

from decimal import Decimal

import pytest

from tests.engine.scoring.support import item, shared_phone
from tracex_engine.graph import EntityType
from tracex_engine.scoring import (
    DEFAULT_THRESHOLDS,
    ClusterVerdict,
    EvidenceItem,
    FailedGate,
    Thresholds,
    compose,
    evaluate_gates,
)

PERSON, ORG, PHONE = EntityType.PERSON, EntityType.ORG, EntityType.PHONE
CLEAR = (0.9, 0.9)
SAFE = ClusterVerdict()

AC01 = [shared_phone(), item("PER_NAME_SIM", "0.75"), item("PER_SHARED_NETWORK", "0.6")]
AC11 = [
    item("PER_NAME_SIM", "0.95"),
    item("PER_DOB_MATCH"),
    item("PER_LOCALITY"),
    item("PER_RELATIVE_NAME", "0.9"),
    item("PER_SHARED_NETWORK"),
    item("PER_CO_LOCATION"),
]

CASES: list[
    tuple[str, EntityType, list[EvidenceItem], tuple[float, float], ClusterVerdict, str]
] = [
    ("AC-01 all pass", PERSON, AC01, CLEAR, SAFE, ""),
    ("AC-01 Tier 1 only", PERSON, [shared_phone()], CLEAR, SAFE, "G1 G3"),
    ("AC-11 no anchor", PERSON, AC11, CLEAR, SAFE, "G2"),
    (
        "AC-10 hard conflict",
        PERSON,
        [shared_phone(), item("PER_NAME_SIM"), item("PER_LOCALITY"), item("PER_DOB_CONFLICT")],
        CLEAR,
        SAFE,
        "G1 G4",
    ),
    (
        "trap item is not an anchor",
        PERSON,
        [shared_phone("0.2", anchor=False), item("PER_NAME_SIM"), item("PER_SHARED_NETWORK")],
        CLEAR,
        SAFE,
        "G1 G2",
    ),
    ("AC-19 low extraction", EntityType.VEHICLE, [item("ID_EXACT")], (0.9, 0.5), SAFE, "G5"),
    ("AC-02 identifier passes", EntityType.VEHICLE, [item("ID_EXACT")], CLEAR, SAFE, ""),
    ("AC-03 identifier below high", PHONE, [item("PHONE_TRANSPOSED")], CLEAR, SAFE, "G1"),
    (
        "AC-26 cluster conflict",
        EntityType.ACCOUNT,
        [item("ID_EXACT")],
        CLEAR,
        ClusterVerdict(conflict=True),
        "G6:match.gate.cluster_conflict",
    ),
    (
        "AC-13 bridge",
        PERSON,
        AC01,
        CLEAR,
        ClusterVerdict(bridge=True),
        "G6:match.gate.cluster_bridge",
    ),
    (
        "AC-14 same case",
        PERSON,
        AC01,
        CLEAR,
        ClusterVerdict(same_case=True),
        "G6:match.gate.cluster_same_case",
    ),
    (
        "AC-21 org review only",
        ORG,
        [item("SHARED_ACCOUNT", anchor=True), item("ORG_NAME_SIM", "0.9")],
        CLEAR,
        SAFE,
        "G7",
    ),
    ("org Tier 1 only", ORG, [item("SHARED_ACCOUNT", anchor=True)], CLEAR, SAFE, "G1 G7"),
]

KEYS = {
    "G1": "match.gate.below_high",
    "G2": "match.gate.no_anchor",
    "G3": "match.gate.single_tier",
    "G4": "match.gate.hard_conflict",
    "G5": "match.gate.low_extraction",
    "G7": "match.gate.org_review_only",
}


def expected(failed: str) -> tuple[FailedGate, ...]:
    out = []
    for token in failed.split():
        gate, _, key = token.partition(":")
        out.append(FailedGate(gate, key or KEYS[gate]))
    return tuple(out)


@pytest.mark.parametrize(
    ("entity_type", "items", "confidences", "cluster", "failed"),
    [c[1:] for c in CASES],
    ids=[c[0] for c in CASES],
)
def test_failed_gates(
    entity_type: EntityType,
    items: list[EvidenceItem],
    confidences: tuple[float, float],
    cluster: ClusterVerdict,
    failed: str,
) -> None:
    gates = evaluate_gates(
        compose(entity_type, items),
        thresholds=DEFAULT_THRESHOLDS,
        confidences=confidences,
        cluster=cluster,
    )

    assert gates == expected(failed)


def test_g1_follows_the_run_thresholds() -> None:
    """AC-18: with high_min 90 the AC-01 person pair (85.5) fails G1."""
    raised = Thresholds(Decimal(90), Decimal(45), 2)

    gates = evaluate_gates(
        compose(PERSON, AC01), thresholds=raised, confidences=CLEAR, cluster=SAFE
    )

    assert gates == expected("G1")


def test_g3_counts_tiers_after_caps() -> None:
    """A tier contributing 14.9 after caps does not count as a second tier."""
    items = [shared_phone(), shared_phone(), item("PER_LOCALITY", "1.0"), item("PER_AGE_CLOSE")]

    gates = evaluate_gates(
        compose(PERSON, items), thresholds=DEFAULT_THRESHOLDS, confidences=CLEAR, cluster=SAFE
    )

    assert FailedGate("G3", KEYS["G3"]) not in gates
    items = [shared_phone(), shared_phone(), item("PER_LOCALITY", "0.4"), item("PER_AGE_CLOSE")]
    gates = evaluate_gates(
        compose(PERSON, items), thresholds=DEFAULT_THRESHOLDS, confidences=CLEAR, cluster=SAFE
    )
    assert FailedGate("G3", KEYS["G3"]) in gates
