"""Ruleset constants, thresholds validation and the evidence catalogue (spec sections 3 and 5)."""

from decimal import Decimal

import pytest

from tracex_engine.scoring import (
    CATALOGUE,
    DEFAULT_THRESHOLDS,
    RULESET_VERSION,
    Severity,
    Thresholds,
    ThresholdsError,
    pending_kinds,
)

SPEC_KINDS = {
    "ID_EXACT": (1, 100),
    "PHONE_TRANSPOSED": (2, 55),
    "ACCT_BANK_CONFLICT": (None, 0),
    "SHARED_PHONE": (1, 45),
    "SHARED_ACCOUNT": (1, 50),
    "SHARED_VEHICLE": (1, 35),
    "PER_NAME_SIM": (2, 30),
    "PER_RELATIVE_NAME": (2, 15),
    "PER_DOB_MATCH": (2, 20),
    "PER_AGE_CLOSE": (2, 10),
    "PER_LOCALITY": (2, 10),
    "PER_NEAR_PHONE": (2, 15),
    "PER_SHARED_NETWORK": (3, 30),
    "PER_CO_LOCATION": (3, 20),
    "ORG_NAME_SIM": (2, 40),
    "PER_DOB_CONFLICT": (None, 40),
    "PER_DOB_MISMATCH": (None, 15),
    "PER_AGE_CONFLICT": (None, 20),
    "PER_GENDER_CONFLICT": (None, 50),
    "PER_RELATIVE_CONFLICT": (None, 20),
}


def test_ruleset_version_is_the_spec_version() -> None:
    assert RULESET_VERSION == "engine-matching/1.1"


def test_catalogue_holds_every_spec_item_with_its_tier_and_weight() -> None:
    assert {k: (s.tier, int(s.weight)) for k, s in CATALOGUE.items()} == SPEC_KINDS


@pytest.mark.parametrize(
    ("kind", "severity"),
    [
        ("ACCT_BANK_CONFLICT", Severity.VETO),
        ("PER_DOB_CONFLICT", Severity.HARD),
        ("PER_GENDER_CONFLICT", Severity.HARD),
        ("PER_DOB_MISMATCH", Severity.SOFT),
        ("PER_AGE_CONFLICT", Severity.SOFT),
        ("PER_RELATIVE_CONFLICT", Severity.SOFT),
        ("SHARED_PHONE", None),
    ],
)
def test_opposing_items_carry_their_severity(kind: str, severity: Severity | None) -> None:
    assert CATALOGUE[kind].severity is severity


def test_every_catalogue_item_is_produced() -> None:
    assert pending_kinds() == {}
    assert set(CATALOGUE) == set(SPEC_KINDS)


def test_default_thresholds_are_the_spec_defaults() -> None:
    assert Thresholds(Decimal(80), Decimal(45), 1) == DEFAULT_THRESHOLDS


@pytest.mark.parametrize(
    ("high", "medium", "ok"),
    [
        (80, 45, True),
        (90, 45, True),
        (70, 30, True),
        (100, 90, True),
        (65, 45, False),
        (101, 45, False),
        (80, 29, False),
        (80, 71, False),
    ],
)
def test_thresholds_validation(high: int, medium: int, ok: bool) -> None:
    if ok:
        Thresholds.validated(high, medium, 2)
    else:
        with pytest.raises(ThresholdsError):
            Thresholds.validated(high, medium, 2)
