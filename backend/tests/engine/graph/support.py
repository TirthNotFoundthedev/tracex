"""Hand-built extractor records for graph tests: one mention per call, source pinned by caller."""

from tracex_engine.extract import (
    CONFIDENCE_CLEAR,
    Attribution,
    AttributionCode,
    CaseRecords,
    IdentifierMention,
    IdKind,
    OrgMention,
    PersonMention,
    Relative,
)
from tracex_engine.ingest import SourceRef
from tracex_engine.normalize import (
    Value,
    normalize_name,
    normalize_org_name,
    normalize_place,
)

CASE = "C-101"


def src(line: int = 12, file: str = "fir.txt", case: str = CASE) -> SourceRef:
    return SourceRef(case, file, line)


def val(text: str) -> Value:
    return Value(text, normalize_place(text))


def person(
    raw: str,
    line: int = 12,
    file: str = "fir.txt",
    confidence: float = CONFIDENCE_CLEAR,
    aliases: tuple[str, ...] = (),
    relative: Relative | None = None,
    age: str | None = None,
    dob: str | None = None,
    gender: str | None = None,
    locality: str | None = None,
    district: str | None = None,
) -> PersonMention:
    return PersonMention(
        raw_text=raw,
        normalized=normalize_name(raw),
        source=src(line, file),
        confidence=confidence,
        aliases=tuple(Value(a, normalize_name(a)) for a in aliases),
        relative=relative,
        age=Value(age, age) if age else None,
        dob=Value(dob, dob) if dob else None,
        gender=Value(gender, gender.lower()) if gender else None,
        locality=val(locality) if locality else None,
        district=val(district) if district else None,
    )


def son_of(name: str, relation: str = "son") -> Relative:
    return Relative(relation, Value(name, normalize_name(name)))


def org(raw: str, line: int = 12, file: str = "fir.txt", locality: str | None = None) -> OrgMention:
    return OrgMention(
        raw_text=raw,
        normalized=normalize_org_name(raw),
        source=src(line, file),
        confidence=CONFIDENCE_CLEAR,
        locality=val(locality) if locality else None,
    )


def ident(
    kind: IdKind,
    raw: str,
    normalized: str,
    line: int = 12,
    file: str = "fir.txt",
    ifsc: str | None = None,
    shared_wording: bool = False,
) -> IdentifierMention:
    return IdentifierMention(
        kind=kind,
        raw_text=raw,
        normalized=normalized,
        source=src(line, file),
        confidence=CONFIDENCE_CLEAR,
        shared_wording=shared_wording,
        ifsc=Value(ifsc, ifsc.upper()) if ifsc else None,
    )


def phone(
    digits: str, line: int = 12, file: str = "fir.txt", raw: str | None = None
) -> IdentifierMention:
    return ident(IdKind.PHONE, raw or digits, digits, line, file)


def account(
    digits: str, line: int = 12, file: str = "fir.txt", ifsc: str | None = None
) -> IdentifierMention:
    return ident(IdKind.ACCOUNT, digits, digits, line, file, ifsc)


def attribute(
    holder: PersonMention | OrgMention,
    identifier: IdentifierMention,
    code: AttributionCode = AttributionCode.OWNS,
    hedged: bool = False,
    line: int | None = None,
    file: str | None = None,
) -> Attribution:
    where = holder.source if line is None else src(line, file or holder.source.file)
    return Attribution(holder, identifier, code, hedged, where, "statement as written")


def records(
    persons: tuple[PersonMention, ...] = (),
    orgs: tuple[OrgMention, ...] = (),
    identifiers: tuple[IdentifierMention, ...] = (),
    attributions: tuple[Attribution, ...] = (),
    case_id: str = CASE,
) -> CaseRecords:
    return CaseRecords(
        case_id=case_id,
        persons=persons,
        orgs=orgs,
        identifiers=identifiers,
        attributions=attributions,
        cdr_rows=(),
        bank_rows=(),
        sdr_rows=(),
        errors=(),
    )
