"""CaseRecords -> CaseGraph. Pure: no database, no I/O, same input gives the same graph."""

from collections import defaultdict
from collections.abc import Iterable

from tracex_engine.extract import (
    CONFIDENCE_CLEAR,
    Attribution,
    CaseRecords,
    IdentifierMention,
    OrgMention,
    PersonMention,
)
from tracex_engine.graph.dedupe import Draft, EntityIndex, Extracted, entity_type
from tracex_engine.graph.model import (
    AttrValue,
    CaseGraph,
    Edge,
    EdgeType,
    Entity,
    EntityType,
    Mention,
    Place,
    Scalar,
)
from tracex_engine.graph.order import file_load_key
from tracex_engine.ingest import BankRow, CdrRow, SourceRef
from tracex_engine.normalize import Value

# (type, source, normalized, ifsc): how a row finds the entity of the mention it produced.
type _MentionKey = tuple[EntityType, SourceRef, str, str | None]


def build_case_graph(records: CaseRecords) -> CaseGraph:
    """Group the case's mentions into entities and draw its edges, each citing its line."""
    case_id = records.case_id
    ordered = _in_load_order(records)
    index = EntityIndex(ordered)
    mention_entity: dict[Extracted, str] = {}
    key_entity: dict[_MentionKey, str] = {}
    mentions: list[Mention] = []
    line_count: dict[tuple[str, int], int] = defaultdict(int)

    for extracted in ordered:
        entity_id = _entity_id(case_id, index.place(extracted))
        mention_entity[extracted] = entity_id
        if isinstance(extracted, IdentifierMention):
            key_entity.setdefault(_key_of(extracted), entity_id)
        where = (extracted.source.file, extracted.source.line)
        line_count[where] += 1
        mentions.append(
            Mention(
                mention_id=f"{case_id}:{where[0]}:{where[1]}:{line_count[where]}",
                entity_id=entity_id,
                case_id=case_id,
                raw_text=extracted.raw_text,
                normalized=extracted.normalized,
                file=where[0],
                line=where[1],
                confidence=extracted.confidence,
                attributes=_attributes(extracted),
            )
        )

    edges = _Edges(case_id, mention_entity, key_entity)
    for attribution in records.attributions:
        edges.attribution(attribution)
    for call in records.cdr_rows:
        edges.call(call)
    for transfer in records.bank_rows:
        edges.transfer(transfer)

    return CaseGraph(
        case_id=case_id,
        entities=tuple(_entity(draft, case_id) for draft in index.drafts),
        mentions=tuple(mentions),
        places=tuple(edges.places.values()),
        edges=tuple(edges.edges),
    )


def _entity_id(case_id: str, position: int) -> str:
    return f"{case_id}:{position + 1:05d}"


def _in_load_order(records: CaseRecords) -> list[Extracted]:
    """Every mention once per extractor entry, plus attribution ends the lists left out.

    Order: file load order, line, then persons, organisations, identifiers, then extractor order.
    """
    listed: set[Extracted] = {*records.persons, *records.orgs, *records.identifiers}
    ranked: list[tuple[int, Extracted]] = [
        *((0, m) for m in records.persons),
        *((1, m) for m in records.orgs),
        *((2, m) for m in records.identifiers),
    ]
    for attribution in records.attributions:
        holder_rank = 1 if isinstance(attribution.holder, OrgMention) else 0
        for rank, end in ((holder_rank, attribution.holder), (2, attribution.identifier)):
            if end not in listed:
                listed.add(end)
                ranked.append((rank, end))
    keyed = [
        ((file_load_key(m.source.file), m.source.line, rank, position), m)
        for position, (rank, m) in enumerate(ranked)
    ]
    return [m for _, m in sorted(keyed, key=lambda item: item[0])]


def _key_of(mention: IdentifierMention) -> _MentionKey:
    ifsc = mention.ifsc.normalized if mention.ifsc is not None and mention.ifsc.normalized else None
    return (entity_type(mention), mention.source, mention.normalized, ifsc)


def _pairs(items: Iterable[tuple[str, AttrValue | None]]) -> tuple[tuple[str, AttrValue], ...]:
    return tuple(sorted((k, v) for k, v in items if v is not None))


def _value_pairs(name: str, value: Value | None) -> list[tuple[str, AttrValue | None]]:
    if value is None:
        return []
    return [(name, value.normalized), (f"{name}_raw", value.raw_text)]


def _attributes(mention: Extracted) -> tuple[tuple[str, AttrValue], ...]:
    items: list[tuple[str, AttrValue | None]] = []
    if isinstance(mention, PersonMention):
        items.append(("role", mention.role))
        for name, value in (
            ("age", mention.age),
            ("dob", mention.dob),
            ("gender", mention.gender),
            ("locality", mention.locality),
            ("district", mention.district),
        ):
            items += _value_pairs(name, value)
        if mention.relative is not None:
            items.append(("relative_relation", mention.relative.relation))
            items += _value_pairs("relative_name", mention.relative.name)
        if mention.aliases:
            items.append(("aliases", tuple(a.normalized for a in mention.aliases)))
            items.append(("aliases_raw", tuple(a.raw_text for a in mention.aliases)))
    elif isinstance(mention, OrgMention):
        items += _value_pairs("locality", mention.locality)
    else:
        items += _value_pairs("ifsc", mention.ifsc)
        items.append(("shared_wording", True if mention.shared_wording else None))
    return _pairs(items)


