"""Record types produced by extraction. All are immutable and carry provenance.

Every mention keeps the text exactly as written (`raw_text`) beside its normalized form and the
`SourceRef` of the line it came from. Nothing here merges or de-duplicates: the same person
written on three lines is three mentions (the graph stage groups them within a case).
"""

from dataclasses import dataclass
from enum import StrEnum

from tracex_engine.ingest import BankRow, CdrRow, RowError, SdrRow, SourceRef
from tracex_engine.normalize import Value

# Extraction confidence (matching spec, gate G5 needs >= 0.7). A mention in a sentence that
# marks the text unclear or unverified drops to CONFIDENCE_HEDGED.
CONFIDENCE_CLEAR = 0.9
CONFIDENCE_HEDGED = 0.5


class IdKind(StrEnum):
    PHONE = "PHONE"
    ACCOUNT = "ACCOUNT"
    VEHICLE = "VEHICLE"


class AttributionCode(StrEnum):
    """How an entity is tied to an identifier (matching spec section 1, attribution table)."""

    OWNS = "OWNS"
    REGISTERED_TO = "REGISTERED_TO"
    MENTIONED_WITH = "MENTIONED_WITH"


@dataclass(frozen=True)
class IdentifierMention:
    """A phone, account or vehicle as written (`raw_text`) and normalized.

    `shared_wording` is True when the text calls it a shop, PCO, office, family or landline
    number (the SHARED flag input). `ifsc` is set for an account written with its IFSC.
    """

    kind: IdKind
    raw_text: str
    normalized: str
    source: SourceRef
    confidence: float
    shared_wording: bool = False
    ifsc: Value | None = None


@dataclass(frozen=True)
class Relative:
    """`s/o`, `d/o`, `w/o` and the name that follows. `relation` is son, daughter or wife."""

    relation: str
    name: Value


@dataclass(frozen=True)
class PersonMention:
    """A person as written. Optional attributes are what the same sentence stated about them."""

    raw_text: str
    normalized: str
    source: SourceRef
    confidence: float
    role: str | None = None
    aliases: tuple[Value, ...] = ()
    relative: Relative | None = None
    age: Value | None = None
    dob: Value | None = None
    gender: Value | None = None
    locality: Value | None = None
    district: Value | None = None


@dataclass(frozen=True)
class OrgMention:
    """An organisation as written; `normalized` has legal and generic suffixes removed."""

    raw_text: str
    normalized: str
    source: SourceRef
    confidence: float
    locality: Value | None = None


@dataclass(frozen=True)
class Attribution:
    """A person or organisation tied to an identifier by one statement.

    `raw_text` is the statement as written (a sentence, or the whole bank or subscriber row).
    `hedged` is True when the statement used hedge wording (see `HEDGE_PHRASES`): the tie is
    then never OWNS, only MENTIONED_WITH.
    """

    holder: PersonMention | OrgMention
    identifier: IdentifierMention
    code: AttributionCode
    hedged: bool
    source: SourceRef
    raw_text: str


@dataclass(frozen=True)
class CaseRecords:
    """Everything extracted from one case's files, in load order, plus every unreadable row."""

    case_id: str
    persons: tuple[PersonMention, ...]
    orgs: tuple[OrgMention, ...]
    identifiers: tuple[IdentifierMention, ...]
    attributions: tuple[Attribution, ...]
    cdr_rows: tuple[CdrRow, ...]
    bank_rows: tuple[BankRow, ...]
    sdr_rows: tuple[SdrRow, ...]
    errors: tuple[RowError, ...]
    district: Value | None = None
    district_source: SourceRef | None = None
