"""Composite score: tier sums, cap adjustments, opposing items and the clamp (spec section 5).

All arithmetic is exact decimal. Rounding each contribution is the only rounding, so the
invariant sum(subtotals) + sum(against) + clamp_adjustment == score holds by equality.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from tracex_engine.graph import EntityType
from tracex_engine.scoring.evidence import EvidenceItem
from tracex_engine.scoring.ruleset import (
    IDENTIFIER_CAPS,
    IDENTIFIER_TYPES,
    PARTY_CAPS,
    Band,
    Severity,
    Thresholds,
)

ZERO = Decimal("0.0")
HUNDRED = Decimal("100.0")


@dataclass(frozen=True)
class TierTotal:
    """One tier of supporting evidence; `cap_adjustment` <= 0 is its own line."""

    tier: int
    cap: Decimal
    raw: Decimal
    cap_adjustment: Decimal
    subtotal: Decimal
    items: tuple[EvidenceItem, ...]


@dataclass(frozen=True)
class Breakdown:
    """The scored evidence of one pair. Tiers without items are omitted."""

    entity_type: EntityType
    support: tuple[TierTotal, ...]
    against: tuple[EvidenceItem, ...]
    clamp_adjustment: Decimal
    score: Decimal

    @property
    def vetoed(self) -> bool:
        return any(i.severity is Severity.VETO for i in self.against)

    @property
    def items(self) -> tuple[EvidenceItem, ...]:
        return tuple(i for t in self.support for i in t.items) + self.against


def caps_for(entity_type: EntityType) -> dict[int, Decimal]:
    return IDENTIFIER_CAPS if entity_type in IDENTIFIER_TYPES else PARTY_CAPS


def compose(entity_type: EntityType, items: Iterable[EvidenceItem]) -> Breakdown:
    """Score the items of one pair; item order inside a tier is kept as given."""
    caps = caps_for(entity_type)
    by_tier: dict[int, list[EvidenceItem]] = {}
    against: list[EvidenceItem] = []
    for item in items:
        if item.spec.opposing:
            against.append(item)
        else:
            assert item.tier is not None  # noqa: S101 - catalogue invariant
            by_tier.setdefault(item.tier, []).append(item)
    support = []
    for tier in sorted(by_tier):
        raw = sum((i.contribution for i in by_tier[tier]), ZERO)
        cap = caps[tier]
        adjustment = min(ZERO, cap - raw)
        support.append(
            TierTotal(tier, cap, raw, adjustment, raw + adjustment, tuple(by_tier[tier]))
        )
    s_raw = sum((t.subtotal for t in support), ZERO) + sum((i.contribution for i in against), ZERO)
    clamped = min(max(s_raw, ZERO), HUNDRED)
    return Breakdown(entity_type, tuple(support), tuple(against), clamped - s_raw, clamped)


def band_of(breakdown: Breakdown, thresholds: Thresholds) -> Band:
    """High >= high_min, Medium >= medium_min, else Low; a veto forces Low."""
    if breakdown.vetoed:
        return Band.LOW
    if breakdown.score >= thresholds.high_min:
        return Band.HIGH
    if breakdown.score >= thresholds.medium_min:
        return Band.MEDIUM
    return Band.LOW
