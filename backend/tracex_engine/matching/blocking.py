"""Candidate generation (spec section 2): a pair is compared only if it shares a block key.

Implemented now: B1 ID_VALUE (identifier pairs) and B3 ANCHOR through B1 (person and org
pairs tied to identifiers of the same value). B2, B4-B7 need Tier 2 or Tier 3 comparators and
arrive with those tiers as `EvidenceProvider.candidates` (providers.py).

Common rules: same type, different cases, at least one end case in the run scope, each
unordered pair once (canonical order by entity id), and a block of more than 500 members is
skipped and counted as `oversized_block`.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from tracex_engine.graph import EntityType, entity_sort_key
from tracex_engine.matching.corpus import Corpus
from tracex_engine.matching.names import is_placeholder

MAX_BLOCK = 500
IDENTIFIER_TYPES = (EntityType.PHONE, EntityType.ACCOUNT, EntityType.VEHICLE)
Pair = tuple[str, str]


@dataclass(frozen=True)
class BlockKeySpec:
    key: str
    types: tuple[str, ...]
    waits_for: int | None


BLOCK_KEYS = (
    BlockKeySpec("B1_ID_VALUE", ("PHONE", "ACCOUNT", "VEHICLE"), None),
    BlockKeySpec("B2_PHONE_DIGITSET", ("PHONE",), 2),
    BlockKeySpec("B3_ANCHOR", ("PERSON", "ORG"), None),
    BlockKeySpec("B4_NAME_KEY", ("PERSON",), 2),
    BlockKeySpec("B5_COMMON_LOC", ("PERSON",), 2),
    BlockKeySpec("B6_NETWORK", ("PERSON",), 3),
    BlockKeySpec("B7_ORG_KEY", ("ORG",), 2),
)


def canonical(a: str, b: str) -> Pair:
    return (a, b) if entity_sort_key(a) <= entity_sort_key(b) else (b, a)


@dataclass
class Candidates:
    pairs: set[Pair]
    oversized_block: int = 0

    def add_block(self, corpus: Corpus, members: Iterable[str], scope: frozenset[str]) -> None:
        block = sorted(set(members), key=entity_sort_key)
        if len(block) < 2:
            return
        if len(block) > MAX_BLOCK:
            self.oversized_block += 1
            return
        for i, a in enumerate(block):
            ea = corpus.entities[a]
            for b in block[i + 1 :]:
                eb = corpus.entities[b]
                if ea.type is not eb.type or ea.case_id == eb.case_id:
                    continue
                if ea.case_id in scope or eb.case_id in scope:
                    self.pairs.add(canonical(a, b))


def identifier_candidates(corpus: Corpus, scope: frozenset[str]) -> Candidates:
    """B1: identifiers with an identical normalized value."""
    found = Candidates(set())
    for (type_, _), members in sorted(corpus.by_value.items()):
        if type_ in IDENTIFIER_TYPES:
            found.add_block(corpus, members, scope)
    return found


def linkable_party(corpus: Corpus, entity_id: str) -> bool:
    """Persons whose name only says it is unknown never take part in person matching."""
    entity = corpus.entities[entity_id]
    if entity.type is EntityType.PERSON:
        return not all(is_placeholder(n) for n in corpus.names(entity_id))
    return entity.type is EntityType.ORG and bool(entity.normalized)


def party_candidates(corpus: Corpus, scope: frozenset[str]) -> Candidates:
    """B3 through B1: persons and orgs tied to identifiers of the same value."""
    parties: dict[tuple[EntityType, str], set[str]] = defaultdict(set)
    for party_id, ties in corpus.ties_of_party.items():
        if not linkable_party(corpus, party_id):
            continue
        for tie in ties:
            identifier = corpus.entities[tie.identifier_id]
            parties[(identifier.type, identifier.normalized)].add(party_id)
    found = Candidates(set())
    for key in sorted(parties):
        found.add_block(corpus, parties[key], scope)
    return found
