"""Tier 3 contextual evidence as one `EvidenceProvider` (spec sections 2, 3.2 and 5).

    B6 NETWORK          PERSON pairs whose 2-hop identifier neighbourhoods share at least two
                        identifiers that are not HUB or SHARED
    PER_SHARED_NETWORK  k >= 2 such identifiers on both sides, not counting an identifier the
                        two persons are both tied to (it is already a Tier 1 item): strength
                        0.6 / 0.8 / 1.0 for k = 2 / 3 / 4 or more
    PER_CO_LOCATION     k >= 2 distinct (place, date +-1 day) pairs on both sides from the CDR
                        rows of phones each person owns that are not SHARED, HUB or MULTI_USER:
                        strength 0.7 / 1.0 for k = 2 / 3 or more

Items cite only lines of the two end cases and name no other case. The Tier 1 exclusion is the
identifier values of this pair's SHARED_* items (both ends of every live-linked tie pair), and
co-location reads the run's flags, where MULTI_USER already knows the CONFIRMED person pairs.
B6 blocking runs before any link is settled and reads HUB and SHARED only, which do not depend
on links.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from decimal import Decimal

from tracex_engine.graph import (
    Entity,
    EntityType,
    NetworkIndex,
    SeenAt,
    entity_sort_key,
    match_seen_at,
)
from tracex_engine.graph.neighbourhood import sorted_lines
from tracex_engine.ingest import SourceRef
from tracex_engine.matching.blocking import MAX_BLOCK, Pair, canonical, linkable_party
from tracex_engine.matching.corpus import Corpus
from tracex_engine.matching.evidence import Context, tier1_used_values
from tracex_engine.matching.flags import HUB, MULTI_USER, SHARED, ValueKey, identifier_flags
from tracex_engine.scoring import EvidenceItem, Source

MIN_K = 2
NETWORK_EXCLUDED = frozenset({HUB, SHARED})
CO_LOCATION_EXCLUDED = frozenset({HUB, SHARED, MULTI_USER})
NETWORK_STRENGTH = {2: Decimal("0.6"), 3: Decimal("0.8")}
NETWORK_STRENGTH_MAX = Decimal("1.0")
CO_LOCATION_STRENGTH = {2: Decimal("0.7")}
CO_LOCATION_STRENGTH_MAX = Decimal("1.0")

Network = dict[ValueKey, tuple[SourceRef, ...]]


def _sources(refs: Iterable[SourceRef]) -> tuple[Source, ...]:
    return tuple(sorted({Source(r.case_id, r.file, r.line) for r in refs}))


def network_strength(k: int) -> Decimal:
    return NETWORK_STRENGTH.get(k, NETWORK_STRENGTH_MAX)


def co_location_strength(k: int) -> Decimal:
    return CO_LOCATION_STRENGTH.get(k, CO_LOCATION_STRENGTH_MAX)


class _Prepared:
    """What one run's corpus yields for Tier 3: hop index, flags and per-person caches."""

    def __init__(self, corpus: Corpus) -> None:
        self.corpus = corpus
        self.index = NetworkIndex(corpus.graphs)
        self.flags = identifier_flags(corpus)
        self._networks: dict[str, Network] = {}

    def _flagged(self, key: ValueKey, excluded: frozenset[str]) -> bool:
        return bool(self.flags.get(key, frozenset()) & excluded)

    def network(self, person_id: str) -> Network:
        """Identifier values within 2 hops (HUB and SHARED left out) with their path lines."""
        cached = self._networks.get(person_id)
        if cached is None:
            found: dict[ValueKey, set[SourceRef]] = defaultdict(set)
            for identifier_id, lines in self.index.neighbourhood(person_id).items():
                entity = self.corpus.entities[identifier_id]
                key = (entity.type, entity.normalized)
                if not self._flagged(key, NETWORK_EXCLUDED):
                    found[key].update(lines)
            cached = {k: sorted_lines(v) for k, v in sorted(found.items())}
            self._networks[person_id] = cached
        return cached

    def network_item(self, ctx: Context, a: Entity, b: Entity) -> EvidenceItem | None:
        net_a, net_b = self.network(a.entity_id), self.network(b.entity_id)
        used = tier1_used_values(ctx, a, b)
        common = sorted((net_a.keys() & net_b.keys()) - used)
        if len(common) < MIN_K:
            return None
        lines = [r for key in common for r in (*net_a[key], *net_b[key])]
        return EvidenceItem(
            "PER_SHARED_NETWORK",
            network_strength(len(common)),
            {"k": len(common), "list": [value for _, value in common]},
            _sources(lines),
        )

    def co_location_item(self, ctx: Context, a: Entity, b: Entity) -> EvidenceItem | None:
        flags = ctx.flags
        matched = match_seen_at(self._seen(a.entity_id, flags), self._seen(b.entity_id, flags))
        if len(matched) < MIN_K:
            return None
        lines = [r.source for pair in matched for r in pair]
        return EvidenceItem(
            "PER_CO_LOCATION",
            co_location_strength(len(matched)),
            {"k": len(matched)},
            _sources(lines),
        )

    def _seen(self, person_id: str, flags: dict[ValueKey, frozenset[str]]) -> tuple[SeenAt, ...]:
        records: list[SeenAt] = []
        for phone_id in self.index.owned(person_id, EntityType.PHONE):
            phone = self.corpus.entities[phone_id]
            if not flags.get((phone.type, phone.normalized), frozenset()) & CO_LOCATION_EXCLUDED:
                records.extend(self.index.seen_at(phone_id))
        return tuple(records)


class Tier3Provider:
    """B6 candidates, PER_SHARED_NETWORK and PER_CO_LOCATION for PERSON pairs."""

    name = "tier 3 contextual evidence"

    def __init__(self) -> None:
        self._prepared: _Prepared | None = None

    def _for(self, corpus: Corpus) -> _Prepared:
        if self._prepared is None or self._prepared.corpus is not corpus:
            self._prepared = _Prepared(corpus)
        return self._prepared

    def candidates(self, corpus: Corpus) -> Iterable[Pair]:
        prepared = self._for(corpus)
        holders: dict[ValueKey, list[str]] = defaultdict(list)
        for person in corpus.of_type(EntityType.PERSON):
            if not linkable_party(corpus, person.entity_id):
                continue
            for key in prepared.network(person.entity_id):
                holders[key].append(person.entity_id)
        shared: dict[Pair, int] = defaultdict(int)
        for key in sorted(holders):
            block = sorted(holders[key], key=entity_sort_key)
            if len(block) > MAX_BLOCK:
                continue
            for i, first in enumerate(block):
                for second in block[i + 1 :]:
                    if corpus.entities[first].case_id != corpus.entities[second].case_id:
                        shared[canonical(first, second)] += 1
        return sorted(pair for pair, count in shared.items() if count >= MIN_K)

    def items(self, ctx: Context, a: Entity, b: Entity) -> Sequence[EvidenceItem]:
        if a.type is not EntityType.PERSON or b.type is not EntityType.PERSON:
            return ()
        prepared = self._for(ctx.corpus)
        found = (prepared.network_item(ctx, a, b), prepared.co_location_item(ctx, a, b))
        return [item for item in found if item is not None]
