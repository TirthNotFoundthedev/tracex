"""Within-case dedupe: which mentions are the same entity (docs/specs/engine-graph.md section 2).

Conservative by construction. A mention joins an existing entity only when a join rule holds,
no stated attribute conflicts with anything already in that entity, and exactly one entity
qualifies; otherwise it starts its own entity. Nothing is ever dropped: the caller keeps every
mention and only groups them.
"""

import re
from dataclasses import dataclass, field

from tracex_engine.extract import IdentifierMention, OrgMention, PersonMention
from tracex_engine.graph.model import EntityType

Extracted = PersonMention | OrgMention | IdentifierMention

# Age may differ by this many years between two writings of one person (FIR vs later note).
AGE_TOLERANCE = 2
# SDR `relative_name` carries no relation word; it is never "the same relation" as another.
UNKNOWN_RELATION = "relative"

_WORD = re.compile(r"\w+")


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

    def absorb(self, other: "_Traits") -> None:
        self.names |= other.names
        self.writings |= other.writings
        self.aliases |= other.aliases
        self.relatives |= other.relatives
        self.ages |= other.ages
        self.genders |= other.genders
        self.dobs |= other.dobs
        self.localities |= other.localities
        self.districts |= other.districts
        self.ifscs |= other.ifscs


@dataclass
class Draft:
    """An entity under construction: its type, 1-based ordinal and mentions in load order."""

    type: EntityType
    ordinal: int
    mentions: list[Extracted] = field(default_factory=list)
    traits: _Traits = field(default_factory=_Traits)


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
        )
    )


def _same_name(type_: EntityType, new: _Traits, entity: _Traits) -> bool:
    """The join rule per type (spec section 2); `new` has at most one name."""
    [name] = new.names
    if type_ is EntityType.PERSON:
        if name in entity.names:
            return len(name.split()) >= 2 or bool(new.writings & entity.writings)
        return name in entity.aliases or bool(new.aliases & entity.names)
    if type_ is EntityType.ORG:
        return name in entity.names and bool(new.writings & entity.writings)
    return name in entity.names


class EntityIndex:
    """Places mentions one by one, in load order, into entities."""

    def __init__(self) -> None:
        self.drafts: list[Draft] = []
        self._placed: dict[Extracted, int] = {}
        self._by_name: dict[tuple[EntityType, str], set[int]] = {}
        self._by_alias: dict[tuple[EntityType, str], set[int]] = {}

    def place(self, mention: Extracted) -> int:
        """Index in `drafts` of the entity this mention belongs to (created when needed)."""
        known = self._placed.get(mention)
        if known is not None:
            self.drafts[known].mentions.append(mention)
            return known
        type_ = entity_type(mention)
        traits = _traits(mention)
        matching = [i for i in sorted(self._candidates(type_, traits)) if self._joins(i, traits)]
        index = matching[0] if len(matching) == 1 else self._create(type_)
        self._absorb(index, mention, traits)
        self._placed[mention] = index
        return index

    def _candidates(self, type_: EntityType, traits: _Traits) -> set[int]:
        if not traits.names:
            return set()
        [name] = traits.names
        found = set(self._by_name.get((type_, name), ())) | set(
            self._by_alias.get((type_, name), ())
        )
        for alias in traits.aliases:
            found |= self._by_name.get((type_, alias), set())
        return found

    def _joins(self, index: int, traits: _Traits) -> bool:
        draft = self.drafts[index]
        return _same_name(draft.type, traits, draft.traits) and not _vetoed(traits, draft.traits)

    def _create(self, type_: EntityType) -> int:
        self.drafts.append(Draft(type_, len(self.drafts) + 1))
        return len(self.drafts) - 1

    def _absorb(self, index: int, mention: Extracted, traits: _Traits) -> None:
        draft = self.drafts[index]
        draft.mentions.append(mention)
        draft.traits.absorb(traits)
        for name in traits.names:
            self._by_name.setdefault((draft.type, name), set()).add(index)
        for alias in traits.aliases:
            self._by_alias.setdefault((draft.type, alias), set()).add(index)
