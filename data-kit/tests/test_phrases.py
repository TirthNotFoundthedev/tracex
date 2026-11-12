"""Phrase contract with the extractor: template shapes, separators, no hedges on OWNS lines."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from datakit import text

# Copied from tracex_engine/extract/hedges.py (HEDGE_PHRASES, NEGATION_WORDS); the kit does
# not import the backend. Update this copy when that list changes.
HEDGE_WORDS = (
    "possibly", "probably", "perhaps", "maybe", "may be", "might be", "could be",
    "suspected to be", "believed to be", "appears to be", "seems to be", "unverified",
    "unconfirmed", "not confirmed", "partly illegible", "illegible", "unclear", "allegedly",
    "reportedly", "suspected", "likely", "claims", "claimed", "doubtful", "to be verified",
    "not verified", "yet to be verified", "yet to be confirmed", "thought to be", "presumably",
    "rumoured", "rumored", "cannot be confirmed", "could not be confirmed",
    "could not be verified", "shayad", "sambhavtah", "apusht", "aspasht", "kathit", "sandeh",
    "sambhavat", "shaayad", "shak", "lagta hai", "शायद", "संभवतः", "हो सकता है", "अपुष्ट",
    "अस्पष्ट", "कथित", "संभावित", "संदेह", "संभवत", "लगता है", "शक",
    "not", "never", "no longer", "deny", "denies", "denied", "denying", "nahi", "nahin",
    "nahee", "nhi", "cannot", "नहीं", "नही", "न",
)  # fmt: skip

TEMPLATES: dict[str, dict[str, str]] = {
    "_PHONE": {
        "en": "mobile {p}",
        "hi": "मोबाइल नंबर {p}",
        "hi-latn": "mobile number {p}",
    },
    "_ACCT": {
        "en": "a/c {a} (IFSC {i})",
        "hi": "खाता संख्या {a} (IFSC {i})",
        "hi-latn": "khata sankhya {a} (IFSC {i})",
    },
    "_ACCT_NO_IFSC": {
        "en": "a/c {a}",
        "hi": "खाता संख्या {a}",
        "hi-latn": "khata sankhya {a}",
    },
    "_VEHICLE": {"en": "vehicle {v}", "hi": "वाहन {v}", "hi-latn": "vahan {v}"},
    "_NUMBER_USED": {
        "en": "Number {p} is used by {n}.",
        "hi": "नंबर {p} {n} द्वारा उपयोग किया जाता है।",
        "hi-latn": "{n} ka number {p} hai.",
    },
    "_SHARED_NOTE": {
        "en": "Number {p} is the {w} (used by {a} and {b}).",
        "hi": "नंबर {p} {w} है ({a} और {b} उपयोग करते हैं)।",
        "hi-latn": "Number {p} {w} hai ({a} aur {b} upyog karte hain).",
    },
    "_AGE": {"en": "aged {n}", "hi": "उम्र {n} वर्ष", "hi-latn": "umra {n} varsh"},
    "_DOB": {"en": "DOB {d}", "hi": "जन्म तिथि {d}", "hi-latn": "janm tithi {d}"},
    "_VILLAGE": {"en": "village {x}", "hi": "ग्राम {x}", "hi-latn": "gram {x}"},
    "_MOHALLA": {"en": "Mohalla {x}", "hi": "मोहल्ला {x}", "hi-latn": "mohalla {x}"},
    "_VEHICLE_SEEN": {
        "en": "Vehicle {v} was seen near the spot.",
        "hi": "घटनास्थल के पास वाहन {v} देखा गया।",
        "hi-latn": "Ghatnasthal ke paas vahan {v} dekha gaya.",
    },
}


def test_sentence_templates_are_pinned() -> None:
    """Any change to a template shape fails here, so it is visible to the extractor owner."""
    for name, expected in TEMPLATES.items():
        assert getattr(text, name) == expected, name
    assert getattr(text, "_GENDER") == {  # noqa: B009
        "en": {"male": "male", "female": "female"},
        "hi": {"male": "पुरुष", "female": "महिला"},
        "hi-latn": {"male": "purush", "female": "mahila"},
    }
    assert getattr(text, "_REL") == {  # noqa: B009
        "en": {"s/o": "s/o", "d/o": "d/o", "w/o": "w/o"},
        "hi": {"s/o": "पुत्र", "d/o": "पुत्री", "w/o": "पत्नी"},
        "hi-latn": {"s/o": "putra", "d/o": "putri", "w/o": "patni"},
    }


def test_person_clause_keeps_a_comma_before_the_first_identifier_cue() -> None:
    cues = {"en": "mobile", "hi": "मोबाइल नंबर", "hi-latn": "mobile number"}
    for lang, cue in cues.items():
        person = text.PersonText(name="NAME", extras=[text.phone_extra(lang, "9000000000")])
        assert text.clause(lang, person) == f"NAME, {cue} 9000000000"
        person = text.PersonText(name="NAME", age=30, extras=[text.phone_extra(lang, "9000000000")])
        assert f", {cue} 9000000000" in text.clause(lang, person)
    plain = text.PersonText(name="NAME", extras=[text.account_extra("en", "5010000000000", None)])
    assert text.clause("en", plain) == "NAME, a/c 5010000000000"
    vehicle = text.PersonText(name="NAME", extras=[text.vehicle_extra("hi", "UP32AB1234")])
    assert text.clause("hi", vehicle) == "NAME, वाहन UP32AB1234"


CUE = r"(?:mobile number|mobile|मोबाइल नंबर|खाता संख्या|khata sankhya|a/c|vehicle|वाहन|vahan)"


def test_every_planted_fir_ownership_line_has_a_separator_before_the_cue(
    gt: dict[str, Any], read_case_file: Callable[..., list[str]]
) -> None:
    entities = {e["gt_id"]: e for e in gt["entities"]}
    checked = 0
    for att in gt["attributions"]:
        src = att["source"]
        person = entities[att["entity"]]
        if att["code"] != "OWNS" or person["gt_id"].startswith("NZ-") or src["file"] != "fir.txt":
            continue
        ident = entities[att["identifier"]]
        line = read_case_file(src["case_id"], src["file"])[src["line"] - 1]
        assert re.search(rf"[,(] {CUE} {re.escape(ident['raw_text'])}", line), line
        checked += 1
    assert checked >= 20


def test_no_planted_ownership_line_contains_a_hedge_or_negation_word(
    gt: dict[str, Any], read_case_file: Callable[..., list[str]]
) -> None:
    entities = {e["gt_id"]: e for e in gt["entities"]}
    checked = 0
    for att in gt["attributions"]:
        if att["code"] != "OWNS" or entities[att["entity"]]["gt_id"].startswith("NZ-"):
            continue
        src = att["source"]
        batch = "b02" if "-02" in src["file"] or src["case_id"] == "C-202" else "b01"
        line = read_case_file(src["case_id"], src["file"], batch)[src["line"] - 1]
        for word in HEDGE_WORDS:
            pattern = rf"(?<![\wऀ-ॿ]){re.escape(word)}(?![\wऀ-ॿ])"
            assert not re.search(pattern, line, re.IGNORECASE), (src, word, line)
        checked += 1
    assert checked >= 30
