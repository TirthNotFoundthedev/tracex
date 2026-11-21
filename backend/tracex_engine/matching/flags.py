"""Identifier flags SHARED, HUB and MULTI_USER (spec section 1), computed over all cases.

The spec assigns the flags to the Graph stage; engine-graph.md section 7 leaves them to a
later slice, so the matcher computes them here until Graph owns them. A flag belongs to the
identifier value (type and normalized form): the phone *is* the same phone in every case, so a
family phone flagged in one case counts for less in every case.

    SHARED       within one case, OWNS or REGISTERED_TO to two or more distinct persons; or a
                 mention calls it a shop, PCO, office, family or landline number
    HUB          25 or more distinct counterparties (called / transferred) in one case
    MULTI_USER   OWNS to persons in two or more cases where some cross-case pair of owners
                 has best name similarity below 0.5 and no CONFIRMED SAME_AS between them;
                 names count as similar only when a non-common token is spelled alike
"""

from collections import defaultdict
from decimal import Decimal

from tracex_engine.graph import EntityType
from tracex_engine.matching.corpus import Corpus
from tracex_engine.matching.names import is_placeholder
from tracex_engine.normalize.phonetic import ratio
from tracex_engine.normalize.similarity import (
    MATCH_RATIO,
    name_similarity,
    name_tokens,
    token_is_common,
)

SHARED, HUB, MULTI_USER = "SHARED", "HUB", "MULTI_USER"
HUB_MIN_COUNTERPARTIES = 25
MULTI_USER_MAX_SIM = Decimal("0.5")
SHARING_CODES = frozenset({"OWNS", "REGISTERED_TO"})

ValueKey = tuple[EntityType, str]


def identifier_flags(
    corpus: Corpus, confirmed_person_pairs: frozenset[frozenset[str]] = frozenset()
) -> dict[ValueKey, frozenset[str]]:
    """Flags per identifier value; values without a flag are absent."""
    flags: dict[ValueKey, set[str]] = defaultdict(set)
    owners: dict[ValueKey, list[str]] = defaultdict(list)
    for entity in corpus.entities.values():
        if entity.type not in (EntityType.PHONE, EntityType.ACCOUNT, EntityType.VEHICLE):
            continue
        key = (entity.type, entity.normalized)
        ties = corpus.ties_of_identifier.get(entity.entity_id, [])
        persons = {
            t.party_id
            for t in ties
            if t.code in SHARING_CODES and corpus.entities[t.party_id].type is EntityType.PERSON
        }
        if len(persons) >= 2 or entity.shared_wording:
            flags[key].add(SHARED)
        if len(corpus.counterparties.get(entity.entity_id, ())) >= HUB_MIN_COUNTERPARTIES:
            flags[key].add(HUB)
        owners[key].extend(
            t.party_id
            for t in ties
            if t.code == "OWNS" and corpus.entities[t.party_id].type is EntityType.PERSON
        )
    for value, owner_ids in owners.items():
        if _multi_user(corpus, sorted(set(owner_ids)), confirmed_person_pairs):
            flags[value].add(MULTI_USER)
    return {k: frozenset(v) for k, v in flags.items() if v}


def _multi_user(corpus: Corpus, persons: list[str], confirmed: frozenset[frozenset[str]]) -> bool:
    for i, a in enumerate(persons):
        for b in persons[i + 1 :]:
            if corpus.entities[a].case_id == corpus.entities[b].case_id:
                continue
            if frozenset({a, b}) in confirmed:
                continue
            if best_name_sim(corpus.names(a), corpus.names(b)) < MULTI_USER_MAX_SIM:
                return True
    return False


def best_name_sim(names_a: set[str], names_b: set[str]) -> Decimal:
    """Highest `name_sim` over main names and aliases of both sides, counting only names that
    share a non-common token spelled alike (ratio at least 0.85, errata 6); names that agree
    only on common tokens or only by sound (`kamal` / `kamla`) compare as 0, and a placeholder
    name (`name not known`) compares as 0. A lower value can only flag more."""
    return max(
        (
            name_similarity(a, b).name_sim
            for a in names_a
            for b in names_b
            if not is_placeholder(a) and not is_placeholder(b) and _spelled_alike(a, b)
        ),
        default=Decimal(0),
    )


def _spelled_alike(a: str, b: str) -> bool:
    """Some non-common token of `a` and one of `b` have ratio at least 0.85."""
    left = [t for t in name_tokens(a) if not token_is_common(t)]
    right = [t for t in name_tokens(b) if not token_is_common(t)]
    return any(ratio(x, y) >= MATCH_RATIO for x in left for y in right)
