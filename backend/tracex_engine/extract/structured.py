"""Entities and attributions from parsed CDR, bank and subscriber rows.

The structured sources state their facts plainly, so they carry CONFIDENCE_CLEAR:
- a bank row's `account_holder` OWNS the account on that row;
- a UPI handle that is a phone number is a PHONE;
- a subscriber row (`sdr.csv`) is the only source of REGISTERED_TO, and never of OWNS.
"""

import re
from dataclasses import dataclass

from tracex_engine.extract.records import (
    CONFIDENCE_CLEAR,
    Attribution,
    AttributionCode,
    IdentifierMention,
    IdKind,
    OrgMention,
    PersonMention,
    Relative,
)
from tracex_engine.ingest import BankRow, CdrRow, SdrRow, SourceRef
from tracex_engine.normalize import (
    ORG_SUFFIXES,
    Value,
    normalize_name,
    normalize_org_name,
    normalize_place,
)

# Account holders that say nothing: treated like a blank cell (no owner).
PLACEHOLDER_HOLDERS = frozenset(
    {
        "-",
        "n/a",
        "na",
        "nil",
        "none",
        "null",
        "unknown",
        "अज्ञात",
        "unknown person",
        "not known",
        "not available",
        "अज्ञात व्यक्ति",
    }
)


@dataclass(frozen=True)
class StructuredRecords:
    persons: tuple[PersonMention, ...] = ()
    orgs: tuple[OrgMention, ...] = ()
    identifiers: tuple[IdentifierMention, ...] = ()
    attributions: tuple[Attribution, ...] = ()


def looks_like_org(name: str) -> bool:
    """True for a name written `M/s ...` or containing a legal or generic suffix word."""
    lowered = name.lower().strip()
    return lowered.startswith("m/s") or bool(set(re.findall(r"[a-z]+", lowered)) & ORG_SUFFIXES)


def extract_cdr(row: CdrRow) -> StructuredRecords:
    """The two phone numbers of a call, each cited to the row."""
    return StructuredRecords(
        identifiers=(_phone(row.source, row.calling), _phone(row.source, row.called))
    )


def extract_bank(row: BankRow) -> StructuredRecords:
    """The account (with its IFSC), its holder, and the counterparty when it is a number."""
    account = IdentifierMention(
        kind=IdKind.ACCOUNT,
        raw_text=row.account.raw_text,
        normalized=row.account.normalized,
        source=row.source,
        confidence=CONFIDENCE_CLEAR,
        ifsc=row.ifsc,
    )
    identifiers = [account]
    if row.counterparty is not None:
        kind = IdKind.PHONE if row.counterparty_kind == "PHONE" else IdKind.ACCOUNT
        identifiers.append(
            IdentifierMention(
                kind=kind,
                raw_text=row.counterparty.raw_text,
                normalized=row.counterparty.normalized,
                source=row.source,
                confidence=CONFIDENCE_CLEAR,
            )
        )
    if (
        not normalize_name(row.holder)
        or " ".join(row.holder.lower().split()) in PLACEHOLDER_HOLDERS
    ):
        return StructuredRecords(identifiers=tuple(identifiers))
    org_name = normalize_org_name(row.holder)
    persons: tuple[PersonMention, ...] = ()
    orgs: tuple[OrgMention, ...] = ()
    holder: PersonMention | OrgMention
    if looks_like_org(row.holder) and org_name:
        holder = OrgMention(row.holder, org_name, row.source, CONFIDENCE_CLEAR)
        orgs = (holder,)
    else:
        holder = PersonMention(row.holder, normalize_name(row.holder), row.source, CONFIDENCE_CLEAR)
        persons = (holder,)
    owns = Attribution(holder, account, AttributionCode.OWNS, False, row.source, row.raw_line)
    return StructuredRecords(persons, orgs, tuple(identifiers), (owns,))


def extract_sdr(row: SdrRow) -> StructuredRecords:
    """The subscriber (REGISTERED_TO the number) with relative, locality and district if given."""
    relative_name = normalize_name(row.relative_name)
    subscriber = PersonMention(
        raw_text=row.subscriber_name,
        normalized=normalize_name(row.subscriber_name),
        source=row.source,
        confidence=CONFIDENCE_CLEAR,
        role="subscriber",
        relative=Relative("relative", Value(row.relative_name, relative_name))
        if relative_name
        else None,
        locality=_optional(row.locality),
        district=_optional(row.district),
    )
    phone = _phone(row.source, row.msisdn)
    registered = Attribution(
        subscriber, phone, AttributionCode.REGISTERED_TO, False, row.source, row.raw_line
    )
    return StructuredRecords(
        persons=(subscriber,), identifiers=(phone,), attributions=(registered,)
    )


def _phone(source: SourceRef, value: Value) -> IdentifierMention:
    return IdentifierMention(
        kind=IdKind.PHONE,
        raw_text=value.raw_text,
        normalized=value.normalized,
        source=source,
        confidence=CONFIDENCE_CLEAR,
    )


def _optional(text: str) -> Value | None:
    return Value(text, normalize_place(text)) if text.strip() else None
