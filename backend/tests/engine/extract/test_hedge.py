"""AC-19 (data-kit Q7): hedged wording is flagged, never asserted as ownership."""

import pytest

from tests.engine.support import fir_file, note, notes_file
from tracex_engine.extract import (
    CONFIDENCE_CLEAR,
    CONFIDENCE_HEDGED,
    HEDGE_PHRASES,
    LEGIBILITY_HEDGE_PHRASES,
    AttributionCode,
    IdKind,
    extract_case,
)

G5_MIN_CONFIDENCE = 0.7


def test_hedge_phrase_list_is_nonempty_and_lowercase_and_covers_the_spec_examples() -> None:
    assert len(HEDGE_PHRASES) == len(set(HEDGE_PHRASES))
    assert all(p == p.lower() for p in HEDGE_PHRASES)
    for required in ("possibly", "may be", "suspected to be", "unverified", "अपुष्ट", "अस्पष्ट"):
        assert required in HEDGE_PHRASES
    assert set(LEGIBILITY_HEDGE_PHRASES) <= set(HEDGE_PHRASES)


@pytest.mark.parametrize("hedge", ["possibly", "may be", "suspected to be", "probably"])
def test_hedged_ownership_statement_is_flagged_and_not_asserted_as_owns(hedge: str) -> None:
    sentence = f"Number 9000014471 is {hedge} used by Irfan bhai."
    if hedge in ("may be", "suspected to be"):
        sentence = f"Number 9000014471 {hedge} used by Irfan bhai."
    files = {"notes.txt": notes_file("C-201", {3: note(sentence)})}

    records = extract_case("C-201", files)

    [person] = records.persons
    [attribution] = [a for a in records.attributions if a.holder is person]
    assert attribution.hedged is True
    assert attribution.code is not AttributionCode.OWNS
    assert attribution.identifier.normalized == "9000014471"


def test_hindi_hedge_marks_an_ownership_statement_as_hedged() -> None:
    sentence = "इरफ़ान का नंबर शायद 9000014471 है।"
    files = {"notes.txt": notes_file("C-201", {3: note(sentence)})}

    records = extract_case("C-201", files)

    attributions = [a for a in records.attributions if a.identifier.normalized == "9000014471"]
    assert attributions
    assert all(a.hedged and a.code is not AttributionCode.OWNS for a in attributions)


def test_unhedged_ownership_next_to_the_same_words_elsewhere_is_still_owns() -> None:
    files = {
        "notes.txt": notes_file("C-201", {3: note("Number 9000014471 is used by Irfan bhai.")})
    }

    [attribution] = extract_case("C-201", files).attributions

    assert attribution.code is AttributionCode.OWNS
    assert attribution.hedged is False


def test_ac19_hedged_plate_has_confidence_below_g5_and_the_clear_plate_does_not() -> None:
    clear = {
        "fir.txt": fir_file("C-121", {12: "A grey bike, plate UP32CD9021, was seen near the shop."})
    }
    hedged = {
        "notes.txt": notes_file(
            "C-211", {3: note("Plate partly illegible, noted as UP32CD9021 (unverified).")}
        )
    }

    [clear_plate] = [
        i for i in extract_case("C-121", clear).identifiers if i.kind is IdKind.VEHICLE
    ]
    [hedged_plate] = [
        i for i in extract_case("C-211", hedged).identifiers if i.kind is IdKind.VEHICLE
    ]

    assert clear_plate.normalized == hedged_plate.normalized == "UP32CD9021"
    assert clear_plate.confidence == CONFIDENCE_CLEAR >= G5_MIN_CONFIDENCE
    assert hedged_plate.confidence == CONFIDENCE_HEDGED < G5_MIN_CONFIDENCE
    assert hedged_plate.raw_text == "UP32CD9021"
    assert hedged_plate.source.line == 3


def test_ac19_hindi_hedge_wording_lowers_vehicle_confidence() -> None:
    files = {"notes.txt": notes_file("C-211", {3: note("अस्पष्ट, UP32CD9021 लिखा है (अपुष्ट)")})}

    [plate] = [i for i in extract_case("C-211", files).identifiers if i.kind is IdKind.VEHICLE]

    assert plate.confidence == CONFIDENCE_HEDGED


def test_negated_ownership_is_not_asserted_at_all() -> None:
    files = {
        "notes.txt": notes_file("C-201", {3: note("Number 9000014471 is not used by Irfan bhai.")})
    }

    records = extract_case("C-201", files)

    assert records.attributions == ()
