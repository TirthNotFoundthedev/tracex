"""Regular expressions for names, identifiers and person facts in FIR text and officer notes.

Shapes read (the data-kit phrase catalogue, docs/specs/data-kit.md section 4.4):
    role + name         `accused Mohd. Irfan`, `आरोपी मोहम्मद इरफ़ान`
    name + relation     `Parminder Atwal s/o Gurmeet Atwal`
    ownership           `Number X is used by <name>`, `<name> ka number X`, `mobile X`, `a/c X`
    registered          `in the name of <name>`, `<name> के नाम पर`
    alias               `<name> urf <alias>`
    facts               `aged 34`, `DOB 12-04-1990`, `male`, `village Kherapur`, `Ward 5`

Text must use Western digits (data-kit convention). Devanagari character classes are explicit
because Python's `\\w` does not match combining vowel signs.
"""

import re

from tracex_engine.normalize import DATE_PATTERN

DEV = r"[ँ-ॣ]"
_DEV_STOP_WORDS = (
    "ने",
    "को",
    "का",
    "की",
    "के",
    "से",
    "में",
    "है",
    "था",
    "थे",
    "और",
    "एक",
    "द्वारा",
    "मोबाइल",
    "फोन",
    "नंबर",
    "नम्बर",
    "उम्र",
    "वर्ष",
    "साल",
    "पुत्र",
    "पुत्री",
    "पत्नी",
    "ग्राम",
    "गांव",
    "मोहल्ला",
    "वार्ड",
    "उर्फ",
    "जन्म",
    "तिथि",
    "खाता",
    "शायद",
    "संभवत",
    "संभवतः",
    "संभावित",
    "लगता",
    "शक",
    "संदेह",
    "कथित",
    "अपुष्ट",
    "अस्पष्ट",
    "नहीं",
    "नही",
    "न",
    "तथा",
    "व",
    "रूप",
    "पुरुष",
    "महिला",
    "आरोपी",
    "अभियुक्त",
    "शिकायतकर्ता",
    "गवाह",
    "संदिग्ध",
    "मुखबिर",
)
_DEV_TOKEN = rf"(?<![\u0900-\u097F])(?!(?:{'|'.join(_DEV_STOP_WORDS)})(?!{DEV})){DEV}+"
NAME_DEV = rf"{_DEV_TOKEN}(?:[ \t]+{_DEV_TOKEN}){{0,2}}"

_LATIN_CAP = r"[A-Z][A-Za-z.-]*(?:['’][A-Z][A-Za-z-]*)?"
NAME_LATIN = (
    rf"{_LATIN_CAP}(?:[ \t]+{_LATIN_CAP}){{0,3}}"
    r"(?:[ \t]+(?:bhai|bhaiya|ji|sahab|sahib|chacha)(?![A-Za-z]))?"
)
NAME = rf"(?:{NAME_LATIN}|{NAME_DEV})"

# Words that start a capitalised run but are not part of the name.
LEADING_NON_NAME = frozenset(
    {
        "the",
        "a",
        "an",
        "one",
        "this",
        "that",
        "then",
        "also",
        "and",
        "but",
        "later",
        "accused",
        "suspect",
        "complainant",
        "witness",
        "victim",
        "informant",
        "informer",
        "arrested",
        "named",
        "person",
    }
)

ORG_MARKER = r"(?:M/[sS]|Messrs)"
_ANY_ORG_MARKER = rf"(?:{ORG_MARKER}|मेसर्स)"

