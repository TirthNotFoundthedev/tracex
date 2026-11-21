"""Extension point for Tier 2 and Tier 3 evidence: `EvidenceProvider`.

A provider adds candidate pairs (its own block keys, e.g. B2 or B4) and evidence items for any
compared pair. Tier 2 (fuzzy: PHONE_TRANSPOSED, PER_NAME_SIM, ...; `matching/tier2.py`) is one
provider and Tier 3 (contextual: PER_SHARED_NETWORK, PER_CO_LOCATION) will be another. Until
Tier 3 lands, its catalogue items are `NotYetImplemented` seams that yield no candidates and no
items, and `pending_seams()` names what is missing.

Tests inject fixture providers: comparator outputs are fixtures in the spec (section 8).
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

from tracex_engine.graph import Entity
from tracex_engine.matching.corpus import Corpus
from tracex_engine.matching.tier2 import Tier2Provider
from tracex_engine.matching.tier3 import Tier3Provider
from tracex_engine.scoring import EvidenceItem, pending_kinds

Pair = tuple[str, str]


class EvidenceProvider(Protocol):
    @property
    def name(self) -> str: ...

    def candidates(self, corpus: Corpus) -> Iterable[Pair]:
        """Extra pairs to compare (any order; the matcher canonicalises and scopes them)."""
        ...

    def items(self, corpus: Corpus, a: Entity, b: Entity) -> Sequence[EvidenceItem]:
        """Evidence for the pair (`a` before `b` in entity id order)."""
        ...


@dataclass(frozen=True)
class NotYetImplemented:
    """A named seam for one catalogue item of a later tier."""

    kind: str
    tier: int

    @property
    def name(self) -> str:
        return f"{self.kind} (tier {self.tier}, not yet implemented)"

    def candidates(self, corpus: Corpus) -> Iterable[Pair]:
        return ()

    def items(self, corpus: Corpus, a: Entity, b: Entity) -> Sequence[EvidenceItem]:
        return ()


def pending_seams() -> tuple[NotYetImplemented, ...]:
    """One seam per catalogue item that waits for Tier 2 or Tier 3."""
    return tuple(NotYetImplemented(kind, tier) for kind, tier in sorted(pending_kinds().items()))


def default_providers() -> tuple[EvidenceProvider, ...]:
    return (Tier2Provider(), Tier3Provider(), *(s for s in pending_seams() if s.tier > 3))
