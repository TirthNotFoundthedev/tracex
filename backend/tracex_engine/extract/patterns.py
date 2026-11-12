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
    "पुरुष",
    "महिला",
    "आरोपी",
    "अभियुक्त",
    "शिकायतकर्ता",
    "गवाह",
    "संदिग्ध",
    "मुखबिर",
)
_DEV_TOKEN = rf"(?!(?:{'|'.join(_DEV_STOP_WORDS)})(?!{DEV})){DEV}+"
NAME_DEV = rf"{_DEV_TOKEN}(?:[ \t]+{_DEV_TOKEN}){{0,2}}"

_LATIN_CAP = r"[A-Z][A-Za-z.'’-]*"
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

ROLE_LATIN = re.compile(
    r"(?i:(?<![A-Za-z])(?P<role>accused|suspect|complainant|witness|victim|informant|informer"
    r"|arrested|aaropi|abhiyukt|shikayatkarta|gawah|sandigdh))(?![A-Za-z])"
    rf"[\s,:]*(?:(?i:person|named|namely)\s+)?(?P<name>{NAME})"
)
ROLE_DEV = re.compile(
    r"(?P<role>आरोपी|अभियुक्त|शिकायतकर्ता|गवाह|संदिग्ध|मुखबिर|पी(?:ड़|ड़)ित)"
    rf"[\s,:]*(?P<name>{NAME_DEV})"
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
    rf"(?P<sep>\s*,\s*(?:and\s+|or\s+)?|\s+and\s+|\s*&\s*|\s+or\s+){_BY_PREFIX}(?P<name>{NAME})"
)
OR_AFTER = re.compile(r"\s+or\s+")
USED_BY_DEV = re.compile(rf"(?P<name>{NAME_DEV})\s+द्वारा\s+(?:इस्तेमाल|उपयोग|प्रयोग)")
IN_NAME_OF = re.compile(
    r"(?i:(?<![A-Za-z])(?:in\s+the\s+name\s+of|sim\s+subscriber|registered\s+to))"
    rf"\s+(?P<name>{NAME})"
)
NAME_KE_NAAM = re.compile(
    rf"(?P<name>{NAME_DEV})\s+के\s+नाम\s+पर|(?P<lname>{NAME_LATIN})\s+(?i:ke\s+naam\s+par)"
)
ALIAS_AFTER = re.compile(rf"\s+(?:(?i:urf|alias)|उर्फ)\s+(?P<alias>{NAME})")
ORG = re.compile(
    r"(?<![A-Za-z])M/[sS]\.?[ \t]+"
    r"(?P<name>[A-Z][A-Za-z0-9&'’.-]*(?:[ \t]+[A-Z][A-Za-z0-9&'’.-]*){0,5})"
)

AGE = re.compile(
    r"(?:(?i:(?<![A-Za-z])(?:aged?|umra|umar))|उम्र)\s*:?\s*(?P<n>\d{1,3})"
    r"(?:\s*(?:(?i:yrs?\.?|years?|saal|sal|varsh)|वर्ष|साल))?"
)
DOB = re.compile(
    r"(?:(?i:(?<![A-Za-z])(?:dob|d\.o\.b\.?|date\s+of\s+birth|born\s+on))|जन्म\s+तिथि)"
    rf"\s*:?\s*(?P<date>{DATE_PATTERN})"
)
GENDER = re.compile(r"(?i:(?<![A-Za-z])(?P<en>male|female)(?![A-Za-z]))|(?P<hi>पुरुष|महिला)")
_LOCALITY_WORD = rf"[A-Z][A-Za-z'’-]*|{DEV}+"
LOCALITY = re.compile(
    r"(?P<kw>(?i:village|mohalla|ward)|ग्राम|गांव|मोहल्ला|वार्ड)[ \t]+"
    rf"(?P<loc>\d{{1,3}}(?!\d)|(?:{_LOCALITY_WORD})(?:[ \t]+(?:{_LOCALITY_WORD}))?)"
)
WARD_WORDS = frozenset({"ward", "वार्ड"})

UPI_PHONE = re.compile(
    r"(?<![\w.@])(?P<num>(?:\+?91)?[6-9]\d{9})@(?P<psp>[A-Za-z][A-Za-z0-9.]*)(?![\w@])"
)
ACCOUNT = re.compile(
    r"(?i:(?<![A-Za-z])(?:a/c|acct?\.?|account)|खाता)\s*(?i:(?:no\.?|number)|नंबर|संख्या)?\s*:?\s*"
    r"(?P<acc>\d{4,}(?:[ -]\d{2,}){0,4})(?!\d)"
)
IFSC_AFTER = re.compile(r"\s*[,(]?\s*(?i:ifsc)\s*[:-]?\s*(?P<code>[A-Za-z]{4}0[A-Za-z0-9]{6})")
PHONE = re.compile(r"(?<![\d@.\w])(?:\+?91[ -]?|0)?[6-9]\d{4}[ -]?\d{5}(?![\d\w@])")
VEHICLE = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]{2}[ -]?\d{2}[ -]?[A-Za-z]{1,3}[ -]?\d{4}(?![A-Za-z0-9])"
)

_CUE_WORDS = (
    r"mobile|phone|cell|contact|number|num|no\.?|vehicle|plate|bike|motorcycle|scooter|car"
    r"|registration|owns|holds|uses|मोबाइल|फोन|नंबर|नम्बर|वाहन"
)
OWNERSHIP_CUE = re.compile(
    r"(?i:(?P<pron>(?<![A-Za-z])(?:his|her)\s+)?"
    rf"(?:(?<![A-Za-z])(?:{_CUE_WORDS})[\s:.,-]*(?:(?:is|are|was|है)\s+)?)+)$"
)

SENTENCE_END = re.compile(r"[.!?;।॥]+(?=\s|$)")
ABBREVIATIONS = frozenset(
    {"mohd", "md", "mr", "mrs", "ms", "smt", "dr", "shri", "st", "no", "vs", "pvt", "ltd", "co"}
)

CUE_WORDS = _CUE_WORDS
_GAP_WORDS = rf"his|her|is|are|was|and|a/c|acct?\.?|account|खाता|है|{_CUE_WORDS}"
# Text allowed between a person (with their facts) and an identifier for the cue to mean
# "this person's": punctuation, his/her, 's, and further cue words (identifiers cut out).
APPOSITION_GAP = re.compile(
    rf"^(?:[\s,:;()&-]+|['’]s(?![A-Za-z])|(?<![A-Za-z])(?:{_GAP_WORDS})(?![A-Za-z]))*$",
    re.IGNORECASE,
)
# Text allowed between two people for them to count as one listed group.
CONNECTOR_GAP = re.compile(
    r"^(?:[\s,&]+|(?<![A-Za-z])(?:and|accused|suspect|complainant|witness|victim|informant"
    r"|informer|arrested)(?![A-Za-z]))*$",
    re.IGNORECASE,
)