ROLE_LATIN = re.compile(
    r"(?i:(?<![A-Za-z])(?P<role>accused|suspect|complainant|witness|victim|informant|informer"
    r"|arrested|aaropi|abhiyukt|shikayatkarta|gawah|sandigdh))(?![A-Za-z])"
    rf"[\s,:]*(?:(?i:person|named|namely)\s+)?(?!{_ANY_ORG_MARKER}(?![A-Za-zऀ-ॿ]))(?P<name>{NAME})"
)
ROLE_DEV = re.compile(
    r"(?P<role>आरोपी|अभियुक्त|शिकायतकर्ता|गवाह|संदिग्ध|मुखबिर|पी(?:ड़|ड़)ित)"
    rf"[\s,:]*(?!{_ANY_ORG_MARKER}(?![A-Za-zऀ-ॿ]))(?P<name>{NAME})"
)
_RELATION = r"(?:(?i:[sdw]/o|son\s+of|daughter\s+of|wife\s+of|putra|putri|patni)|पुत्र|पुत्री|पत्नी)"
RELATION = re.compile(rf"(?P<name>{NAME})\s*,?\s*(?P<rel>{_RELATION})\s+(?P<relname>{NAME})")
NAME_THEN_FACT = re.compile(
    rf"(?P<name>{NAME_LATIN})\s*,\s*(?=(?i:aged?\s*\d|umra|umar|dob|d\.o\.b|born\s+on)|उम्र|जन्म)"
)
NAME_KA_NUMBER = re.compile(
    rf"(?P<name>{NAME})\s+(?:(?i:ka|ki|ke)|का|की|के)\s+"
    r"(?:(?i:mobile\s+|phone\s+)|मोबाइल\s+|फोन\s+)?(?:(?i:number|no\.?)|नंबर|नम्बर)"
)
_BY_PREFIX = (
    r"(?:(?i:(?:accused|suspect|complainant|witness|victim|informant|informer|arrested)"
    r"|(?:his|her)\s+[a-z]+)\s+)?"
)
USED_BY = re.compile(rf"(?i:(?<![A-Za-z])used\s+by)\s+{_BY_PREFIX}(?P<name>{NAME})")
LIST_NEXT = re.compile(
    rf"(?P<sep>\s*,\s*(?:and\s+|or\s+)?|\s+and\s+(?:also\s+)?(?:by\s+)?|\s+aur\s+|\s*&\s*|\s+or\s+){_BY_PREFIX}(?P<name>{NAME})"
)
OR_AFTER = re.compile(r"\s+or\s+")
USED_BY_DEV = re.compile(
    rf"(?P<name>{NAME})(?:\s+(?:(?i:urf|alias)|उर्फ)\s+{NAME})?\s+द्वारा\s+(?:इस्तेमाल|उपयोग|प्रयोग)"
)
IN_NAME_OF = re.compile(
    r"(?i:(?<![A-Za-z])(?:in\s+the\s+name\s+of|sim\s+subscriber|registered\s+to))"
    rf"\s+(?P<name>{NAME})"
)
NAME_KE_NAAM = re.compile(
    rf"(?P<name>{NAME_DEV})\s+के\s+नाम\s+पर|(?P<lname>{NAME_LATIN})\s+(?i:ke\s+naam\s+par)"
)
ALIAS_AFTER = re.compile(rf"\s+(?:(?i:urf|alias)|उर्फ)\s+(?P<alias>{NAME})")
ORG = re.compile(
    rf"(?<![A-Za-z]){ORG_MARKER}\.?[ \t]+"
    r"(?P<name>[A-Z][A-Za-z0-9&'’.-]*(?:[ \t]+[A-Z][A-Za-z0-9&'’.-]*){0,5})"
)

ORG_DEV = re.compile(rf"मेसर्स[ \t]+(?P<name>{NAME_DEV})")

# Legal suffix words of an organisation name in Devanagari (the Roman ones are ORG_SUFFIXES).
DEV_ORG_SUFFIXES = frozenset(
    {
        "ट्रेडर्स",
        "ट्रेडिंग",
        "एंटरप्राइजेज",
        "एंटरप्राइज",
        "प्राइवेट",
        "लिमिटेड",
        "कंपनी",
        "कम्पनी",
        "एलएलपी",
    }
)

