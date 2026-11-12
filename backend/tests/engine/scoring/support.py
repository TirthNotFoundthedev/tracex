"""Hand-built evidence items for scoring tests: comparator outputs are fixtures (spec section 8)."""

from decimal import Decimal

from tracex_engine.scoring import EvidenceItem, Modifier, Source
from tracex_engine.scoring.evidence import ParamValue

A = Source("C-901", "fir.txt", 12)
B = Source("C-902", "notes.txt", 3)


def item(
    kind: str,
    strength: str = "1.0",
    *,
    anchor: bool = False,
    trap: str | None = None,
    params: dict[str, ParamValue] | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        kind=kind,
        strength=Decimal(strength),
        params=params or {},
        sources=(A, B),
        is_anchor=anchor,
        modifiers=(Modifier(trap),) if trap else (),
    )


def shared_phone(strength: str = "1.0", *, anchor: bool = True) -> EvidenceItem:
    return item(
        "SHARED_PHONE",
        strength,
        anchor=anchor,
        params={
            "value": "9000014471",
            "how_a": "OWNS",
            "case_a": "C-901",
            "how_b": "OWNS",
            "case_b": "C-902",
        },
    )
