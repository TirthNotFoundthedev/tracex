"""Tier 1 evidence and the exact opposing checks (spec sections 3 and 4).

    ID_EXACT             identifier pair, identical normalized value
    ACCT_BANK_CONFLICT   same account digits, both IFSCs known and different (veto)
    SHARED_PHONE/_ACCOUNT/_VEHICLE
                         person or org pair: each side tied to an identifier, the two
                         identifiers joined by an AUTO or CONFIRMED SAME_AS (section 4 rule 2)
    PER_DOB_CONFLICT / PER_DOB_MISMATCH / PER_GENDER_CONFLICT
                         exact comparisons of stated facts; they only ever lower a score

Tier 2 and Tier 3 items come from `EvidenceProvider`s (providers.py).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from tracex_engine.graph import Entity, EntityType
from tracex_engine.matching.corpus import Corpus, Tie
from tracex_engine.matching.flags import ValueKey
from tracex_engine.scoring import EvidenceItem, Modifier
from tracex_engine.scoring.ruleset import ATTRIBUTION_FACTOR, MIN_CONFIDENCE, TRAP_FACTOR

SHARED_KIND = {
    EntityType.PHONE: "SHARED_PHONE",
    EntityType.ACCOUNT: "SHARED_ACCOUNT",
    EntityType.VEHICLE: "SHARED_VEHICLE",
}
ONE = Decimal("1.0")

# Is there an AUTO or CONFIRMED SAME_AS between these two identifier entities?
ActiveLink = Callable[[str, str], bool]


@dataclass(frozen=True)
class Context:
    """What evidence builders read: the corpus, the identifier flags and the live links."""

    corpus: Corpus
    flags: dict[ValueKey, frozenset[str]]
    active_link: ActiveLink


def identifier_items(ctx: Context, a: Entity, b: Entity) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    sources = tuple(sorted({*ctx.corpus.sources(a.entity_id), *ctx.corpus.sources(b.entity_id)}))
    if a.normalized == b.normalized:
        items.append(
            EvidenceItem(
                "ID_EXACT",
                ONE,
                {"id_label": a.type.value, "value": a.normalized},
                sources,
            )
        )
    if a.type is EntityType.ACCOUNT and a.ifsc and b.ifsc and a.ifsc != b.ifsc:
        items.append(bank_conflict(ctx.corpus, a, b))
    return items


def bank_conflict(corpus: Corpus, a: Entity, b: Entity) -> EvidenceItem:
    sources = tuple(sorted({*corpus.sources(a.entity_id), *corpus.sources(b.entity_id)}))
    return EvidenceItem(
        "ACCT_BANK_CONFLICT", ONE, {"bank_a": a.ifsc or "", "bank_b": b.ifsc or ""}, sources
    )


def _best_tie(ties: list[Tie]) -> Tie:
    """The strongest statement tying a party to one identifier: highest factor, then
    confidence, then the earliest line."""
    return sorted(ties, key=lambda t: (-ATTRIBUTION_FACTOR[t.code], -t.confidence, t.source))[0]


def shared_identifier_items(ctx: Context, a: Entity, b: Entity) -> list[EvidenceItem]:
    """One SHARED_* item per identifier value both parties are tied to through a live link."""
    corpus = ctx.corpus
    ties_a = corpus.ties_of_party.get(a.entity_id, [])
    ties_b = corpus.ties_of_party.get(b.entity_id, [])
    shared: dict[ValueKey, tuple[list[Tie], list[Tie]]] = {}
    for ta in ties_a:
        ia = corpus.entities[ta.identifier_id]
        for tb in ties_b:
            ib = corpus.entities[tb.identifier_id]
            if ia.type is not ib.type or not ctx.active_link(ia.entity_id, ib.entity_id):
                continue
            side_a, side_b = shared.setdefault((ia.type, ia.normalized), ([], []))
            side_a.append(ta)
            side_b.append(tb)
    items = []
    for key in sorted(shared):
        best_a, best_b = (_best_tie(side) for side in shared[key])
        codes = sorted(ctx.flags.get(key, frozenset()))
        trap = TRAP_FACTOR if codes else ONE
        factor = min(ATTRIBUTION_FACTOR[best_a.code], ATTRIBUTION_FACTOR[best_b.code])
        anchor = (
            best_a.code == best_b.code == "OWNS"
            and not codes
            and min(best_a.confidence, best_b.confidence) >= MIN_CONFIDENCE
        )
        items.append(
            EvidenceItem(
                SHARED_KIND[key[0]],
                factor * trap,
                {
                    "value": key[1],
                    "how_a": best_a.code,
                    "case_a": a.case_id,
                    "how_b": best_b.code,
                    "case_b": b.case_id,
                },
                tuple(sorted({best_a.source, best_b.source})),
                is_anchor=anchor,
                modifiers=tuple(Modifier(c) for c in codes),
            )
        )
    return items


def _dob(corpus: Corpus, entity_id: str) -> date | None:
    for value in sorted(corpus.attribute(entity_id, "dob")):
        try:
            return date.fromisoformat(value)
        except ValueError:
            continue
    return None


def person_conflicts(corpus: Corpus, a: Entity, b: Entity) -> list[EvidenceItem]:
    """Opposing items from facts both records state (DOB, gender)."""
    items: list[EvidenceItem] = []
    dob_a, dob_b = _dob(corpus, a.entity_id), _dob(corpus, b.entity_id)
    if dob_a and dob_b and dob_a != dob_b:
        kind = "PER_DOB_CONFLICT" if abs((dob_a - dob_b).days) > 365 else "PER_DOB_MISMATCH"
        sources = corpus.attribute_sources(a.entity_id, "dob") + corpus.attribute_sources(
            b.entity_id, "dob"
        )
        items.append(
            EvidenceItem(
                kind, ONE, {"dob_a": dob_a.isoformat(), "dob_b": dob_b.isoformat()}, sources
            )
        )
    genders_a = corpus.attribute(a.entity_id, "gender")
    genders_b = corpus.attribute(b.entity_id, "gender")
    if genders_a and genders_b and not genders_a & genders_b:
        sources = corpus.attribute_sources(a.entity_id, "gender") + corpus.attribute_sources(
            b.entity_id, "gender"
        )
        items.append(EvidenceItem("PER_GENDER_CONFLICT", ONE, {}, sources))
    return items


def hard_conflict(corpus: Corpus, a: Entity, b: Entity) -> bool:
    """C3: does any opposing item between these two entities block AUTO?"""
    if a.type is EntityType.PERSON:
        return any(
            i.kind in ("PER_DOB_CONFLICT", "PER_GENDER_CONFLICT")
            for i in person_conflicts(corpus, a, b)
        )
    return bool(a.type is EntityType.ACCOUNT and a.ifsc and b.ifsc and a.ifsc != b.ifsc)