AGE = re.compile(
    r"(?:(?i:(?<![A-Za-z])(?:aged?|umra|umar))|उम्र)\s*:?\s*(?P<n>\d{1,3})"
    r"(?:\s*(?:(?i:yrs?\.?|years?|saal|sal|varsh)|वर्ष|साल))?"
)
DOB = re.compile(
    r"(?:(?i:(?<![A-Za-z])(?:dob|d\.o\.b\.?|date\s+of\s+birth|born\s+on|janm\s+tithi))|जन्म\s+तिथि)"
    rf"\s*:?\s*(?P<date>{DATE_PATTERN})"
)
GENDER = re.compile(
    r"(?i:(?<![A-Za-z])(?P<en>male|female)(?![A-Za-z]))|(?P<hi>पुरुष|महिला)"
    r"|(?i:(?<![A-Za-z])(?P<rom>purush|mahila)(?![A-Za-z]))"
)
_LOCALITY_WORD = rf"[A-Z][A-Za-z'’-]*|{DEV}+"
LOCALITY = re.compile(
    r"(?P<kw>(?i:village|gram|gaon|mohalla|ward)|ग्राम|गांव|मोहल्ला|वार्ड)[ \t]+"
    rf"(?P<loc>\d{{1,3}}(?!\d)|(?:{_LOCALITY_WORD})(?:[ \t]+(?:{_LOCALITY_WORD})){{0,2}})"
)
PERSON_FACT = re.compile(rf"\s*,?\s*(?:{_RELATION}|{AGE.pattern}|{DOB.pattern}|{GENDER.pattern})")
WARD_WORDS = frozenset({"ward", "वार्ड"})

UPI_PHONE = re.compile(
    r"(?<![\w.@])(?P<num>(?:\+?91)?[6-9]\d{9})@(?P<psp>[A-Za-z][A-Za-z0-9.]*)(?![\w@])"
)
ACCOUNT = re.compile(
    r"(?i:(?<![A-Za-z])(?:a/c|acct?\.?|account|khata)|खाता)\s*(?i:(?:no\.?|number|sankhya)|नंबर|संख्या)?\s*:?\s*"
    r"(?P<acc>\d{4,}(?:[ -]\d{2,}){0,4})(?!\d)"
)
IFSC_AFTER = re.compile(
    r"\s*[,(]?\s*(?i:ifsc)\s*[:-]?\s*(?P<code>[A-Za-z]{4}0[A-Za-z0-9]{6})(?:\s*\))?"
)
PHONE = re.compile(r"(?<![\d@.\w])(?:\+?91[ -]?|0)?[6-9]\d{4}[ -]?\d{5}(?![\d\w@])")
VEHICLE = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]{2}[ -]?\d{2}[ -]?[A-Za-z]{1,3}[ -]?\d{4}(?![A-Za-z0-9])"
)

_CUE_WORDS = (
    r"mobile|phone|cell|contact|number|num|no\.?|vehicle|plate|bike|motorcycle|scooter|car"
    r"|registration|vahan|owns|holds|uses|मोबाइल|फोन|नंबर|नम्बर|वाहन"
)
OWNERSHIP_CUE = re.compile(
    r"(?i:(?P<pron>(?<![A-Za-z])(?:his|her)\s+)?"
    rf"(?:(?<![A-Za-z])(?:{_CUE_WORDS})[\s:.,-]*(?:(?:is|are|was|है)\s+)?)+)$"
)

SENTENCE_END = re.compile(r"[.!?;।॥]+(?=\s|$)")
ABBREVIATIONS = frozenset(
    {
        "mohd",
        "md",
        "mr",
        "mrs",
        "ms",
        "smt",
        "dr",
        "shri",
        "st",
        "no",
        "vs",
        "pvt",
        "ltd",
        "co",
        "m/s",
        "messrs",
    }
)

