"""Tier 2 evidence: fuzzy and probabilistic comparison, as one `EvidenceProvider` (spec 2, 3).

Blocking keys (candidate pairs, spec section 2):
    B2 PHONE_DIGITSET   phones: first two digits + the digits sorted (finds adjacent swaps)
    B4 NAME_KEY         persons: phonetic key of each non-common name token, main name or alias
    B5 COMMON_LOC       persons whose name has only common tokens: (whole-name key, stated district)
    B7 ORG_KEY          organisations: phonetic key of the reduced name

Evidence items:
    PHONE_TRANSPOSED                phones equal except one adjacent pair of digits swapped
    PER_NAME_SIM, PER_RELATIVE_NAME, PER_DOB_MATCH, PER_AGE_CLOSE, PER_LOCALITY, PER_NEAR_PHONE
    ORG_NAME_SIM, and PER_LOCALITY for organisations
    PER_AGE_CONFLICT, PER_RELATIVE_CONFLICT (opposing)

Hard PER_AGE_CONFLICT is seen by the cluster check C3 (`matching/evidence.hard_conflict`).

Gaps the data allows no answer to yet (they only ever make a link be missed, never made):
- Ages are compared as stated. The case graph carries no case dates, so "ages at a common date"
  is read as "ages as written"; cases are normally written close together.
- A person's district is the stated one. The district of the case is not in the graph, so a
  person with no stated district has no district (B5 skips them; PER_LOCALITY sees none).
- `oversized_block` for B2, B4, B5 and B7 is not counted in the run record: a provider returns
  pairs only. Blocks over the size limit are skipped as for the other keys.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal
from math import ceil

from tracex_engine.graph import Entity, EntityType
from tracex_engine.matching.blocking import Candidates, Pair
from tracex_engine.matching.corpus import Corpus, source_of
from tracex_engine.matching.evidence import Context
from tracex_engine.matching.names import is_placeholder
from tracex_engine.normalize.facts import (
    CLOSE_AGE_YEARS,
    CONFLICT_AGE_YEARS,
    HARD_CONFLICT_AGE_YEARS,
    closest_ages,
    parse_age,
    parse_iso_date,
    phone_digitset_key,
    phones_transposed,
    same_place,
)
from tracex_engine.normalize.phonetic import phonetic_key
from tracex_engine.normalize.similarity import (
    NameSimilarity,
    name_key,
    name_similarity,
    name_tokens,
    org_name_key,
    org_name_similarity,
    token_is_common,
)
from tracex_engine.scoring import EvidenceItem, Severity, Source
from tracex_engine.scoring.evidence import ParamValue
from tracex_engine.scoring.ruleset import ATTRIBUTION_FACTOR, MIN_CONFIDENCE

ONE = Decimal("1.0")
NAME_SIM_MIN = Decimal("0.80")
RELATIVE_SIM_MIN = Decimal("0.85")
RELATIVE_CONFLICT_BELOW = Decimal("0.60")
ORG_SIM_MIN = Decimal("0.85")
DISTRICT_ONLY = Decimal("0.4")
AGE_TWO_YEARS = Decimal("0.5")
AGE_HARD_WEIGHT = Decimal(40)
# A name token is corpus-frequent when at least this many person entities, and at least
# FREQUENT_SHARE of all of them, have a name with the same sound (spec section 2).
FREQUENT_MIN_ENTITIES = 20
FREQUENT_SHARE = Decimal("0.01")
UNKNOWN_RELATION = "relative"


def frequent_keys(corpus: Corpus) -> frozenset[str]:
    """Phonetic keys that sound like a name in at least 1% of person entities (and 20 of them)."""
    persons = [p for p in corpus.of_type(EntityType.PERSON) if _linkable(corpus, p.entity_id)]
    counts: dict[str, int] = defaultdict(int)
    for person in persons:
        keys = {phonetic_key(t) for n in _names(corpus, person.entity_id) for t in name_tokens(n)}
        for key in keys:
            if len(key) >= 2:
                counts[key] += 1
    needed = max(FREQUENT_MIN_ENTITIES, ceil(Decimal(len(persons)) * FREQUENT_SHARE))
    return frozenset(k for k, n in counts.items() if n >= needed)


def _names(corpus: Corpus, entity_id: str) -> list[str]:
    return sorted(n for n in corpus.names(entity_id) if not is_placeholder(n))


def _linkable(corpus: Corpus, entity_id: str) -> bool:
    return bool(_names(corpus, entity_id))


def _name_source(corpus: Corpus, entity_id: str, name: str) -> Source:
    """The first line (in load order) that writes `name` as a main name or an alias."""
    for mention in corpus.mentions[entity_id]:
        aliases = dict(mention.attributes).get("aliases", ())
        if mention.normalized == name or (isinstance(aliases, tuple) and name in aliases):
            return source_of(mention.case_id, mention.file, mention.line)
    return corpus.first_source(entity_id)


def _fact_source(corpus: Corpus, entity_id: str, key: str) -> Source:
    """The first line (in load order) that states the fact `key` for the entity."""
    for mention in corpus.mentions[entity_id]:
        if any(k == key for k, _ in mention.attributes):
            return source_of(mention.case_id, mention.file, mention.line)
    return corpus.first_source(entity_id)


def _cited(*sources: Source) -> tuple[Source, ...]:
    return tuple(sorted(set(sources)))


class Tier2Provider:
    """Fuzzy and probabilistic evidence. Stateless between runs except a per-corpus cache."""

    def __init__(self) -> None:
        self._frequent: tuple[Corpus, frozenset[str]] | None = None

    @property
    def name(self) -> str:
        return "tier 2 fuzzy evidence"

    def _frequent_keys(self, corpus: Corpus) -> frozenset[str]:
        if self._frequent is None or self._frequent[0] is not corpus:
            self._frequent = (corpus, frequent_keys(corpus))
        return self._frequent[1]

    # --- blocking -----------------------------------------------------------------------

    def candidates(self, corpus: Corpus) -> Iterable[Pair]:
        frequent = self._frequent_keys(corpus)
        blocks: dict[tuple[str, ...], set[str]] = defaultdict(set)
        for entity in corpus.entities.values():
            if entity.type is EntityType.PHONE:
                blocks[("B2", phone_digitset_key(entity.normalized))].add(entity.entity_id)
            elif entity.type is EntityType.PERSON:
                self._person_blocks(corpus, entity, frequent, blocks)
            elif entity.type is EntityType.ORG:
                for name in _names(corpus, entity.entity_id):
                    if key := org_name_key(name):
                        blocks[("B7", key)].add(entity.entity_id)
        found = Candidates(set())
        scope = frozenset(corpus.case_ids)
        for block_key in sorted(blocks):
            found.add_block(corpus, blocks[block_key], scope)
        return sorted(found.pairs)

    def _person_blocks(
        self,
        corpus: Corpus,
        person: Entity,
        frequent: frozenset[str],
        blocks: dict[tuple[str, ...], set[str]],
    ) -> None:
        districts = corpus.attribute(person.entity_id, "district")
        for name in _names(corpus, person.entity_id):
            tokens = name_tokens(name)
            rare = [t for t in tokens if not token_is_common(t, frequent)]
            for token in rare:
                if len(key := phonetic_key(token)) >= 2:
                    blocks[("B4", key)].add(person.entity_id)
            if not rare:
                for district in districts:
                    blocks[("B5", name_key(name), district)].add(person.entity_id)

    # --- evidence -----------------------------------------------------------------------

    def items(self, ctx: Context, a: Entity, b: Entity) -> Sequence[EvidenceItem]:
        corpus = ctx.corpus
        if a.type is EntityType.PHONE:
            return self._phone_items(corpus, a, b)
        if a.type is EntityType.PERSON:
            if _linkable(corpus, a.entity_id) and _linkable(corpus, b.entity_id):
                return self._person_items(ctx, a, b)
        elif a.type is EntityType.ORG:
            return self._org_items(corpus, a, b)
        return ()

    def _phone_items(self, corpus: Corpus, a: Entity, b: Entity) -> list[EvidenceItem]:
        if not phones_transposed(a.normalized, b.normalized):
            return []
        sources = _cited(*corpus.sources(a.entity_id), *corpus.sources(b.entity_id))
        params = {"value_a": a.normalized, "value_b": b.normalized}
        return [EvidenceItem("PHONE_TRANSPOSED", ONE, params, sources)]

    def _person_items(self, ctx: Context, a: Entity, b: Entity) -> list[EvidenceItem]:
        corpus = ctx.corpus
        frequent = self._frequent_keys(corpus)
        items: list[EvidenceItem] = []
        items += _name_item(corpus, a, b, frequent)
        relative, relative_conflict = _relative_items(corpus, a, b, frequent)
        items += relative
        items += _dob_item(corpus, a, b)
        close, age_conflict = _age_items(corpus, a, b)
        items += close
        items += _locality_item(corpus, a, b, with_district=True)
        items += _near_phone_item(ctx, a, b)
        return items + age_conflict + relative_conflict

    def _org_items(self, corpus: Corpus, a: Entity, b: Entity) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []
        best: tuple[NameSimilarity, str, str] | None = None
        for na in _names(corpus, a.entity_id):
            for nb in _names(corpus, b.entity_id):
                found = org_name_similarity(na, nb)
                if found and (best is None or found.name_sim > best[0].name_sim):
                    best = (found, na, nb)
        if best and best[0].name_sim >= ORG_SIM_MIN:
            found, na, nb = best
            sources = _cited(
                _name_source(corpus, a.entity_id, na), _name_source(corpus, b.entity_id, nb)
            )
            params: dict[str, ParamValue] = {"name_a": na, "name_b": nb}
            items.append(EvidenceItem("ORG_NAME_SIM", found.name_sim, params, sources))
        return items + _locality_item(corpus, a, b, with_district=False)


def _near_phone_item(ctx: Context, a: Entity, b: Entity) -> list[EvidenceItem]:
    """PER_NEAR_PHONE: each side is tied to a phone and the two phones, one adjacent swap
    apart, have a CONFIRMED SAME_AS (a CONFIRMED PHONE_TRANSPOSED link); strength is the
    weaker attribution factor."""
    corpus = ctx.corpus
    best = None
    for ta in corpus.ties_of_party.get(a.entity_id, []):
        for tb in corpus.ties_of_party.get(b.entity_id, []):
            pa, pb = corpus.entities[ta.identifier_id], corpus.entities[tb.identifier_id]
            if pa.type is not EntityType.PHONE or pb.type is not EntityType.PHONE:
                continue
            if not phones_transposed(pa.normalized, pb.normalized):
                continue
            if not ctx.confirmed_link(pa.entity_id, pb.entity_id):
                continue
            if min(ta.confidence, tb.confidence) < MIN_CONFIDENCE:
                continue
            strength = min(ATTRIBUTION_FACTOR[ta.code], ATTRIBUTION_FACTOR[tb.code])
            rank = (-strength, pa.normalized, pb.normalized)
            if best is None or rank < best[0]:
                best = (rank, strength, ta.source, tb.source)
    if best is None:
        return []
    _, strength, source_a, source_b = best
    return [EvidenceItem("PER_NEAR_PHONE", strength, {}, _cited(source_a, source_b))]


def _name_item(
    corpus: Corpus, a: Entity, b: Entity, frequent: frozenset[str]
) -> list[EvidenceItem]:
    best: tuple[tuple[Decimal, Decimal, str, str], NameSimilarity] | None = None
    for na in _names(corpus, a.entity_id):
        for nb in _names(corpus, b.entity_id):
            found = name_similarity(na, nb, frequent)
            rank = (found.name_sim, found.completeness * found.rarity, na, nb)
            if best is None or rank[:2] > best[0][:2]:
                best = (rank, found)
    if best is None or best[1].name_sim < NAME_SIM_MIN:
        return []
    (_, _, na, nb), found = best
    sources = _cited(_name_source(corpus, a.entity_id, na), _name_source(corpus, b.entity_id, nb))
    params: dict[str, ParamValue] = {"name_a": na, "name_b": nb, "sim": float(found.name_sim)}
    return [EvidenceItem("PER_NAME_SIM", found.strength, params, sources)]


def _relatives(corpus: Corpus, entity_id: str) -> list[tuple[str, str, Source]]:
    """(relation, relative name, line) from every mention that states a known relation."""
    found = []
    for mention in corpus.mentions[entity_id]:
        attributes = dict(mention.attributes)
        relation, name = attributes.get("relative_relation"), attributes.get("relative_name")
        if (
            isinstance(relation, str)
            and isinstance(name, str)
            and name
            and relation != UNKNOWN_RELATION
        ):
            found.append((relation, name, source_of(mention.case_id, mention.file, mention.line)))
    return found


def _relative_items(
    corpus: Corpus, a: Entity, b: Entity, frequent: frozenset[str]
) -> tuple[list[EvidenceItem], list[EvidenceItem]]:
    """PER_RELATIVE_NAME (same relation, names match) or PER_RELATIVE_CONFLICT (same relation
    on both sides and no pair of names reaches 0.6)."""
    best: tuple[Decimal, str, str, Source, Source] | None = None
    for relation_a, name_a, source_a in _relatives(corpus, a.entity_id):
        for relation_b, name_b, source_b in _relatives(corpus, b.entity_id):
            if relation_a != relation_b:
                continue
            sim = name_similarity(name_a, name_b, frequent).name_sim
            if best is None or (sim, name_a, name_b) > (best[0], best[1], best[2]):
                best = (sim, name_a, name_b, source_a, source_b)
    if best is None:
        return [], []
    sim, name_a, name_b, source_a, source_b = best
    params = {"rel_a": name_a, "rel_b": name_b}
    sources = _cited(source_a, source_b)
    if sim >= RELATIVE_SIM_MIN:
        return [EvidenceItem("PER_RELATIVE_NAME", sim, params, sources)], []
    if sim < RELATIVE_CONFLICT_BELOW:
        return [], [EvidenceItem("PER_RELATIVE_CONFLICT", ONE, params, sources)]
    return [], []


def _dob_item(corpus: Corpus, a: Entity, b: Entity) -> list[EvidenceItem]:
    dobs_a, dobs_b = _dobs(corpus, a), _dobs(corpus, b)
    common = sorted(dobs_a & dobs_b)
    if not common:
        return []
    sources = _cited(
        _fact_source(corpus, a.entity_id, "dob"), _fact_source(corpus, b.entity_id, "dob")
    )
    return [EvidenceItem("PER_DOB_MATCH", ONE, {"dob": common[0].isoformat()}, sources)]


def _dobs(corpus: Corpus, person: Entity) -> set[date]:
    return {d for v in corpus.attribute(person.entity_id, "dob") if (d := parse_iso_date(v))}


def _ages(corpus: Corpus, person: Entity) -> set[int]:
    return {n for v in corpus.attribute(person.entity_id, "age") if (n := parse_age(v)) is not None}


def _age_items(
    corpus: Corpus, a: Entity, b: Entity
) -> tuple[list[EvidenceItem], list[EvidenceItem]]:
    """PER_AGE_CLOSE (no full DOB on one side, ages differ by 2 or less) and PER_AGE_CONFLICT
    (ages differ by more than 5; more than 10 is hard with weight 40)."""
    closest = closest_ages(_ages(corpus, a), _ages(corpus, b))
    if closest is None:
        return [], []
    age_a, age_b = closest
    gap = abs(age_a - age_b)
    sources = _cited(
        _fact_source(corpus, a.entity_id, "age"), _fact_source(corpus, b.entity_id, "age")
    )
    params = {"age_a": age_a, "age_b": age_b}
    both_dob = bool(_dobs(corpus, a)) and bool(_dobs(corpus, b))
    if gap <= CLOSE_AGE_YEARS and not both_dob:
        strength = ONE if gap <= 1 else AGE_TWO_YEARS
        return [EvidenceItem("PER_AGE_CLOSE", strength, params, sources)], []
    if gap > HARD_CONFLICT_AGE_YEARS:
        hard = EvidenceItem(
            "PER_AGE_CONFLICT",
            ONE,
            params,
            sources,
            weight_override=AGE_HARD_WEIGHT,
            severity_override=Severity.HARD,
        )
        return [], [hard]
    if gap > CONFLICT_AGE_YEARS:
        return [], [EvidenceItem("PER_AGE_CONFLICT", ONE, params, sources)]
    return [], []


def _locality_item(corpus: Corpus, a: Entity, b: Entity, with_district: bool) -> list[EvidenceItem]:
    """PER_LOCALITY: the same locality (1.0), else the same stated district only (0.4)."""
    for key, strength in (("locality", ONE), ("district", DISTRICT_ONLY)):
        if key == "district" and not with_district:
            break
        for place_a in sorted(corpus.attribute(a.entity_id, key)):
            for place_b in sorted(corpus.attribute(b.entity_id, key)):
                if same_place(place_a, place_b):
                    sources = _cited(
                        _fact_source(corpus, a.entity_id, key),
                        _fact_source(corpus, b.entity_id, key),
                    )
                    return [EvidenceItem("PER_LOCALITY", strength, {"place": place_a}, sources)]
    return []
