"""The evidence model: one item per check that fired, with its sources (spec sections 3 and 7)."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from tracex_engine.scoring.ruleset import CATALOGUE, EvidenceSpec, Severity

ParamValue = str | int | float

ONE_DECIMAL = Decimal("0.1")


def round_half_up(value: Decimal) -> Decimal:
    """The only rounding in the ruleset: each contribution to one decimal, half up."""
    return value.quantize(ONE_DECIMAL, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, order=True)
class Source:
    """A cited line. `document_id` is the file name inside the case (`notes.txt`)."""

    case_id: str
    document_id: str
    line: int


@dataclass(frozen=True)
class Modifier:
    """Trap-identifier modifier: the identifier is SHARED, HUB or MULTI_USER (factor 0.2)."""

    code: str


@dataclass(frozen=True)
class EvidenceItem:
    """One evidence item. `params` hold only values and codes, never display text.

    `weight_override` exists for the one item whose weight depends on its trigger
    (PER_AGE_CONFLICT is 40 and hard when the ages differ by more than 10 years).
    """

    kind: str
    strength: Decimal
    params: Mapping[str, ParamValue]
    sources: tuple[Source, ...]
    is_anchor: bool = False
    modifiers: tuple[Modifier, ...] = ()
    weight_override: Decimal | None = None
    severity_override: Severity | None = field(default=None)

    @property
    def spec(self) -> EvidenceSpec:
        return CATALOGUE[self.kind]

    @property
    def tier(self) -> int | None:
        return self.spec.tier

    @property
    def weight(self) -> Decimal:
        return self.weight_override if self.weight_override is not None else self.spec.weight

    @property
    def severity(self) -> Severity | None:
        return self.severity_override or self.spec.severity

    @property
    def contribution(self) -> Decimal:
        value = round_half_up(self.weight * self.strength)
        return -value if self.spec.opposing else value
