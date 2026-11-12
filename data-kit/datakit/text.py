"""Phrase catalogue (data-kit spec section 4.4): sentence shapes per language."""

from __future__ import annotations

from dataclasses import dataclass, field

BANNER = "SYNTHETIC DATA TRACEX-SYN/1 - NOT A REAL RECORD"

LANGS = ("en", "hi", "hi-latn", "mixed")

_REL = {
    "en": {"s/o": "s/o", "d/o": "d/o", "w/o": "w/o"},
    "hi": {"s/o": "पुत्र", "d/o": "पुत्री", "w/o": "पत्नी"},
    "hi-latn": {"s/o": "putra", "d/o": "putri", "w/o": "patni"},
}
_AGE = {"en": "aged {n}", "hi": "उम्र {n} वर्ष", "hi-latn": "umra {n} varsh"}
_DOB = {"en": "DOB {d}", "hi": "जन्म तिथि {d}", "hi-latn": "janm tithi {d}"}
_GENDER = {
    "en": {"male": "male", "female": "female"},
    "hi": {"male": "पुरुष", "female": "महिला"},
    "hi-latn": {"male": "purush", "female": "mahila"},
}
_VILLAGE = {"en": "village {x}", "hi": "ग्राम {x}", "hi-latn": "gram {x}"}
_MOHALLA = {"en": "Mohalla {x}", "hi": "मोहल्ला {x}", "hi-latn": "mohalla {x}"}
_ROLE = {
    "en": {"accused": "Accused", "complainant": "Complainant", "witness": "Witness"},
    "hi": {"accused": "अभियुक्त", "complainant": "शिकायतकर्ता", "witness": "गवाह"},
    "hi-latn": {"accused": "Abhiyukt", "complainant": "Shikayatkarta", "witness": "Gawah"},
}
_PHONE = {"en": "mobile {p}", "hi": "मोबाइल नंबर {p}", "hi-latn": "mobile number {p}"}
_ACCT = {
    "en": "a/c {a} (IFSC {i})",
    "hi": "खाता संख्या {a} (IFSC {i})",
    "hi-latn": "khata sankhya {a} (IFSC {i})",
}
_ACCT_NO_IFSC = {"en": "a/c {a}", "hi": "खाता संख्या {a}", "hi-latn": "khata sankhya {a}"}
_VEHICLE = {"en": "vehicle {v}", "hi": "वाहन {v}", "hi-latn": "vahan {v}"}
_VEHICLE_SEEN = {
    "en": "Vehicle {v} was seen near the spot.",
    "hi": "घटनास्थल के पास वाहन {v} देखा गया।",
    "hi-latn": "Ghatnasthal ke paas vahan {v} dekha gaya.",
}
_NUMBER_USED = {
    "en": "Number {p} is used by {n}.",
    "hi": "नंबर {p} {n} द्वारा उपयोग किया जाता है।",
    "hi-latn": "{n} ka number {p} hai.",
}
_SHARED_NOTE = {
    "en": "Number {p} is the {w} (used by {a} and {b}).",
    "hi": "नंबर {p} {w} है ({a} और {b} उपयोग करते हैं)।",
    "hi-latn": "Number {p} {w} hai ({a} aur {b} upyog karte hain).",
}
_ENDING = {"en": ".", "hi": "।", "hi-latn": "."}
_COMPLAINANT_HEADER = "Complainant: "


def base_lang(lang: str) -> str:
    """Template language: `mixed` uses Devanagari templates."""
    return "hi" if lang == "mixed" else lang


@dataclass
class PersonText:
    """What a person line states. Only stated attributes appear in the text."""

    name: str
    relation: str | None = None
    relative: str | None = None
    age: int | None = None
    dob: str | None = None
    gender: str | None = None
    village: str | None = None
    mohalla: str | None = None
    extras: list[str] = field(default_factory=list)


def clause(lang: str, person: PersonText) -> str:
    t = base_lang(lang)
    parts = [person.name]
    if person.relation and person.relative:
        parts.append(f"{_REL[t][person.relation]} {person.relative}")
    if person.age is not None:
        parts.append(_AGE[t].format(n=person.age))
    if person.dob:
        parts.append(_DOB[t].format(d=person.dob))
    if person.gender:
        parts.append(_GENDER[t][person.gender])
    if person.village:
        parts.append(_VILLAGE[t].format(x=person.village))
    if person.mohalla:
        parts.append(_MOHALLA[t].format(x=person.mohalla))
    parts.extend(person.extras)
    return ", ".join(parts)


def phone_extra(lang: str, phone: str) -> str:
    return _PHONE[base_lang(lang)].format(p=phone)


def account_extra(lang: str, account: str, ifsc: str | None) -> str:
    t = base_lang(lang)
    if ifsc:
        return _ACCT[t].format(a=account, i=ifsc)
    return _ACCT_NO_IFSC[t].format(a=account)


def vehicle_extra(lang: str, plate: str) -> str:
    return _VEHICLE[base_lang(lang)].format(v=plate)


def role_sentence(lang: str, role: str, body: str) -> str:
    t = base_lang(lang)
    return f"{_ROLE[t][role]} {body}{_ENDING[t]}"


def vehicle_seen(lang: str, plate: str) -> str:
    return _VEHICLE_SEEN[base_lang(lang)].format(v=plate)


def number_used(lang: str, phone: str, name: str) -> str:
    return _NUMBER_USED[base_lang(lang)].format(p=phone, n=name)


def shared_note(lang: str, phone: str, wording: str, a: str, b: str) -> str:
    return _SHARED_NOTE[base_lang(lang)].format(p=phone, w=wording, a=a, b=b)


def shared_wording(lang: str) -> str:
    return {"en": "family number", "hi": "घर का नंबर", "hi-latn": "ghar ka number"}[base_lang(lang)]


def complainant_header(name: str, detail: str) -> str:
    return _COMPLAINANT_HEADER + (f"{name}, {detail}" if detail else name)


def phone_format(number: str, style: int) -> str:
    """Render a 10-digit number: 0 plain, 1 +91, 2 leading 0, 3 spaced."""
    if style == 1:
        return f"+91{number}"
    if style == 2:
        return f"0{number}"
    if style == 3:
        return f"{number[:5]} {number[5:]}"
    return number
