"""Entity extraction from one line of FIR narrative or officer note.

The line is split into sentences. Within a sentence, people and organisations are found from
the cue shapes in `patterns`, identifiers by their own formats, and an identifier is tied to a
person by these rules:

1. `<identifier> ... used by <name>` ties it to every name in an and/comma list (OWNS); an `or`
   list is a hedge.
2. An identifier after an ownership cue (`mobile`, `number`, `a/c`, `plate`) is OWNS only when
   it stands next to exactly one person: between that person (with their age, relative, alias,
   locality) and the cue there is only punctuation, his/her, `'s` or further cue words. Two
   people joined by `and`/commas before one identifier, or any other wording in between, give
   MENTIONED_WITH to each. `his number` binds only to a single person of the previous sentence.
   `in the name of <name>` gives MENTIONED_WITH, never OWNS.
3. Hedge wording (see hedges.py) or a negation word in the sentence removes OWNS: hedged gives
   MENTIONED_WITH with `hedged`, negated gives nothing. Hedge and unclear-text wording covers
   the sentence plus following fragments with no identifier or person (a whole note line for
   notes); a question is hedged.

Unclear or unverified text lowers the confidence of every mention in its scope. When in doubt,
no OWNS.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from tracex_engine.extract.hedges import (
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
    DOB,
    GENDER,
    IFSC_AFTER,
    IN_NAME_OF,
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
    UPI_PHONE,
    USED_BY,
    USED_BY_DEV,
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
    used_by: int | None = None  # index of the identifier named by "used by"
    or_hedged: bool = False  # named in an "or" list: a hedge
    registered: bool = False  # named by "in the name of": never an owner by apposition
    registered_for: int | None = None  # identifier of an "in the name of" statement
    fact_ends: list[int] = field(default_factory=list)  # where each stated fact ends

    def extent(self, before: int) -> int:
        """End of the name and of every fact stated about it that ends before `before`."""
        return max([self.end, *(e for e in self.fact_ends if e <= before)])


@dataclass
class _Ident:
    kind: IdKind
    start: int
    end: int
    raw: str
    normalized: str
    ifsc: Value | None = None


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
    reach = [index]
    following = index + 1
    while following < len(parsed) and parsed[following].is_fragment:
        reach.append(following)
        following += 1
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
        taken.append((ident.start, ident.end))

    for match in UPI_PHONE.finditer(sentence):
        phone = phone_from_upi(match.group())
        if phone:
            add(_Ident(IdKind.PHONE, match.start(), match.end(), match.group(), phone))
    for match in ACCOUNT.finditer(sentence):
        digits = normalize_account(match["acc"])
        span = (match.start("acc"), match.end("acc"))
        if digits and _free(span, taken):
            ifsc = _ifsc_after(sentence, span[1])
            add(_Ident(IdKind.ACCOUNT, span[0], span[1], match["acc"], digits, ifsc))
    for match in PHONE.finditer(sentence):
        phone = normalize_phone(match.group())
        if phone and _free(match.span(), taken):
            add(_Ident(IdKind.PHONE, match.start(), match.end(), match.group(), phone))
    for match in VEHICLE.finditer(sentence):
        plate = normalize_vehicle(match.group())
        if plate and _free(match.span(), taken):
            add(_Ident(IdKind.VEHICLE, match.start(), match.end(), match.group(), plate))
    return sorted(found, key=lambda i: i.start)


def _ifsc_after(sentence: str, position: int) -> Value | None:
    match = IFSC_AFTER.match(sentence, position)
    if match is None:
        return None
    code = normalize_ifsc(match["code"])
    return Value(match["code"], code) if code else None


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


def _find_candidates(sentence: str, idents: list[_Ident]) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    reserved = [(i.start, i.end) for i in idents]

    def add(start: int, end: int, kind: str = "person") -> _Candidate | None:
        start, end = _trim(sentence, start, end)
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
            holder.fact_ends.append(r_end)
            reserved.append((r_start, r_end))
    for match in NAME_THEN_FACT.finditer(sentence):
        add(match.start("name"), match.end("name"))
    for match in NAME_KA_NUMBER.finditer(sentence):
        add(match.start("name"), match.end("name"))
    for pattern in (USED_BY, USED_BY_DEV):
        for match in pattern.finditer(sentence):
            for candidate, or_listed in _used_by_names(sentence, match, add):
                candidate.used_by = _nearest_before(idents, match.start())
                candidate.or_hedged = or_listed
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
                candidate.fact_ends.append(a_end)
    return sorted(candidates, key=lambda c: c.start)


def _used_by_names(
    sentence: str,
    match: re.Match[str],
    add: Callable[[int, int], _Candidate | None],
) -> list[tuple[_Candidate, bool]]:
    """Every person named after `used by`: a comma or `and` list; `or` marks them hedged."""
    found: list[tuple[_Candidate, bool]] = []
    spans = [(match.start("name"), match.end("name"), False)]
    position = match.end("name")
    while following := LIST_NEXT.match(sentence, position):
        spans.append((following.start("name"), following.end("name"), "or" in following["sep"]))
        position = following.end("name")
    or_after = OR_AFTER.match(sentence, position) is not None
    any_or = or_after or any(flag for *_, flag in spans)
    for start, end, _ in spans:
        if candidate := add(start, end):
            found.append((candidate, any_or))
    return found


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
            owner.fact_ends.append(match.end())
    for match in DOB.finditer(sentence):
        born = parse_date(match["date"])
        owner = _preceding(candidates, match.start(), person_only=True)
        if owner and owner.dob is None and born:
            owner.dob = Value(match.group(), born.isoformat())
            owner.fact_ends.append(match.end())
    for match in GENDER.finditer(sentence):
        owner = _preceding(candidates, match.start(), person_only=True)
        if owner and owner.gender is None:
            female = (match["en"] or "").lower() == "female" or match["hi"] == "महिला"
            owner.gender = Value(match.group(), "female" if female else "male")
            owner.fact_ends.append(match.end())
    for match in LOCALITY.finditer(sentence):
        owner = _preceding(candidates, match.start(), person_only=False)
        if owner and owner.locality is None:
            place = normalize_place(match["loc"])
            if match["kw"].lower() in WARD_WORDS:
                place = f"ward {place}"
            owner.locality = Value(match.group(), place)
            owner.fact_ends.append(match.end())


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
    """Tie identifiers to people. OWNS only when nothing is in doubt (module docstring)."""
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
        if candidate.used_by is not None:
            emit(holder, candidate.used_by, AttributionCode.OWNS, candidate.or_hedged)
            continue
        if candidate.registered and candidate.registered_for is None:
            candidate.registered_for = _identifier_after(sentence, idents, candidate)
        if candidate.registered_for is not None:
            emit(holder, candidate.registered_for, AttributionCode.MENTIONED_WITH)

    stated = {c.used_by for c in candidates if c.used_by is not None}
    for index, ident in enumerate(idents):
        if index in stated:
            continue
        has_cue, pronoun = _ownership_cue(sentence, ident)
        before = [(c, h) for c, h in pairs if c.end <= ident.start and not c.registered]
        if not before:
            _from_previous_sentence(emit, index, previous, has_cue and pronoun)
            continue
        owner_candidate, owner = before[-1]
        group = _listed_group(sentence, idents, [c for c, _ in before])
        alone = len(group) == 1
        close = _in_apposition(sentence, idents, owner_candidate, ident)
        if pronoun and len(before) >= 2:
            for _, holder in before:
                emit(holder, index, AttributionCode.MENTIONED_WITH)
        elif has_cue and close and alone:
            emit(owner, index, AttributionCode.OWNS)
        elif not alone:
            for member in group:
                emit(holders[candidates.index(member)], index, AttributionCode.MENTIONED_WITH)
        else:
            emit(owner, index, AttributionCode.MENTIONED_WITH)
    return result


def _from_previous_sentence(
    emit: Callable[..., None],
    index: int,
    previous: list[PersonMention | OrgMention],
    his_or_her_cue: bool,
) -> None:
    """`His number is X` with no person earlier in the sentence: only one candidate is safe."""
    if not his_or_her_cue:
        return
    code = AttributionCode.OWNS if len(previous) == 1 else AttributionCode.MENTIONED_WITH
    for holder in previous:
        emit(holder, index, code)


def _identifier_after(sentence: str, idents: list[_Ident], candidate: _Candidate) -> int | None:
    """The identifier standing right after a name (`in the name of X, mobile Y`), if any."""
    for index, ident in enumerate(idents):
        if ident.start >= candidate.end:
            gap = _gap_without(sentence, idents, candidate.extent(ident.start), ident.start)
            return index if APPOSITION_GAP.match(gap) else None
    return None


def _gap_without(sentence: str, idents: list[_Ident], start: int, end: int) -> str:
    """`sentence[start:end]` with the identifiers inside it cut out."""
    pieces: list[str] = []
    position = start
    for ident in idents:
        if start <= ident.start and ident.end <= end:
            pieces.append(sentence[position : ident.start])
            position = ident.end
    pieces.append(sentence[position:end])
    return "".join(pieces)


def _in_apposition(
    sentence: str, idents: list[_Ident], candidate: _Candidate, ident: _Ident
) -> bool:
    gap = _gap_without(sentence, idents, candidate.extent(ident.start), ident.start)
    return APPOSITION_GAP.match(gap) is not None


def _listed_group(
    sentence: str, idents: list[_Ident], before: list[_Candidate]
) -> list[_Candidate]:
    """The nearest person and those joined to them by `and`/commas/role words with no
    identifier in between: one identifier after such a group is ambiguous."""
    group = [before[-1]]
    for earlier in reversed(before[:-1]):
        later = group[0]
        gap = sentence[earlier.extent(later.start) : later.start]
        between = any(earlier.end <= i.start and i.end <= later.start for i in idents)
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
