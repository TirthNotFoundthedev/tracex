"""The worked scenario and a fixture provider standing in for the Tier 2 and Tier 3 comparators.

Comparator outputs are fixtures in the matching spec (section 8): `FixtureProvider` adds the
named Tier 2 and Tier 3 items to named pairs so the run, rerun and decision rules can be tested
end to end before those tiers land. The production run never uses it.
"""

import itertools
import uuid
from collections.abc import Iterable, Sequence
from decimal import Decimal

from tests.engine.matching.support import account, build, clock, owns, person, phone, store_of
from tracex_engine.graph import CaseGraph, Entity, InMemoryCaseGraphStore
from tracex_engine.matching import InMemoryLinkStore, Matcher
from tracex_engine.matching.corpus import Corpus
from tracex_engine.scoring import EvidenceItem, Source
from tracex_engine.scoring.evidence import ParamValue

Who = tuple[str, str]  # (case id, normalized name)


class FixtureProvider:
    """Adds `kind` items of the given strengths to pairs named by (case, normalized name)."""

    name = "fixture comparators"

    def __init__(self, pairs: dict[frozenset[Who], list[tuple[str, str]]]) -> None:
        self.pairs = pairs

    def _who(self, entity: Entity) -> Who:
        return (entity.case_id, entity.normalized)

    def candidates(self, corpus: Corpus) -> Iterable[tuple[str, str]]:
        index = {self._who(e): e.entity_id for e in corpus.entities.values()}
        for pair in self.pairs:
            first, second = sorted(pair)
            if first in index and second in index:
                yield (index[first], index[second])

    def items(self, corpus: Corpus, a: Entity, b: Entity) -> Sequence[EvidenceItem]:
        spec = self.pairs.get(frozenset({self._who(a), self._who(b)}), [])
        sources = (corpus.first_source(a.entity_id), corpus.first_source(b.entity_id))
        return [EvidenceItem(kind, Decimal(s), _params(kind, a, b, s), sources) for kind, s in spec]


def _params(kind: str, a: Entity, b: Entity, strength: str) -> dict[str, ParamValue]:
    """Contract-shaped params for the fixture items (values only, never display text)."""
    shapes: dict[str, dict[str, ParamValue]] = {
        "PER_NAME_SIM": {"name_a": a.normalized, "name_b": b.normalized, "sim": float(strength)},
        "PER_SHARED_NETWORK": {"k": 2, "list": ["9000021203", "9000028816"]},
        "PER_RELATIVE_NAME": {"rel_a": "fixture", "rel_b": "fixture"},
        "PER_LOCALITY": {"place": "fixture"},
        "PER_AGE_CLOSE": {"age_a": 34, "age_b": 35},
    }
    return shapes.get(kind, {})


IRFAN_A: Who = ("C-101", "mohammad irfan")
IRFAN_B: Who = ("C-201", "irfan")
AC01_FIXTURE = {
    frozenset({IRFAN_A, IRFAN_B}): [("PER_NAME_SIM", "0.75"), ("PER_SHARED_NETWORK", "0.6")]
}


def ac01_graphs() -> tuple[CaseGraph, CaseGraph]:
    """AC-01: C-101 FIR line 12 and bank rows 4 and 7; C-201 CDR rows 33 and 41 and note 3."""
    c101 = build(
        "C-101",
        identifiers=[phone("9000021203", 4, "bank.csv"), phone("9000028816", 7, "bank.csv")],
        attributions=[
            owns(person("Mohd. Irfan"), phone("9000014471", raw="90000 14471")),
            owns(person("Mohd. Irfan"), account("5010000019082", ifsc="SYNB0000123")),
        ],
    )
    c201 = build(
        "C-201",
        identifiers=[
            phone("9000021203", 33, "cdr.csv"),
            phone("9000014471", 33, "cdr.csv"),
            phone("9000028816", 41, "cdr.csv"),
        ],
        attributions=[
            owns(person("Irfan bhai", 3, "notes.txt"), phone("9000014471", 3, "notes.txt"))
        ],
    )
    return c101, c201


_IDS = itertools.count(1)


def matcher(
    *graphs: CaseGraph,
    fixture: dict[frozenset[Who], list[tuple[str, str]]] | None = None,
    links: InMemoryLinkStore | None = None,
    store: InMemoryCaseGraphStore | None = None,
) -> Matcher:
    """A matcher with a fake clock and uuid4-shaped link ids from one process-wide counter."""
    providers = (FixtureProvider(fixture),) if fixture else ()
    return Matcher(
        store or store_of(*graphs),
        links or InMemoryLinkStore(),
        providers=providers,
        clock=clock(),
        new_id=lambda: str(uuid.UUID(int=next(_IDS), version=4)),
    )


def src(case: str, file: str, line: int) -> Source:
    return Source(case, file, line)
