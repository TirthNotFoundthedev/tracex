"""Extraction: entities, attributes and ownership statements from case files.

`extract_case(case_id, files)` is the entry point the matcher's loader calls. `files` maps a
file name (`fir.txt`, `notes.txt`, `sdr.csv`, `cdr.csv`, `bank.csv`, `notes-02.txt` ...) to its
text. It returns one `CaseRecords`. Every mention keeps the text as written (`raw_text`), the
normalized form and its `SourceRef` (case, file, line); nothing is merged or overwritten, so
the same person written on three lines is three mentions. Unreadable rows and lines are listed
in `CaseRecords.errors`, never dropped silently.

Exposed:
    extract_case                 files of one case -> CaseRecords
    file_load_key                sort key of a file name in load order: fir, notes, sdr, cdr, bank;
                                 later batches (`notes-02.txt`) after every baseline file, by
                                 batch number; unknown names last
    CaseRecords                  persons, orgs, identifiers, attributions, cdr/bank/sdr rows, errors
    PersonMention                name, role, aliases, relative, age, dob, gender, locality, district
    OrgMention                   organisation name without legal suffixes, locality
    IdentifierMention            PHONE / ACCOUNT (with IFSC) / VEHICLE; confidence; shared_wording
    Attribution                  holder -> identifier with OWNS / REGISTERED_TO / MENTIONED_WITH,
                                 `hedged`, the statement as written and its source
    IdKind, AttributionCode      the enums
    CONFIDENCE_CLEAR (0.9), CONFIDENCE_HEDGED (0.5)
    HEDGE_PHRASES, LEGIBILITY_HEDGE_PHRASES, SHARED_WORDING   the wording rules (hedges.py)

`raw_text` rule (PERSON and ORG mentions). It is the name as written and nothing else: no role
word before it (`accused`, `complainant`, `आरोपी` ...), no leading `M/s` or `Messrs`, no
`urf`/`alias`/`उर्फ` clause (a person's alias goes to `aliases`), and none of the facts written
beside it (age, `s/o`, village). Honorifics and spelling stay as written (`Mohd. Irfan`); legal
suffixes of an organisation stay too (`Om Traders Pvt Ltd`), only `normalized` drops them.
A role word followed by `M/s`, `Messrs` or a name carrying a legal suffix word (Pvt, Ltd, LLP,
Traders, Trading, Enterprises, Co, Company ...) names an ORG; it never also yields a PERSON.

Ownership contract. OWNS comes only from this closed set of clean patterns (English,
romanised Hindi, Devanagari); everything else near a person is MENTIONED_WITH:
    A  <person phrase> , cue [is] <identifier> [, cue <identifier>]*
       cue = mobile, phone, number, no., contact, a/c, account, plate, vehicle ...; the
       person phrase is the name with the role word and the facts written right after it
       (age, relative, alias, locality); a comma, semicolon, colon, dash or bracket must
       come before the first cue; no verb between name and cue; `'s` also allowed
    B  <identifier> [is/was] used by <name> [(, | and | aur) <name>]*
       (Hindi: <identifier> <name> द्वारा इस्तेमाल [किया जाता] [है]); every named person
       owns it; the list must end the clause (a closing `and ...` is fine); `or` is a hedge
    C  <name> ka/का [mobile] number/नंबर [hai/है] <identifier> [hai/है]
    D  `His/Her number is <identifier>` when the previous sentence has exactly one person
A pattern is void (MENTIONED_WITH, hedged where a list was left open) when another person is
joined to the same identifier by and/aur/और/commas, when a name list is followed by a verb or
a possessive, when hedge wording (hedges.py) or a negation word is in scope (negated: no
attribution at all), or when any other word stands between name, cue and identifier.
REGISTERED_TO comes only from `sdr.csv` rows. Mentions in the scope of unclear or unverified
wording (the sentence, fragments with no identifier or person on both sides, a whole note
line) get confidence 0.5, else 0.9 (gate G5 needs 0.7).
"""

from tracex_engine.extract.case import extract_case
from tracex_engine.extract.hedges import HEDGE_PHRASES, LEGIBILITY_HEDGE_PHRASES, SHARED_WORDING
from tracex_engine.extract.order import file_load_key
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
    "file_load_key",
]