def _entity(draft: Draft, case_id: str) -> Entity:
    first = draft.mentions[0]
    aliases: list[str] = []
    ifsc: str | None = None
    for mention in draft.mentions:
        if isinstance(mention, PersonMention):
            aliases += [a.normalized for a in mention.aliases if a.normalized not in aliases]
        elif isinstance(mention, IdentifierMention) and ifsc is None and mention.ifsc is not None:
            ifsc = mention.ifsc.normalized or None
    return Entity(
        entity_id=_entity_id(case_id, draft.ordinal - 1),
        case_id=case_id,
        type=draft.type,
        ordinal=draft.ordinal,
        normalized=first.normalized,
        display_value=first.raw_text,
        confidence=max(m.confidence for m in draft.mentions),
        file=first.source.file,
        line=first.source.line,
        aliases=tuple(dict.fromkeys(aliases)),
        ifsc=ifsc,
        shared_wording=any(
            isinstance(m, IdentifierMention) and m.shared_wording for m in draft.mentions
        ),
    )


class _Edges:
    """Draws the edges of one case; each edge id counts per (type, file, line)."""

    def __init__(
        self,
        case_id: str,
        mention_entity: dict[Extracted, str],
        key_entity: dict[_MentionKey, str],
    ) -> None:
        self._case_id = case_id
        self._mention_entity = mention_entity
        self._key_entity = key_entity
        self._count: dict[tuple[EdgeType, str, int], int] = defaultdict(int)
        self.edges: list[Edge] = []
        self.places: dict[str, Place] = {}

    def attribution(self, attribution: Attribution) -> None:
        self._add(
            EdgeType(attribution.code.value),
            self._mention_entity[attribution.holder],
            self._mention_entity[attribution.identifier],
            attribution.source,
            min(attribution.holder.confidence, attribution.identifier.confidence),
            attribution.raw_text,
            hedged=attribution.hedged,
        )

    def call(self, row: CdrRow) -> None:
        calling = self._phone(row.source, row.calling.normalized)
        called = self._phone(row.source, row.called.normalized)
        properties: dict[str, Scalar] = {
            "call_id": row.call_id,
            "start_time": row.start_time.isoformat(),
            "duration_sec": row.duration_sec,
            "call_type": row.call_type,
            "cell_id": row.cell_id,
        }
        self._add(
            EdgeType.CALLED,
            calling,
            called,
            row.source,
            CONFIDENCE_CLEAR,
            row.raw_line,
            properties=properties,
        )
        place = row.tower_place
        if place is not None and place.normalized:
            place_id = f"{self._case_id}:place:{place.normalized}"
            self.places.setdefault(
                place_id, Place(place_id, self._case_id, place.normalized, place.raw_text)
            )
            seen: dict[str, Scalar] = {
                "on": row.start_time.date().isoformat(),
                "at": row.start_time.isoformat(),
                "call_id": row.call_id,
                "cell_id": row.cell_id,
            }
            self._add(
                EdgeType.SEEN_AT,
                calling,
                place_id,
                row.source,
                CONFIDENCE_CLEAR,
                row.raw_line,
                properties=seen,
            )

    def transfer(self, row: BankRow) -> None:
        if row.counterparty is None or row.counterparty_kind not in ("PHONE", "ACCOUNT"):
            return
        own = self._lookup(
            EntityType.ACCOUNT,
            row.source,
            row.account.normalized,
            row.ifsc.normalized if row.ifsc is not None and row.ifsc.normalized else None,
        )
        other_type = EntityType.PHONE if row.counterparty_kind == "PHONE" else EntityType.ACCOUNT
        other = self._lookup(other_type, row.source, row.counterparty.normalized, None)
        source, target = (own, other) if row.direction == "DR" else (other, own)
        properties: dict[str, Scalar] = {
            "txn_id": row.txn_id,
            "txn_date": row.txn_date.isoformat(),
            "amount_inr": str(row.amount_inr),
            "direction": row.direction,
        }
        self._add(
            EdgeType.TRANSFERRED_TO,
            source,
            target,
            row.source,
            CONFIDENCE_CLEAR,
            row.raw_line,
            properties=properties,
        )

    def _phone(self, source: SourceRef, normalized: str) -> str:
        return self._lookup(EntityType.PHONE, source, normalized, None)

    def _lookup(
        self, type_: EntityType, source: SourceRef, normalized: str, ifsc: str | None
    ) -> str:
        try:
            return self._key_entity[(type_, source, normalized, ifsc)]
        except KeyError:
            raise ValueError(
                f"{source.file}:{source.line}: no {type_} mention {normalized!r} in the records"
            ) from None

    def _add(
        self,
        type_: EdgeType,
        source_id: str,
        target_id: str,
        source: SourceRef,
        confidence: float,
        raw_text: str,
        hedged: bool | None = None,
        properties: dict[str, Scalar] | None = None,
    ) -> None:
        key = (type_, source.file, source.line)
        self._count[key] += 1
        self.edges.append(
            Edge(
                edge_id=f"{self._case_id}|{type_}|{source.file}|{source.line}|{self._count[key]}",
                case_id=self._case_id,
                type=type_,
                source_id=source_id,
                target_id=target_id,
                file=source.file,
                line=source.line,
                confidence=confidence,
                raw_text=raw_text,
                hedged=hedged,
                properties=tuple(sorted((properties or {}).items())),
            )
        )
