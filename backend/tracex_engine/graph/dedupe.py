"""Within-case dedupe: which mentions are the same entity (docs/specs/engine-graph.md section 2).

Conservative and order-independent by construction. The partition is a function of the set of
the case's mentions: writings that say the same about themselves are one node; two nodes are
linked when a join rule holds; a connected set of nodes is one entity only if no two of its
nodes are separated by a stated conflict, otherwise none of them joins (no guessing). The
caller numbers entities afterwards from source order. Nothing is ever dropped: every mention
is kept and only grouped.
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field, fields

from tracex_engine.extract import IdentifierMention, OrgMention, PersonMention
from tracex_engine.graph.model import EntityType

Extracted = PersonMention | OrgMention | IdentifierMention

# Age may differ by this many years between two writings of one person (FIR vs later note).
AGE_TOLERANCE = 2
# SDR `relative_name` carries no relation word; it is never "the same relation" as another.
UNKNOWN_RELATION = "relative"

_WORD = re.compile(r"\w+")

# Roles (extract/patterns.py, English, romanised Hindi, Devanagari) by side of a case. A
# complainant-side and an accused-side writing are never one person; witnesses are neutral.
_COMPLAINANT_SIDE = frozenset(
    unicodedata.normalize("NFC", w)
    for w in ("complainant", "victim", "informant", "informer", "shikayatkarta", "शिकायतकर्ता",
              "मुखबिर", "पीड़ित")
)  # fmt: skip
_ACCUSED_SIDE = frozenset(
    unicodedata.normalize("NFC", w)
    for w in ("accused", "suspect", "arrested", "aaropi", "abhiyukt", "sandigdh", "आरोपी",
              "अभियुक्त", "संदिग्ध")
)  # fmt: skip


@dataclass
class _Traits:
    """What a mention (or a whole entity, as the union of its mentions) says about itself."""

    names: set[str] = field(default_factory=set)
    writings: set[str] = field(default_factory=set)
    aliases: set[str] = field(default_factory=set)
    relatives: set[tuple[str, str]] = field(default_factory=set)
    ages: set[int] = field(default_factory=set)
    genders: set[str] = field(default_factory=set)
    dobs: set[str] = field(default_factory=set)
    localities: set[str] = field(default_factory=set)
    districts: set[str] = field(default_factory=set)
    ifscs: set[str] = field(default_factory=set)
    sides: set[str] = field(default_factory=set)


@dataclass
class Draft:
    """An entity under construction: its type, 1-based ordinal and mentions in load order."""

    type: EntityType
    ordinal: int
    mentions: list[Extracted] = field(default_factory=list)


def entity_type(mention: Extracted) -> EntityType:
    if isinstance(mention, PersonMention):
        return EntityType.PERSON
    if isinstance(mention, OrgMention):
        return EntityType.ORG
    return EntityType(mention.kind.value)


def _writing(text: str, drop_m_s: bool = False) -> str:
    words = _WORD.findall(text.casefold())
    if drop_m_s and words[:2] == ["m", "s"]:
        words = words[2:]
    return " ".join(words)


def _traits(mention: Extracted) -> _Traits:
    traits = _Traits()
    if mention.normalized:
        traits.names.add(mention.normalized)
    if isinstance(mention, PersonMention):
        traits.writings.add(_writing(mention.raw_text))
        traits.aliases = {a.normalized for a in mention.aliases if a.normalized}
        if mention.role is not None:
            role = unicodedata.normalize("NFC", mention.role.casefold())
            if role in _COMPLAINANT_SIDE:
                traits.sides.add("complainant")
            elif role in _ACCUSED_SIDE:
                traits.sides.add("accused")
        if mention.relative is not None and mention.relative.name.normalized:
            traits.relatives.add((mention.relative.relation, mention.relative.name.normalized))
        if mention.age is not None and mention.age.normalized.isdigit():
            traits.ages.add(int(mention.age.normalized))
        for value, bucket in (
            (mention.gender, traits.genders),
            (mention.dob, traits.dobs),
            (mention.locality, traits.localities),
            (mention.district, traits.districts),
        ):
            if value is not None and value.normalized:
                bucket.add(value.normalized)
    elif isinstance(mention, OrgMention):
        traits.writings.add(_writing(mention.raw_text, drop_m_s=True))
        if mention.locality is not None and mention.locality.normalized:
            traits.localities.add(mention.locality.normalized)
    elif mention.ifsc is not None and mention.ifsc.normalized:
        traits.ifscs.add(mention.ifsc.normalized)
    return traits


def _clash[T](a: set[T], b: set[T]) -> bool:
    return any(x != y for x in a for y in b)


def _vetoed(new: _Traits, entity: _Traits) -> bool:
    """True when something both sides state differs, so they cannot be the same entity."""
    if any(
        relation == other_relation and relation != UNKNOWN_RELATION and name != other_name
        for relation, name in new.relatives
        for other_relation, other_name in entity.relatives
    ):
        return True
    if any(abs(a - b) > AGE_TOLERANCE for a in new.ages for b in entity.ages):
        return True
    return any(
        _clash(a, b)
        for a, b in (
            (new.genders, entity.genders),
            (new.dobs, entity.dobs),
            (new.localities, entity.localities),
            (new.districts, entity.districts),
            (new.ifscs, entity.ifscs),
            (new.sides, entity.sides),
        )
    )


def _linked(type_: EntityType, a: _Traits, b: _Traits, contested: set[str]) -> bool:
    """The join rule per type (spec section 2) between two nodes, one name each.

    A link through a bare name or alias that two or more different full names claim is
    refused, so a shared nickname never ties its claimants together.
    """
    [x] = a.names
    [y] = b.names
    if type_ is EntityType.PERSON:
        if x == y:
            if len(x.split()) >= 2:
                return True
            return bool(a.writings & b.writings) and x not in contested
        return (x in b.aliases and x not in contested) or (y in a.aliases and y not in contested)
    if type_ is EntityType.ORG:
        return x == y and bool(a.writings & b.writings)
    return x == y


def _contested(traits: Sequence[_Traits]) -> set[str]:
    """Strings (a bare token or alias) that two or more different names lay claim to."""
    owners: dict[str, set[str]] = {}
    for item in traits:
        if not item.names or not item.writings:
            continue
        [name] = item.names
        if len(name.split()) >= 2:
            for token in name.split():
                owners.setdefault(token, set()).add(name)
        for alias in item.aliases - {name}:
            owners.setdefault(alias, set()).add(name)
    return {text for text, names in owners.items() if len(names) >= 2}


def separated(a: Extracted, b: Extracted) -> bool:
    """True when something both writings state differs, so they can never be one entity."""
    return _vetoed(_traits(a), _traits(b))


def group_mentions(mentions: Sequence[Extracted]) -> list[int]:
    """Entity group of each mention, numbered 0, 1, ... in order of first appearance."""
    all_traits = [_traits(m) for m in mentions]
    contested = _contested(all_traits)
    node_of: dict[object, int] = {}
    nodes: list[tuple[EntityType, _Traits]] = []
    position_node: list[int] = []
    for mention, traits in zip(mentions, all_traits, strict=True):
        type_ = entity_type(mention)
        signature: object = (
            (type_, *(tuple(sorted(getattr(traits, f.name))) for f in fields(traits)))
            if traits.names
            else ("nameless", mention)
        )
        if signature not in node_of:
            node_of[signature] = len(nodes)
            nodes.append((type_, traits))
        position_node.append(node_of[signature])

    parent = list(range(len(nodes)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by_name: dict[tuple[EntityType, str], list[int]] = {}
    by_alias: dict[tuple[EntityType, str], list[int]] = {}
    for index, (type_, traits) in enumerate(nodes):
        for name in traits.names:
            by_name.setdefault((type_, name), []).append(index)
        for alias in traits.aliases:
            by_alias.setdefault((type_, alias), []).append(index)
    for index, (type_, traits) in enumerate(nodes):
        if not traits.names:
            continue
        [name] = traits.names
        found = {*by_name.get((type_, name), ()), *by_alias.get((type_, name), ())}
        for alias in traits.aliases:
            found.update(by_name.get((type_, alias), ()))
        for other in found - {index}:
            if _linked(type_, traits, nodes[other][1], contested):
                parent[find(index)] = find(other)

    members: dict[int, list[int]] = {}
    for index in range(len(nodes)):
        members.setdefault(find(index), []).append(index)
    joined = {
        root: not any(
            _vetoed(nodes[a][1], nodes[b][1]) for i, a in enumerate(group) for b in group[i + 1 :]
        )
        for root, group in members.items()
    }

    numbering: dict[tuple[str, int], int] = {}
    out: list[int] = []
    for node in position_node:
        root = find(node)
        entity = ("joined", root) if joined[root] else ("alone", node)
        out.append(numbering.setdefault(entity, len(numbering)))
    return out
