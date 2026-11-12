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

Reading rules in one place (details in text.py):
    OWNS            `Number X is used by <name> [and <name>]`, a bank row's account holder, or
                    an identifier right after a cue (`mobile`, `number`, `a/c`) standing next
                    to exactly one person; never when hedged, negated or ambiguous
    REGISTERED_TO   only from `sdr.csv` rows; never OWNS
    MENTIONED_WITH  any other identifier near a person, `in the name of <name>`, and hedged
                    or ambiguous ownership (hedged=True for the hedged ones)
    hedged          see hedges.py; negated statements give no attribution at all
    confidence      0.5 for every mention in the scope of "unclear/unverified" wording, else
                    0.9 (gate G5 needs 0.7)
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
