"""Entity extraction from one line of FIR narrative or officer note.

The line is split into sentences. Within a sentence, people and organisations are found from
the cue shapes in `patterns` and identifiers by their own formats. OWNS is then emitted only
from a small closed set of clean patterns (the contract; see `extract/__init__.py`):

    A  apposition  <person phrase> [, cue [is] <identifier>]+  `Mohd. Irfan, mobile 9000.., a/c ..`
    B  used by     <identifier> [is] used by <name> [(,|and) <name>]*   and the Hindi form
    C  ka number   <name> ka/का [mobile] number/नंबर [hai/है] <identifier>
    D  his number  `His number is <identifier>` after exactly one person in the previous sentence

Each pattern must match cleanly: only the words the pattern lists between person, cue and
identifier; no other person joined to the same identifier; nothing but a closing connector after
a used-by list. Anything else near a person is MENTIONED_WITH. Hedge wording (hedges.py) turns
OWNS into hedged MENTIONED_WITH and a negation word removes it; unclear or unverified wording
lowers mention confidence. A hedge-only fragment covers the sentences on both sides. When in
doubt, no OWNS.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from tracex_engine.extract.hedges import (
    FORBIDDEN_NAME_TOKENS,
    has_shared_wording,
    is_hedged,
    is_illegible,
    is_negated,
)
from tracex_engine.extract.patterns import (
    ABBREVIATIONS,
    ACCOUNT,
    AGE,
    ALIAS_AFTER,
    APPOSITION_GAP,
    CONNECTOR_GAP,
    DEV_USED_TAIL,
    DOB,
    GENDER,
    HIS_GAP,
    IFSC_AFTER,
    IN_NAME_OF,
    JOINED_TO_NAME,
    KA_GAP,
    KA_TAIL,
    LEADING_NON_NAME,
    LIST_NEXT,
    LOCALITY,
    NAME_KA_NUMBER,
    NAME_KE_NAAM,
    NAME_THEN_FACT,
    OR_AFTER,
    ORG,
    OWNERSHIP_CUE,
    PHONE,
    RELATION,
    ROLE_DEV,
    ROLE_LATIN,
    SENTENCE_END,
    SHARED_NOTE_TAIL,
    UPI_PHONE,
    USED_BY,
    USED_BY_DEV,
    USED_GAP,
    USED_TAIL,
    VEHICLE,
    WARD_WORDS,
)
from tracex_engine.extract.records import (
    CONFIDENCE_CLEAR,
    CONFIDENCE_HEDGED,
    Attribution,
    AttributionCode,
    IdentifierMention,
    IdKind,
    OrgMention,
    PersonMention,
    Relative,
)
from tracex_engine.ingest import SourceRef
from tracex_engine.normalize import (
    Value,
    normalize_account,
    normalize_ifsc,
    normalize_name,
    normalize_org_name,
    normalize_phone,
    normalize_place,
    normalize_vehicle,
    parse_date,
    phone_from_upi,
)

_RELATIONS = {"s": "son", "d": "daughter", "w": "wife"}
_RELATION_WORDS = {
    "son": "son",
    "daughter": "daughter",
    "wife": "wife",
    "putra": "son",
    "putri": "daughter",
    "patni": "wife",
    "पुत्र": "son",
    "पुत्री": "daughter",
    "पत्नी": "wife",
}
_MIN_AGE, _MAX_AGE = 1, 119


@dataclass(frozen=True)
class TextRecords:
    """What one text line yielded."""

    persons: tuple[PersonMention, ...] = ()
    orgs: tuple[OrgMention, ...] = ()
    identifiers: tuple[IdentifierMention, ...] = ()
    attributions: tuple[Attribution, ...] = ()


@dataclass
class _UsedGroup:
    """The people named after `used by` (or `द्वारा`) and what stands next to the list."""

    ident: int  # the nearest identifier before `used by`
    adjacent: bool  # nothing but `is`/`was` stands between that identifier and `used by`
    clean: bool  # nothing but a closing connector follows the list
    or_hedged: bool  # the list is an `or` list: a hedge


@dataclass
class _Candidate:
    start: int
    end: int
    kind: str  # "person" or "org"
    role: str | None = None
    relative: Relative | None = None
    aliases: list[Value] = field(default_factory=list)
    age: Value | None = None
    dob: Value | None = None
    gender: Value | None = None
    locality: Value | None = None
    used_group: _UsedGroup | None = None
    registered: bool = False  # named by "in the name of": never an owner
    registered_for: int | None = None  # identifier of an "in the name of" statement
    fact_spans: list[tuple[int, int]] = field(default_factory=list)  # stated facts, by position


@dataclass
class _Ident:
    kind: IdKind
    start: int
    end: int
    raw: str
    normalized: str
    ifsc: Value | None = None
    full_end: int = 0  # end of the identifier including a trailing `(IFSC ...)`

    def __post_init__(self) -> None:
        self.full_end = self.full_end or self.end


def sentence_spans(text: str) -> list[tuple[int, int, bool]]:
    """Sentence spans (start, end, is_question), terminators excluded; `Mohd.` ends none."""
    spans: list[tuple[int, int, bool]] = []
    start = 0
    for match in SENTENCE_END.finditer(text):
        if match.group()[0] == "." and _ends_abbreviation(text, match.start()):
            continue
        spans.append((start, match.start(), "?" in match.group()))
        start = match.end()
    spans.append((start, len(text), False))
    return [(a, b, q) for a, b, q in spans if text[a:b].strip()]


def _ends_abbreviation(text: str, dot: int) -> bool:
    begin = dot
    while begin > 0 and not text[begin - 1].isspace():
        begin -= 1
    word = text[begin:dot].lower()
    return word in ABBREVIATIONS or (len(word) == 1 and word.isalpha())


@dataclass
class _Parsed:
    sentence: str
    question: bool
    idents: list[_Ident]
    candidates: list[_Candidate]

    @property
    def is_fragment(self) -> bool:
        """A fragment states no identifier and no person of its own (`unverified.`)."""
        return not self.idents and not self.candidates


def extract_text_line(
    source: SourceRef,
    text: str,
    *,
    whole_line: bool = False,
    statement: str | None = None,
) -> TextRecords:
    """Extract persons, organisations, identifiers and attributions from one line.

    Hedge and legibility wording covers the sentence plus any following fragment that states
    no identifier or person; with `whole_line` (an officer note: one note, one statement) it
    covers every sentence of the line, and shared-number wording is searched over the line.
    `statement` replaces the sentence as the `raw_text` of attributions (header lines).
    """
    parsed: list[_Parsed] = []
    for begin, end, question in sentence_spans(text):
        sentence = text[begin:end]
        idents = _find_identifiers(sentence)
        candidates = _find_candidates(sentence, idents)
        _bind_facts(sentence, candidates)
        parsed.append(_Parsed(sentence, question, idents, candidates))
    own_hedge = [is_hedged(p.sentence) or p.question for p in parsed]
    own_illegible = [is_illegible(p.sentence) for p in parsed]

    persons: list[PersonMention] = []
    orgs: list[OrgMention] = []
    identifiers: list[IdentifierMention] = []
    attributions: list[Attribution] = []
    previous: list[PersonMention | OrgMention] = []
    for index, item in enumerate(parsed):
        if whole_line:
            hedged, illegible = any(own_hedge), any(own_illegible)
        else:
            reach = _fragment_reach(parsed, index)
            hedged = any(own_hedge[i] for i in reach)
            illegible = any(own_illegible[i] for i in reach)
        shared = has_shared_wording(text if whole_line else item.sentence)
        records, holders = _finish(
            source, item, hedged, illegible, shared, previous, statement or item.sentence.strip()
        )
        persons.extend(records.persons)
        orgs.extend(records.orgs)
        identifiers.extend(records.identifiers)
        attributions.extend(records.attributions)
        previous = holders
    return TextRecords(tuple(persons), tuple(orgs), tuple(identifiers), tuple(attributions))


def _fragment_reach(parsed: list[_Parsed], index: int) -> list[int]:
    """The sentence and the hedge-capable fragments (no identifier, no person) on both sides."""
    reach = [index]
    following = index + 1
    while following < len(parsed) and parsed[following].is_fragment:
        reach.append(following)
        following += 1
    earlier = index - 1
    while earlier >= 0 and parsed[earlier].is_fragment:
        reach.append(earlier)
        earlier -= 1
    return reach


def _finish(
    source: SourceRef,
    item: _Parsed,
    hedged: bool,
    illegible: bool,
    shared: bool,
    previous: list[PersonMention | OrgMention],
    statement: str,
) -> tuple[TextRecords, list[PersonMention | OrgMention]]:
    sentence = item.sentence
    confidence = CONFIDENCE_HEDGED if illegible else CONFIDENCE_CLEAR
    holders: list[PersonMention | OrgMention] = [
        _build_holder(source, sentence, c, confidence) for c in item.candidates
    ]
    mentions = [
        IdentifierMention(
            kind=i.kind,
            raw_text=i.raw,
            normalized=i.normalized,
            source=source,
            confidence=confidence,
            shared_wording=shared,
            ifsc=i.ifsc,
        )
        for i in item.idents
    ]
    attributions = _attribute(source, item, hedged, statement, holders, mentions, previous)
    records = TextRecords(
        tuple(h for h in holders if isinstance(h, PersonMention)),
        tuple(h for h in holders if isinstance(h, OrgMention)),
        tuple(mentions),
        tuple(attributions),
    )
    return records, holders


# --- identifiers ---------------------------------------------------------------------------


def _free(span: tuple[int, int], taken: list[tuple[int, int]]) -> bool:
    return all(span[1] <= a or span[0] >= b for a, b in taken)


def _find_identifiers(sentence: str) -> list[_Ident]:
    found: list[_Ident] = []
    taken: list[tuple[int, int]] = []

    def add(ident: _Ident) -> None:
        found.append(ident)
        taken.append((ident.start, ident.full_end))

    for match in UPI_PHONE.finditer(sentence):
        phone = phone_from_upi(match.group())
        if phone:
            add(_Ident(IdKind.PHONE, match.start(), match.end(), match.group(), phone))
    for match in ACCOUNT.finditer(sentence):
        digits = normalize_account(match["acc"])
        span = (match.start("acc"), match.end("acc"))
        if digits and _free(span, taken):
            ifsc, tail = _ifsc_after(sentence, span[1])
            add(_Ident(IdKind.ACCOUNT, span[0], span[1], match["acc"], digits, ifsc, tail))
    for match in PHONE.finditer(sentence):
        phone = normalize_phone(match.group())
        if phone and _free(match.span(), taken):
            add(_Ident(IdKind.PHONE, match.start(), match.end(), match.group(), phone))
    for match in VEHICLE.finditer(sentence):
        plate = normalize_vehicle(match.group())
        if plate and _free(match.span(), taken):
            add(_Ident(IdKind.VEHICLE, match.start(), match.end(), match.group(), plate))
    return sorted(found, key=lambda i: i.start)


def _ifsc_after(sentence: str, position: int) -> tuple[Value | None, int]:
    """The IFSC written right after an account, and where the account phrase ends."""
    match = IFSC_AFTER.match(sentence, position)
    if match is None:
        return None, position
    code = normalize_ifsc(match["code"])
    return (Value(match["code"], code) if code else None), match.end()


# --- people and organisations --------------------------------------------------------------


def _trim(sentence: str, start: int, end: int) -> tuple[int, int]:
    """Drop leading role or function words and trailing punctuation from a name span."""
    while start < end:
        first = sentence[start:end].split(None, 1)
        if first and first[0].lower() in LEADING_NON_NAME and len(first) > 1:
            start = sentence.index(first[1], start + len(first[0]))
        else:
            break
    while end > start and sentence[end - 1] in ".,;:-":
        end -= 1
    return start, end


def _cut_at_forbidden(sentence: str, start: int, end: int) -> int:
    """End a name before any hedge, negation or connector word: those are never names."""
    for token in re.finditer(r"\S+", sentence[start:end]):
        if token.group().strip(".,;:()").lower() in FORBIDDEN_NAME_TOKENS:
            return start + token.start()
    return end


def _find_candidates(sentence: str, idents: list[_Ident]) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    reserved = [(i.start, i.end) for i in idents]

    def add(start: int, end: int, kind: str = "person") -> _Candidate | None:
        start, end = _trim(sentence, start, _cut_at_forbidden(sentence, start, end))
        raw = sentence[start:end]
        if not raw or (normalize_org_name(raw) if kind == "org" else normalize_name(raw)) == "":
            return None
        for existing in candidates:
            if existing.start == start:
                return existing
        if not _free((start, end), reserved):
            return None
        candidate = _Candidate(start, end, kind)
        candidates.append(candidate)
        reserved.append((start, end))
        return candidate

    for match in ORG.finditer(sentence):
        add(match.start("name"), match.end("name"), "org")
    for pattern in (ROLE_LATIN, ROLE_DEV):
        for match in pattern.finditer(sentence):
            if candidate := add(match.start("name"), match.end("name")):
                candidate.role = candidate.role or match["role"].lower()
    for match in RELATION.finditer(sentence):
        _, name_end = _trim(sentence, match.start("name"), match.end("name"))
        holder = next((c for c in candidates if c.end == name_end), None)
        holder = holder or add(match.start("name"), match.end("name"))
        r_start, r_end = _trim(sentence, match.start("relname"), match.end("relname"))
        if holder is not None and holder.relative is None and r_end > r_start:
            raw = sentence[r_start:r_end]
            relation = _relation_code(match["rel"])
            holder.relative = Relative(relation, Value(raw, normalize_name(raw)))
            holder.fact_spans.append((name_end, r_end))
            reserved.append((r_start, r_end))
    for match in NAME_THEN_FACT.finditer(sentence):
        add(match.start("name"), match.end("name"))
    for match in NAME_KA_NUMBER.finditer(sentence):
        add(match.start("name"), match.end("name"))
    for pattern, devanagari in ((USED_BY, False), (USED_BY_DEV, True)):
        for match in pattern.finditer(sentence):
            _used_by(sentence, idents, match, add, devanagari=devanagari)
    for match in IN_NAME_OF.finditer(sentence):
        if candidate := add(match.start("name"), match.end("name")):
            candidate.registered = True
            candidate.registered_for = _nearest_before(idents, match.start())
    for match in NAME_KE_NAAM.finditer(sentence):
        group = "name" if match["name"] else "lname"
        if candidate := add(match.start(group), match.end(group)):
            candidate.registered = True
            candidate.registered_for = _nearest_before(idents, match.start())

    for candidate in candidates:
        alias = ALIAS_AFTER.match(sentence, candidate.end)
        if alias and candidate.kind == "person":
            a_start, a_end = _trim(sentence, alias.start("alias"), alias.end("alias"))
            raw = sentence[a_start:a_end]
            if normalize_name(raw):
                candidate.aliases.append(Value(raw, normalize_name(raw)))
                candidate.fact_spans.append((candidate.end, a_end))
    return sorted(candidates, key=lambda c: c.start)


def _used_by(
    sentence: str,
    idents: list[_Ident],
    match: re.Match[str],
    add: Callable[[int, int], _Candidate | None],
    *,
    devanagari: bool,
) -> None:
    """Read `<identifier> is used by <name> [, <name> and <name>]` into one `_UsedGroup`."""
    spans = [(match.start("name"), match.end("name"), False)]
    position = match.end() if devanagari else match.end("name")
    while not devanagari and (following := LIST_NEXT.match(sentence, position)):
        spans.append((following.start("name"), following.end("name"), "or" in following["sep"]))
        position = following.end("name")
    added = [add(start, end) for start, end, _ in spans]
    alias = ALIAS_AFTER.match(sentence, position)
    if alias and not devanagari:
        position = alias.end()
    tail = sentence[position:]
    or_listed = any(flag for *_, flag in spans) or OR_AFTER.match(sentence, position) is not None
    index = _nearest_before(idents, match.start())
    if index is None:
        return
    bridge = sentence[idents[index].full_end : match.start("name" if devanagari else 0)]
    adjacent = bool(re.fullmatch(r"\s*", bridge) if devanagari else USED_GAP.match(bridge))
    tail_ok = (DEV_USED_TAIL if devanagari else USED_TAIL).match(tail) is not None
    shared_note = SHARED_NOTE_TAIL.match(tail)
    tail_ok = tail_ok or bool(shared_note and has_shared_wording(shared_note["inside"]))
    clean = tail_ok and all(c is not None for c in added)
    group = _UsedGroup(index, adjacent, clean, or_listed)
    for candidate in added:
        if candidate is not None:
            candidate.used_group = group


def _relation_code(token: str) -> str:
    lowered = token.lower()
    if "/" in lowered:
        return _RELATIONS[lowered[0]]
    return _RELATION_WORDS[lowered.split()[0]]


def _nearest_before(idents: list[_Ident], position: int) -> int | None:
    before = [index for index, i in enumerate(idents) if i.end <= position]
    return before[-1] if before else None


def _build_holder(
    source: SourceRef, sentence: str, candidate: _Candidate, confidence: float
) -> PersonMention | OrgMention:
    raw = sentence[candidate.start : candidate.end]
    if candidate.kind == "org":
        return OrgMention(
            raw_text=raw,
            normalized=normalize_org_name(raw),
            source=source,
            confidence=confidence,
            locality=candidate.locality,
        )
    return PersonMention(
        raw_text=raw,
        normalized=normalize_name(raw),
        source=source,
        confidence=confidence,
        role=candidate.role,
        aliases=tuple(candidate.aliases),
        relative=candidate.relative,
        age=candidate.age,
        dob=candidate.dob,
        gender=candidate.gender,
        locality=candidate.locality,
    )


# --- facts about a person ------------------------------------------------------------------


def _preceding(
    candidates: list[_Candidate], position: int, *, person_only: bool
) -> _Candidate | None:
    before = [
        c for c in candidates if c.end <= position and (c.kind == "person" or not person_only)
    ]
    return before[-1] if before else None


def _bind_facts(sentence: str, candidates: list[_Candidate]) -> None:
    for match in AGE.finditer(sentence):
        years = int(match["n"])
        owner = _preceding(candidates, match.start(), person_only=True)
        if owner and owner.age is None and _MIN_AGE <= years <= _MAX_AGE:
            owner.age = Value(match.group(), str(years))
            owner.fact_spans.append(match.span())
    for match in DOB.finditer(sentence):
        born = parse_date(match["date"])
        owner = _preceding(candidates, match.start(), person_only=True)
        if owner and owner.dob is None and born:
            owner.dob = Value(match.group(), born.isoformat())
            owner.fact_spans.append(match.span())
    for match in GENDER.finditer(sentence):
        owner = _preceding(candidates, match.start(), person_only=True)
        if owner and owner.gender is None:
            female = (match["en"] or match["rom"] or "").lower() in ("female", "mahila") or match[
                "hi"
            ] == "महिला"
            owner.gender = Value(match.group(), "female" if female else "male")
            owner.fact_spans.append(match.span())
    for match in LOCALITY.finditer(sentence):
        owner = _preceding(candidates, match.start(), person_only=False)
        if owner and owner.locality is None:
            place = normalize_place(match["loc"])
            if match["kw"].lower() in WARD_WORDS:
                place = f"ward {place}"
            owner.locality = Value(match.group(), place)
            owner.fact_spans.append(match.span())


# --- attribution ---------------------------------------------------------------------------


def _attribute(
    source: SourceRef,
    item: _Parsed,
    hedged: bool,
    statement: str,
    holders: list[PersonMention | OrgMention],
    mentions: list[IdentifierMention],
    previous: list[PersonMention | OrgMention],
) -> list[Attribution]:
    """Tie identifiers to people; OWNS only from the closed patterns, only without doubt."""
    sentence, idents, candidates = item.sentence, item.idents, item.candidates
    negated = is_negated(sentence)
    result: list[Attribution] = []
    pairs = list(zip(candidates, holders, strict=True))

    def emit(
        holder: PersonMention | OrgMention,
        index: int,
        code: AttributionCode,
        extra_hedge: bool = False,
    ) -> None:
        is_hedged_here = hedged or extra_hedge
        if code is AttributionCode.OWNS:
            if negated:
                return
            if is_hedged_here:
                code = AttributionCode.MENTIONED_WITH
        result.append(Attribution(holder, mentions[index], code, is_hedged_here, source, statement))

    for candidate, holder in pairs:
        group = candidate.used_group
        if group is not None:
            if negated:
                continue
            sure = group.adjacent and group.clean
            owns = AttributionCode.OWNS if sure else AttributionCode.MENTIONED_WITH
            emit(holder, group.ident, owns, group.or_hedged or not group.clean)
            continue
        if candidate.registered and candidate.registered_for is None:
            candidate.registered_for = _identifier_after(sentence, idents, candidate)
        if candidate.registered_for is not None:
            emit(holder, candidate.registered_for, AttributionCode.MENTIONED_WITH)

    stated = {c.used_group.ident for c in candidates if c.used_group}
    for index, ident in enumerate(idents):
        if index in stated:
            continue
        before = [(c, h) for c, h in pairs if c.end <= ident.start and not c.registered]
        _, pronoun = _ownership_cue(sentence, ident)
        if not before:
            only_his_number = pronoun and HIS_GAP.match(_cut(sentence, idents, 0, ident.start))
            _from_previous_sentence(emit, index, previous, bool(only_his_number))
            continue
        nearest, owner = before[-1]
        group_members = _listed_group(sentence, idents, [c for c, _ in before])
        if pronoun and len(before) >= 2:
            for _, holder in before:
                emit(holder, index, AttributionCode.MENTIONED_WITH)
        elif len(group_members) > 1:
            for member in group_members:
                emit(holders[candidates.index(member)], index, AttributionCode.MENTIONED_WITH)
        elif _owns_shape(sentence, idents, candidates, nearest, ident):
            emit(owner, index, AttributionCode.OWNS)
        else:
            emit(owner, index, AttributionCode.MENTIONED_WITH)
    return result


def _from_previous_sentence(
    emit: Callable[..., None],
    index: int,
    previous: list[PersonMention | OrgMention],
    his_or_her_number: bool,
) -> None:
    """Pattern D: `His number is X` binds only to a single person of the previous sentence."""
    if not his_or_her_number:
        return
    code = AttributionCode.OWNS if len(previous) == 1 else AttributionCode.MENTIONED_WITH
    for holder in previous:
        emit(holder, index, code)


def _owns_shape(
    sentence: str,
    idents: list[_Ident],
    candidates: list[_Candidate],
    person: _Candidate,
    ident: _Ident,
) -> bool:
    """Pattern A (apposition) or C (`<name> ka number <identifier>`) matches cleanly."""
    if JOINED_TO_NAME.search(sentence[: person.start]):
        return False
    if _apposed(sentence, idents, person, ident):
        return True
    gap = _cut(sentence, idents, _phrase_end(sentence, idents, person, ident.start), ident.start)
    if not KA_GAP.match(gap):
        return False
    following = [c.start for c in candidates if c.start >= ident.full_end]
    following += [i.start for i in idents if i.start >= ident.full_end]
    tail = sentence[ident.full_end : min(following, default=len(sentence))]
    return KA_TAIL.match(tail) is not None


def _apposed(sentence: str, idents: list[_Ident], person: _Candidate, ident: _Ident) -> bool:
    """Pattern A: `person, cue identifier` and every identifier between them is such a pair too."""
    start = _phrase_end(sentence, idents, person, ident.start)
    between = [i for i in idents if start <= i.start and i.full_end <= ident.start]
    if not all(_apposed(sentence, idents, person, i) for i in between):
        return False
    return APPOSITION_GAP.match(_cut(sentence, idents, start, ident.start)) is not None


def _identifier_after(sentence: str, idents: list[_Ident], candidate: _Candidate) -> int | None:
    """The identifier standing right after a name (`in the name of X, mobile Y`), if any."""
    for index, ident in enumerate(idents):
        if ident.start >= candidate.end:
            gap = _cut(
                sentence, idents, _phrase_end(sentence, idents, candidate, ident.start), ident.start
            )
            return index if APPOSITION_GAP.match(gap) else None
    return None


def _cut(sentence: str, idents: list[_Ident], start: int, end: int) -> str:
    """`sentence[start:end]` with the identifiers inside it cut out."""
    pieces: list[str] = []
    position = start
    for ident in idents:
        if start <= ident.start and ident.full_end <= end:
            pieces.append(sentence[position : ident.start])
            position = ident.full_end
    pieces.append(sentence[position:end])
    return "".join(pieces)


def _phrase_end(sentence: str, idents: list[_Ident], person: _Candidate, limit: int) -> int:
    """End of the person phrase: the name plus the facts written directly after it."""
    position = person.end
    for start, end in sorted(person.fact_spans):
        if start >= limit:
            break
        if end <= position:
            continue
        if re.fullmatch(r"[\s,]*", _cut(sentence, idents, position, start)):
            position = end
        else:
            break
    return position


def _listed_group(
    sentence: str, idents: list[_Ident], before: list[_Candidate]
) -> list[_Candidate]:
    """The nearest person plus those joined to them by connectors and role words alone, with no
    identifier in between: one identifier after such a group is ambiguous."""
    group = [before[-1]]
    for earlier in reversed(before[:-1]):
        later = group[0]
        gap = sentence[_phrase_end(sentence, idents, earlier, later.start) : later.start]
        between = any(earlier.end <= i.start and i.full_end <= later.start for i in idents)
        if between or not CONNECTOR_GAP.match(gap):
            break
        group.insert(0, earlier)
    return group


def _ownership_cue(sentence: str, ident: _Ident) -> tuple[bool, bool]:
    """Whether an ownership cue sits right before the identifier, and whether it is his or her."""
    if ident.kind is IdKind.ACCOUNT:
        return True, False
    match = OWNERSHIP_CUE.search(sentence[max(0, ident.start - 40) : ident.start])
    return match is not None, bool(match and match.group("pron"))
