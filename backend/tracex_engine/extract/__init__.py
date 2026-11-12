"""Extraction: entities, attributes and ownership statements from case files.

`extract_case(case_id, files)` is the entry point the matcher's loader calls. `files` maps a
file name (`fir.txt`, `notes.txt`, `sdr.csv`, `cdr.csv`, `bank.csv`, `notes-02.txt` ...) to its
text. It returns one `CaseRecords`. Every mention keeps the text as written (`raw_text`), the
normalized form and its `SourceRef` (case, file, line); nothing is merged or overwritten, so
the same person written on three lines is three mentions. Unreadable rows and lines are listed
in `CaseRecords.errors`, never dropped silently.

Exposed:
    extract_case                 files of one case -> CaseRecords
    CaseRecords                  persons, orgs, identifiers, attributions, cdr/bank/sdr rows, errors
    PersonMention                name, role, aliases, relative, age, dob, gender, locality, district
    OrgMention                   organisation name without legal suffixes, locality
    IdentifierMention            PHONE / ACCOUNT (with IFSC) / VEHICLE; confidence; shared_wording
    Attribution                  holder -> identifier with OWNS / REGISTERED_TO / MENTIONED_WITH,
                                 `hedged`, the statement as written and its source
    IdKind, AttributionCode      the enums
    CONFIDENCE_CLEAR (0.9), CONFIDENCE_HEDGED (0.5)
    HEDGE_PHRASES, LEGIBILITY_HEDGE_PHRASES, SHARED_WORDING   the wording rules (hedges.py)

Reading rules in one place:
    OWNS            `Number X is used by <name>`, a bank row's account holder, or an
                    identifier right after a cue (`mobile`, `number`, `a/c`, `plate`) following
                    the person in the same sentence
    REGISTERED_TO   only from `sdr.csv` rows; never OWNS
    MENTIONED_WITH  any other identifier after a person, and `in the name of <name>`
    hedged          a sentence with hedge wording never gives OWNS (see hedges.py)
    confidence      0.5 for every mention in a sentence that says the text is unclear or
                    unverified, else 0.9 (gate G5 needs 0.7)
"""

from tracex_engine.extract.case import extract_case
from tracex_engine.extract.hedges import HEDGE_PHRASES, LEGIBILITY_HEDGE_PHRASES, SHARED_WORDING
from tracex_engine.extract.records import (
    CONFIDENCE_CLEAR,
    CONFIDENCE_HEDGED,
    Attribution,
    AttributionCode,
    CaseRecords,
    IdentifierMention,
    IdKind,
    OrgMention,
    PersonMention,
    Relative,
)

__all__ = [
    "CONFIDENCE_CLEAR",
    "CONFIDENCE_HEDGED",
    "HEDGE_PHRASES",
    "LEGIBILITY_HEDGE_PHRASES",
    "SHARED_WORDING",
    "Attribution",
    "AttributionCode",
    "CaseRecords",
    "IdKind",
    "IdentifierMention",
    "OrgMention",
    "PersonMention",
    "Relative",
    "extract_case",
]
