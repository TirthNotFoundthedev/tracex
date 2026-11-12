"""Entity extraction from one line of FIR narrative or officer note.

The line is split into sentences. Within a sentence, people and organisations are found from
the cue shapes in `patterns`, identifiers are found by their own formats, and each identifier is
tied to a person by these rules, strongest first:

1. `<identifier> ... used by <name>` ties the identifier to that name (OWNS). Negated wording
   ("is not used by") ties nothing.
2. An identifier right after an ownership cue (`mobile`, `number`, `a/c`, `plate` ...) is OWNS
   of the nearest person written before it in the sentence (for "his number is", the last
   person of the previous sentence).
3. Any other identifier after a person is MENTIONED_WITH that person; `in the name of <name>`
   is MENTIONED_WITH for the named person, never OWNS.

A sentence with hedge wording never asserts OWNS: its attributions are flagged `hedged` and
downgraded to MENTIONED_WITH. A sentence that marks the text unclear or unverified lowers the
confidence of every mention in it. No assertion is made when in doubt.
"""

from dataclasses import dataclass, field

from tracex_engine.extract.hedges import has_shared_wording, is_hedged, is_illegible
from tracex_engine.extract.patterns import (
    ABBREVIATIONS,
    ACCOUNT,
    AGE,
    ALIAS_AFTER,
    DOB,
    GENDER,
    IFSC_AFTER,
    IN_NAME_OF,
    LEADING_NON_NAME,
    LOCALITY,
    NAME_KA_NUMBER,
    NAME_KE_NAAM,
    NAME_THEN_FACT,
    NEGATION_BEFORE,
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
    negated: bool = False
    registered_for: int | None = None  # identifier of an "in the name of" statement


@dataclass
class _Ident:
    kind: IdKind
    start: int
    end: int
    raw: str
    normalized: str
    ifsc: Value | None = None


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Sentence spans of `text`, terminators excluded; `Mohd.` and initials end none."""
    spans: list[tuple[int, int]] = []
    start = 0
    for match in SENTENCE_END.finditer(text):
        if match.group()[0] == "." and _ends_abbreviation(text, match.start()):
            continue
        spans.append((start, match.start()))
        start = match.end()
    spans.append((start, len(text)))
    return [(a, b) for a, b in spans if text[a:b].strip()]


def _ends_abbreviation(text: str, dot: int) -> bool:
    begin = dot
    while begin > 0 and not text[begin - 1].isspace():
        begin -= 1
    word = text[begin:dot].lower()
    return word in ABBREVIATIONS or (len(word) == 1 and word.isalpha())


def extract_text_line(
    source: SourceRef, text: str, *, shared_scope: str | None = None
) -> TextRecords:
    """Extract persons, organisations, identifiers and attributions from one line.

    `shared_scope` is the text searched for shared-number wording (a note's whole line); by
    default each identifier's own sentence.
    """
    persons: list[PersonMention] = []
    orgs: list[OrgMention] = []
    identifiers: list[IdentifierMention] = []
    attributions: list[Attribution] = []
    last_holder: PersonMention | OrgMention | None = None
    for begin, end in sentence_spans(text):
        records, holders = _extract_sentence(source, text[begin:end], shared_scope, last_holder)
        persons.extend(records.persons)
        orgs.extend(records.orgs)
        identifiers.extend(records.identifiers)
        attributions.extend(records.attributions)
        last_holder = holders[-1] if holders else last_holder
    return TextRecords(tuple(persons), tuple(orgs), tuple(identifiers), tuple(attributions))


def _extract_sentence(
    source: SourceRef,
    sentence: str,
    shared_scope: str | None,
    previous_holder: PersonMention | OrgMention | None,
) -> tuple[TextRecords, list[PersonMention | OrgMention]]:
    hedged = is_hedged(sentence)
    confidence = CONFIDENCE_HEDGED if is_illegible(sentence) else CONFIDENCE_CLEAR
    shared = has_shared_wording(shared_scope if shared_scope is not None else sentence)
    idents = _find_identifiers(sentence)
    candidates = _find_candidates(sentence, idents)
    _bind_facts(sentence, candidates)

    holders: list[PersonMention | OrgMention] = [
        _build_holder(source, sentence, c, confidence) for c in candidates
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
        for i in idents
    ]
    attributions = _attribute(
        source, sentence, hedged, idents, candidates, holders, mentions, previous_holder
    )
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
            reserved.append((r_start, r_end))
    for match in NAME_THEN_FACT.finditer(sentence):
        add(match.start("name"), match.end("name"))
    for match in NAME_KA_NUMBER.finditer(sentence):
        add(match.start("name"), match.end("name"))
    for pattern in (USED_BY, USED_BY_DEV):
        for match in pattern.finditer(sentence):
            if candidate := add(match.start("name"), match.end("name")):
                candidate.used_by = _nearest_before(idents, match.start())
                candidate.negated = NEGATION_BEFORE.search(sentence[: match.start()]) is not None
    for match in IN_NAME_OF.finditer(sentence):
        if candidate := add(match.start("name"), match.end("name")):
            candidate.registered_for = _nearest_before(idents, match.start())
    for match in NAME_KE_NAAM.finditer(sentence):
        group = "name" if match["name"] else "lname"
        if candidate := add(match.start(group), match.end(group)):
            candidate.registered_for = _nearest_before(idents, match.start())

    for candidate in candidates:
        alias = ALIAS_AFTER.match(sentence, candidate.end)
        if alias and candidate.kind == "person":
            a_start, a_end = _trim(sentence, alias.start("alias"), alias.end("alias"))
            raw = sentence[a_start:a_end]
            if normalize_name(raw):
                candidate.aliases.append(Value(raw, normalize_name(raw)))
    return sorted(candidates, key=lambda c: c.start)


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
    for match in DOB.finditer(sentence):
        born = parse_date(match["date"])
        owner = _preceding(candidates, match.start(), person_only=True)
        if owner and owner.dob is None and born:
            owner.dob = Value(match.group(), born.isoformat())
    for match in GENDER.finditer(sentence):
        owner = _preceding(candidates, match.start(), person_only=True)
        if owner and owner.gender is None:
            female = (match["en"] or "").lower() == "female" or match["hi"] == "महिला"
            owner.gender = Value(match.group(), "female" if female else "male")
    for match in LOCALITY.finditer(sentence):
        owner = _preceding(candidates, match.start(), person_only=False)
        if owner and owner.locality is None:
            place = normalize_place(match["loc"])
            if match["kw"].lower() in WARD_WORDS:
                place = f"ward {place}"
            owner.locality = Value(match.group(), place)


# --- attribution ---------------------------------------------------------------------------


def _attribute(
    source: SourceRef,
    sentence: str,
    hedged: bool,
    idents: list[_Ident],
    candidates: list[_Candidate],
    holders: list[PersonMention | OrgMention],
    mentions: list[IdentifierMention],
    previous_holder: PersonMention | OrgMention | None,
) -> list[Attribution]:
    result: list[Attribution] = []
    statement = sentence.strip()
    pairs = list(zip(candidates, holders, strict=True))

    def emit(holder: PersonMention | OrgMention, index: int, code: AttributionCode) -> None:
        if hedged and code is AttributionCode.OWNS:
            code = AttributionCode.MENTIONED_WITH
        result.append(Attribution(holder, mentions[index], code, hedged, source, statement))

    for candidate, holder in pairs:
        if candidate.used_by is not None and not candidate.negated:
            emit(holder, candidate.used_by, AttributionCode.OWNS)
        if candidate.registered_for is not None:
            emit(holder, candidate.registered_for, AttributionCode.MENTIONED_WITH)

    stated = {c.used_by for c in candidates if c.used_by is not None}
    for index, ident in enumerate(idents):
        if index in stated:
            continue
        has_cue, pronoun = _ownership_cue(sentence, ident)
        owner = next((h for c, h in reversed(pairs) if c.end <= ident.start), None)
        if owner is None and pronoun:
            owner = previous_holder
        if owner is not None:
            code = AttributionCode.OWNS if has_cue else AttributionCode.MENTIONED_WITH
            emit(owner, index, code)
    return result


def _ownership_cue(sentence: str, ident: _Ident) -> tuple[bool, bool]:
    """Whether an ownership cue sits right before the identifier, and whether it is his or her."""
    if ident.kind is IdKind.ACCOUNT:
        return True, False
    match = OWNERSHIP_CUE.search(sentence[max(0, ident.start - 40) : ident.start])
    return match is not None, bool(match and match.group("pron"))
