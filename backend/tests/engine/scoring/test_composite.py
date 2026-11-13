"""Composite score, caps, clamp and bands (matching spec section 5), exact decimal arithmetic."""

from decimal import Decimal

import pytest

from tests.engine.scoring.support import item, shared_phone
from tracex_engine.graph import EntityType
from tracex_engine.scoring import (
    DEFAULT_THRESHOLDS,
    Band,
    Breakdown,
    EvidenceItem,
    band_of,
    compose,
)

PERSON = EntityType.PERSON


def invariant_holds(b: Breakdown) -> bool:
    total = sum((t.subtotal for t in b.support), Decimal(0))
    total += sum((i.contribution for i in b.against), Decimal(0))
    return total + b.clamp_adjustment == b.score and all(
        t.raw + t.cap_adjustment == t.subtotal for t in b.support
    )


CASES: list[tuple[str, EntityType, list[EvidenceItem], str, Band]] = [
    (
        "AC-01 worked numbers",
        PERSON,
        [shared_phone(), item("PER_NAME_SIM", "0.75"), item("PER_SHARED_NETWORK", "0.6")],
        "85.5",
        Band.HIGH,
    ),
    (
        "AC-01 Tier 1 only",
        PERSON,
        [shared_phone()],
        "45.0",
        Band.MEDIUM,
    ),
    (
        "AC-05 no anchor",
        PERSON,
        [item("PER_NAME_SIM", "0.94"), item("PER_AGE_CLOSE"), item("PER_LOCALITY")],
        "48.2",
        Band.MEDIUM,
    ),
    (
        "AC-06 common name",
        PERSON,
        [item("PER_NAME_SIM", "0.4"), item("PER_LOCALITY", "0.4")],
        "16.0",
        Band.LOW,
    ),
    (
        "AC-07 family phone",
        PERSON,
        [shared_phone("0.2", anchor=False), item("PER_SHARED_NETWORK", "0.8")],
        "33.0",
        Band.LOW,
    ),
    (
        "AC-10 boundary inclusive",
        PERSON,
        [
            shared_phone(),
            item("PER_NAME_SIM"),
            item("PER_LOCALITY"),
            item("PER_DOB_CONFLICT"),
        ],
        "45.0",
        Band.MEDIUM,
    ),
    (
        "AC-11 caps",
        PERSON,
        [
            item("PER_NAME_SIM", "0.95"),
            item("PER_DOB_MATCH"),
            item("PER_LOCALITY"),
            item("PER_RELATIVE_NAME", "0.9"),
            item("PER_SHARED_NETWORK"),
            item("PER_CO_LOCATION"),
        ],
        "90.0",
        Band.HIGH,
    ),
    ("AC-02 vehicle", EntityType.VEHICLE, [item("ID_EXACT")], "100.0", Band.HIGH),
    ("AC-03 transposed", EntityType.PHONE, [item("PHONE_TRANSPOSED")], "55.0", Band.MEDIUM),
    (
        "clamp at zero",
        PERSON,
        [shared_phone(), item("PER_GENDER_CONFLICT")],
        "0.0",
        Band.LOW,
    ),
]


@pytest.mark.parametrize(
    ("entity_type", "items", "score", "band"),
    [c[1:] for c in CASES],
    ids=[c[0] for c in CASES],
)
def test_score_and_band_follow_the_worked_numbers(
    entity_type: EntityType, items: list[EvidenceItem], score: str, band: Band
) -> None:
    breakdown = compose(entity_type, items)

    assert breakdown.score == Decimal(score)
    assert band_of(breakdown, DEFAULT_THRESHOLDS) is band
    assert invariant_holds(breakdown)


def test_tier_caps_are_their_own_lines() -> None:
    breakdown = compose(PERSON, [c for c in CASES if c[0] == "AC-11 caps"][0][2])

    tiers = {t.tier: t for t in breakdown.support}
    assert (tiers[2].raw, tiers[2].cap_adjustment, tiers[2].subtotal) == (
        Decimal("72.0"),
        Decimal("-17.0"),
        Decimal("55.0"),
    )
    assert (tiers[3].raw, tiers[3].cap_adjustment, tiers[3].subtotal) == (
        Decimal("50.0"),
        Decimal("-15.0"),
        Decimal("35.0"),
    )


def test_two_shared_identifiers_are_capped_at_tier_one_sixty() -> None:
    account = item("SHARED_ACCOUNT", anchor=True)

    breakdown = compose(PERSON, [shared_phone(), account])

    assert breakdown.score == Decimal("60.0")
    assert breakdown.support[0].cap_adjustment == Decimal("-35.0")


def test_identifier_tier_one_cap_is_one_hundred() -> None:
    assert compose(EntityType.PHONE, [item("ID_EXACT")]).support[0].cap == Decimal(100)


@pytest.mark.parametrize(
    ("kind", "strength", "contribution"),
    [
        ("PER_NAME_SIM", "0.75", "22.5"),
        ("PER_NAME_SIM", "0.94", "28.2"),
        ("SHARED_PHONE", "0.21", "9.5"),
        ("SHARED_PHONE", "0.2", "9.0"),
        ("PER_AGE_CONFLICT", "1.0", "-20.0"),
    ],
)
def test_each_contribution_rounds_half_up_to_one_decimal(
    kind: str, strength: str, contribution: str
) -> None:
    assert item(kind, strength).contribution == Decimal(contribution)


def test_a_veto_forces_low_whatever_the_score() -> None:
    breakdown = compose(EntityType.ACCOUNT, [item("ID_EXACT"), item("ACCT_BANK_CONFLICT")])

    assert breakdown.vetoed
    assert band_of(breakdown, DEFAULT_THRESHOLDS) is Band.LOW


def test_items_are_split_into_support_by_tier_and_against() -> None:
    breakdown = compose(
        PERSON, [item("PER_SHARED_NETWORK", "0.6"), shared_phone(), item("PER_DOB_MISMATCH")]
    )

    assert [t.tier for t in breakdown.support] == [1, 3]
    assert [i.kind for i in breakdown.against] == ["PER_DOB_MISMATCH"]
    assert breakdown.against[0].contribution == Decimal("-15.0")
