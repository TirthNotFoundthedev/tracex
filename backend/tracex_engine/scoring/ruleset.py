"""Ruleset constants of `engine-matching/1.1` (docs/specs/engine-matching.md sections 1, 3, 5).

Weights, caps, the trap factor and the evidence catalogue are ruleset constants, never admin
config; changing any of them bumps `RULESET_VERSION`. Only the band thresholds are admin
config, passed into each run as `Thresholds`.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from tracex_engine.graph import EntityType

RULESET_VERSION = "engine-matching/1.1"

IDENTIFIER_TYPES = frozenset({EntityType.PHONE, EntityType.ACCOUNT, EntityType.VEHICLE})
PARTY_TYPES = frozenset({EntityType.PERSON, EntityType.ORG})

# Tier caps (section 3.1 for identifier pairs, section 5 for person and org pairs).
IDENTIFIER_CAPS = {1: Decimal(100), 2: Decimal(55)}
PARTY_CAPS = {1: Decimal(60), 2: Decimal(55), 3: Decimal(35)}

TRAP_FACTOR = Decimal("0.2")
ATTRIBUTION_FACTOR = {
    "OWNS": Decimal("1.0"),
    "REGISTERED_TO": Decimal("0.5"),
    "MENTIONED_WITH": Decimal("0.2"),
}
# G2 and G5: an attribution or entity below this extraction confidence is never an anchor
# and never legible enough for AUTO (Errata 3).
MIN_CONFIDENCE = 0.7
# G3: a tier counts when it contributes at least this much after caps.
TIER_MIN_CONTRIBUTION = Decimal(15)


class Band(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Severity(StrEnum):
    SOFT = "soft"
    HARD = "hard"
    VETO = "veto"


class ThresholdsError(ValueError):
    """Thresholds outside 70 <= high_min <= 100 and 30 <= medium_min <= high_min - 10."""


@dataclass(frozen=True)
class Thresholds:
    """Band thresholds read once at the start of a run (`matching.thresholds`)."""

    high_min: Decimal
    medium_min: Decimal
    version: int

    @classmethod
    def validated(
        cls, high_min: int | Decimal, medium_min: int | Decimal, version: int
    ) -> "Thresholds":
        high, medium = Decimal(high_min), Decimal(medium_min)
        if not (Decimal(70) <= high <= Decimal(100)):
            raise ThresholdsError("high_min must be between 70 and 100")
        if not (Decimal(30) <= medium <= high - Decimal(10)):
            raise ThresholdsError("medium_min must be between 30 and high_min - 10")
        return cls(high, medium, version)


DEFAULT_THRESHOLDS = Thresholds(Decimal(80), Decimal(45), 1)


@dataclass(frozen=True)
class EvidenceSpec:
    """One catalogue row. `tier` is None for opposing items; `waits_for` is the tier whose
    comparators an item needs and that has not landed yet (None: implemented now)."""

    kind: str
    tier: int | None
    weight: Decimal
    severity: Severity | None = None
    waits_for: int | None = None

    @property
    def opposing(self) -> bool:
        return self.severity is not None

    @property
    def template_key(self) -> str:
        return f"match.evidence.{self.kind.lower()}"


def _spec(
    kind: str,
    tier: int | None,
    weight: int,
    severity: Severity | None = None,
    waits_for: int | None = None,
) -> EvidenceSpec:
    return EvidenceSpec(kind, tier, Decimal(weight), severity, waits_for)


_HARD, _SOFT, _VETO = Severity.HARD, Severity.SOFT, Severity.VETO

CATALOGUE: dict[str, EvidenceSpec] = {
    s.kind: s
    for s in (
        # 3.1 identifier pairs
        _spec("ID_EXACT", 1, 100),
        _spec("PHONE_TRANSPOSED", 2, 55),
        _spec("ACCT_BANK_CONFLICT", None, 0, _VETO),
        # 3.2 person and org pairs, supporting
        _spec("SHARED_PHONE", 1, 45),
        _spec("SHARED_ACCOUNT", 1, 50),
        _spec("SHARED_VEHICLE", 1, 35),
        _spec("PER_NAME_SIM", 2, 30),
        _spec("PER_RELATIVE_NAME", 2, 15),
        _spec("PER_DOB_MATCH", 2, 20),
        _spec("PER_AGE_CLOSE", 2, 10),
        _spec("PER_LOCALITY", 2, 10),
        _spec("PER_NEAR_PHONE", 2, 15),
        _spec("PER_SHARED_NETWORK", 3, 30),
        _spec("PER_CO_LOCATION", 3, 20),
        _spec("ORG_NAME_SIM", 2, 40),
        # 3.3 person pairs, opposing
        _spec("PER_DOB_CONFLICT", None, 40, _HARD),
        _spec("PER_DOB_MISMATCH", None, 15, _SOFT),
        _spec("PER_AGE_CONFLICT", None, 20, _SOFT),
        _spec("PER_GENDER_CONFLICT", None, 50, _HARD),
        _spec("PER_RELATIVE_CONFLICT", None, 20, _SOFT),
    )
}

# PER_AGE_CONFLICT is hard with weight 40 when the ages differ by more than 10 years.
AGE_CONFLICT_HARD_WEIGHT = Decimal(40)


def pending_kinds() -> dict[str, int]:
    """Catalogue items not produced yet, with the tier each waits for."""
    return {k: s.waits_for for k, s in CATALOGUE.items() if s.waits_for is not None}


GATE_TEMPLATE_KEYS = {
    "G1": "match.gate.below_high",
    "G2": "match.gate.no_anchor",
    "G3": "match.gate.single_tier",
    "G4": "match.gate.hard_conflict",
    "G5": "match.gate.low_extraction",
    "G7": "match.gate.org_review_only",
}
G6_CONFLICT = "match.gate.cluster_conflict"
G6_BRIDGE = "match.gate.cluster_bridge"
G6_SAME_CASE = "match.gate.cluster_same_case"

CAP_TEMPLATE_KEY = "match.adjust.cap"
CLAMP_TEMPLATE_KEY = "match.adjust.clamp"
TRAP_TEMPLATE_KEY = "match.modifier.trap_identifier"