CUE_WORDS = _CUE_WORDS
_CONNECTOR = r"(?:and|aur|tatha|&|और|तथा|व)"
_ROLE_WORD = (
    r"(?:accused|suspect|complainant|witness|victim|informant|informer|arrested|aaropi|abhiyukt"
    r"|shikayatkarta|gawah|sandigdh|आरोपी|अभियुक्त|शिकायतकर्ता|गवाह|संदिग्ध|मुखबिर"
    r"|पी(?:ड़|ड़)ित)"
)
_WORD_EDGE_LEFT = r"(?<![A-Za-zऀ-ॿ])"
_WORD_EDGE_RIGHT = r"(?![A-Za-zऀ-ॿ])"
_CUE_PHRASE = (
    rf"{_WORD_EDGE_LEFT}(?:a/c|acct?\.?|account|khata\s+sankhya|khata|खाता(?:\s+(?:संख्या|नंबर))?|{_CUE_WORDS})"
    rf"{_WORD_EDGE_RIGHT}[\s:.\-]*"
)
# Pattern A: text allowed between a person phrase and an identifier (identifiers cut out): a
# separator (comma, semicolon, colon, dash or bracket) or `'s`, then cue [is]; further pairs
# are joined by a separator or a connector. No verb before the cue, no other words.
_PAIR = (
    r"(?:"
    + _WORD_EDGE_LEFT
    + r"(?:his|her)"
    + _WORD_EDGE_RIGHT
    + r"\s+)?(?:"
    + _CUE_PHRASE
    + r")+(?:(?:is|are|was|है)\s+)?"
)
_SEPARATOR = r"[,;:(\-]"
APPOSITION_GAP = re.compile(
    r"^(?:\s*"
    + _SEPARATOR
    + r"\s*|\s*['’]s\s+)"
    + _PAIR
    + r"(?:(?:\s*(?:"
    + _SEPARATOR
    + r"|"
    + _WORD_EDGE_LEFT
    + _CONNECTOR
    + _WORD_EDGE_RIGHT
    + r"))+\s*"
    + _PAIR
    + r")*\s*$",
    re.IGNORECASE,
)
# Pattern D: `His number is <identifier>` from the start of the sentence.
HIS_GAP = re.compile(
    r"^\s*(?:his|her)\s+(?:" + _CUE_PHRASE + r")+(?:(?:is|are|was)\s+)?$", re.IGNORECASE
)
# Pattern C: `<name> ka number <identifier> [hai]`.
KA_GAP = re.compile(
    r"^\s*(?:ka|ki|ke|का|की|के)\s+(?:(?:mobile|phone|मोबाइल|फोन)\s+)?"
    r"(?:number|no\.?|नंबर|नम्बर)\s*(?:(?:hai|है)\s+)?$",
    re.IGNORECASE,
)
KA_TAIL = re.compile(
    r"^\s*(?:(?:hai|hain|है|हैं)\s*)?[,;]?\s*(?:" + _CONNECTOR + r"\s*)?$", re.IGNORECASE
)
# Pattern B: `<identifier> [is] used by <list>`; what may sit before `used` and after the list.
USED_GAP = re.compile(
    r"^\s*,?\s*(?:(?:is|are|was|being|is\s+being|are\s+being)\s*)?$", re.IGNORECASE
)
USED_TAIL = re.compile(r"^\s*$|^\s*,?\s*(?:and|aur|&|or)(?![A-Za-z]).*$", re.IGNORECASE | re.DOTALL)
DEV_USED_TAIL = re.compile(r"^\s*(?:(?:किया\s+(?:जाता|जाती|गया)|होता|होती)\s*)?(?:है|हैं)?\s*$")
# Two people count as one listed group when only connectors and role words separate them.
CONNECTOR_GAP = re.compile(
    r"^(?:[\s,&]+|"
    + _WORD_EDGE_LEFT
    + r"(?:"
    + _CONNECTOR
    + "|"
    + _ROLE_WORD
    + r")"
    + _WORD_EDGE_RIGHT
    + r")*$",
    re.IGNORECASE,
)

# A name written just before a connector that leads into the person phrase: the identifier
# would belong to a list of people, one of whom the extractor did not recognise.
_NAME_TOKEN = rf"(?:{_WORD_EDGE_LEFT}[A-Z][A-Za-z.'’-]*|{_DEV_TOKEN})"
JOINED_TO_NAME = re.compile(
    r"(?:urf|alias|उर्फ)\s*(?:"
    + _ROLE_WORD
    + r"\s*)+$|"
    + _NAME_TOKEN
    + r"\s*(?:[,&]|"
    + _CONNECTOR
    + r")\s*(?:"
    + _ROLE_WORD
    + r"\s*)*$",
)

# `used by <name> (shop number, PCO)`: a closing parenthesis holding only shared-number wording.
SHARED_NOTE_TAIL = re.compile(r"^\s*\((?P<inside>[^()]*)\)\s*$")

# After the identifier of pattern A (and its optional IFSC): a closing bracket, `hai`/`है`, then
# only commas, connectors, role words or the next cue. Any other word may change the meaning
# (`se dhamki mili`, `में पैसे भेजे`, `of the accused`), so the statement is not an ownership.
A_TAIL = re.compile(
    r"^\s*\)?\s*(?:(?:hai|hain|है|हैं)\s*)?(?:(?:[,;]|"
    + _CONNECTOR
    + "|"
    + _ROLE_WORD
    + "|"
    + _CUE_PHRASE
    + r")\s*)*$",
    re.IGNORECASE,
)
