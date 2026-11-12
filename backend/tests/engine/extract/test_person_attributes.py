"""Person attributes and identifier flags read from FIR text, with the original text kept."""

import pytest

from tests.engine.support import SDR_HEADER, fir_file, note, notes_file
from tracex_engine.extract import AttributionCode, IdKind, PersonMention, extract_case
from tracex_engine.ingest import SourceRef


def _fir_persons(line: str, case_id: str = "C-107") -> tuple[PersonMention, ...]:
    return extract_case(case_id, {"fir.txt": fir_file(case_id, {12: line})}).persons


def _accused(line: str) -> PersonMention:
    [person] = [p for p in _fir_persons(line) if p.source.line == 12]
    return person


def test_age_and_village_are_read_with_original_text() -> None:
    person = _accused("The accused Jaswinder Bhullar, aged 34, village Kherapur, fled the spot.")

    assert (person.raw_text, person.normalized) == ("Jaswinder Bhullar", "jaswinder bhullar")
    assert person.age is not None
    assert (person.age.raw_text, person.age.normalized) == ("aged 34", "34")
    assert person.locality is not None
    assert (person.locality.raw_text, person.locality.normalized) == (
        "village Kherapur",
        "kherapur",
    )
    assert person.dob is None and person.gender is None and person.relative is None


@pytest.mark.parametrize(
    "written",
    ["DOB 12-04-1990", "DOB 12/04/1990", "DOB 1990-04-12", "DOB 12 April 1990"],
)
def test_dob_formats_normalize_to_iso_date(written: str) -> None:
    person = _accused(f"The accused Arjun Mehra, {written}, Mohalla Shivpuri, was questioned.")

    assert person.dob is not None
    assert person.dob.normalized == "1990-04-12"
    assert person.dob.raw_text == written
    assert person.locality is not None
    assert person.locality.normalized == "shivpuri"


def test_relative_and_gender_are_read() -> None:
    person = _accused("The accused Parminder Atwal s/o Gurmeet Atwal, male, was arrested.")

    assert person.relative is not None
    assert person.relative.relation == "son"
    assert person.relative.name.raw_text == "Gurmeet Atwal"
    assert person.relative.name.normalized == "gurmeet atwal"
    assert person.gender is not None
    assert person.gender.normalized == "male"
    assert [
        p.normalized
        for p in _fir_persons("The accused Parminder Atwal s/o Gurmeet Atwal.")
        if p.source.line == 12
    ] == ["parminder atwal"]


def test_alias_after_urf_is_kept_on_the_main_person_not_a_second_person() -> None:
    line = "The accused Rakesh Dubey urf Monu owns mobile 9000041001 and mobile 9000041002."
    records = extract_case("C-209", {"fir.txt": fir_file("C-209", {12: line})})

    [person] = [p for p in records.persons if p.source.line == 12]
    assert person.normalized == "rakesh dubey"
    assert [(a.raw_text, a.normalized) for a in person.aliases] == [("Monu", "monu")]
    owned = {a.identifier.normalized for a in records.attributions if a.holder is person}
    assert owned == {"9000041001", "9000041002"}


def test_second_person_in_a_sentence_takes_the_identifiers_after_their_name() -> None:
    line = (
        "The accused Ramesh Yadav, mobile 9000022310, and witness Sunil Verma, mobile 9000022311, "
        "were present."
    )
    records = extract_case("C-109", {"fir.txt": fir_file("C-109", {12: line})})

    owner = {a.identifier.normalized: a.holder.normalized for a in records.attributions}
    assert owner == {"9000022310": "ramesh yadav", "9000022311": "sunil verma"}


def test_identifier_without_an_ownership_cue_is_only_mentioned_with() -> None:
    line = "The accused Ramesh Yadav was seen with a person who called 9000022310 twice."
    records = extract_case("C-109", {"fir.txt": fir_file("C-109", {12: line})})

    [attribution] = records.attributions
    assert attribution.code is AttributionCode.MENTIONED_WITH
    assert attribution.hedged is False


def test_in_the_name_of_is_never_owns() -> None:
    line = (
        "The accused Vikram Chauhan, mobile 9000035562. "
        "Number 9000035562 is in the name of Kamla Devi."
    )
    records = extract_case("C-110", {"fir.txt": fir_file("C-110", {12: line})})

    by_holder = {a.holder.normalized: a.code for a in records.attributions}
    assert by_holder["vikram chauhan"] is AttributionCode.OWNS
    assert by_holder["kamla devi"] is AttributionCode.MENTIONED_WITH


def test_devanagari_names_and_digits_in_a_hindi_fir_line() -> None:
    line = "आरोपी मोहम्मद इरफ़ान, मोबाइल नंबर 90000 51234।"
    records = extract_case("C-120", {"fir.txt": fir_file("C-120", {12: line})})

    [person] = [p for p in records.persons if p.source.line == 12]
    assert person.raw_text == "मोहम्मद इरफ़ान"
    assert person.normalized == "mohammad irfan"
    [attribution] = [a for a in records.attributions if a.holder is person]
    assert attribution.code is AttributionCode.OWNS
    assert attribution.identifier.raw_text == "90000 51234"
    assert attribution.identifier.normalized == "9000051234"


@pytest.mark.parametrize(
    "written",
    ["9000052210", "90000 52210", "+91-9000052210", "09000052210", "+91 90000 52210"],
)
def test_phone_formats_keep_the_raw_text_and_share_one_normalized_value(written: str) -> None:
    records = extract_case(
        "C-127", {"fir.txt": fir_file("C-127", {12: f"Seen with mobile {written} today."})}
    )

    [phone] = [i for i in records.identifiers if i.kind is IdKind.PHONE]
    assert phone.raw_text == written
    assert phone.normalized == "9000052210"
    assert phone.source == SourceRef("C-127", "fir.txt", 12)


@pytest.mark.parametrize("written", ["UP32AB1234", "up 32 ab 1234", "UP-32-AB-1234"])
def test_vehicle_plates_normalize_without_spaces_or_hyphens(written: str) -> None:
    notes = {
        "notes.txt": notes_file("C-104", {3: note(f"Vehicle {written} seen near the market.")})
    }

    [plate] = [i for i in extract_case("C-104", notes).identifiers if i.kind is IdKind.VEHICLE]

    assert plate.raw_text == written
    assert plate.normalized == "UP32AB1234"


def test_shop_or_pco_wording_flags_the_identifier_and_creates_no_owner() -> None:
    notes = {"notes.txt": notes_file("C-132", {3: note("9000088120 is the shop number (PCO).")})}

    records = extract_case("C-132", notes)

    [phone] = records.identifiers
    assert phone.shared_wording is True
    assert records.attributions == ()


def test_a_plain_phone_in_a_note_has_no_shared_wording() -> None:
    notes = {"notes.txt": notes_file("C-132", {3: note("Called 9000088120 on Monday.")})}

    [phone] = extract_case("C-132", notes).identifiers

    assert phone.shared_wording is False


def test_sdr_row_gives_registered_to_and_never_owns() -> None:
    sdr = f"{SDR_HEADER}\n9000035562,Kamla Devi,,,,2024-01-05\n"

    records = extract_case("C-111", {"sdr.csv": sdr})

    [attribution] = records.attributions
    assert attribution.code is AttributionCode.REGISTERED_TO
    assert attribution.holder.normalized == "kamla devi"
    assert attribution.identifier.normalized == "9000035562"
    assert attribution.source == SourceRef("C-111", "sdr.csv", 2)
    [person] = records.persons
    assert person.locality is None and person.district is None


def test_org_with_m_s_prefix_is_an_org_and_owns_the_account() -> None:
    line = "M/s Shree Balaji Traders, Mohalla Subhash Nagar, a/c 5010000066602 (IFSC SYNB0000123)."
    records = extract_case("C-122", {"fir.txt": fir_file("C-122", {12: line})})

    [org] = [o for o in records.orgs if o.source.line == 12]
    assert org.raw_text == "Shree Balaji Traders"
    assert org.normalized == "shree balaji"
    assert org.locality is not None and org.locality.normalized == "subhash nagar"
    [owns] = [a for a in records.attributions if a.holder is org]
    assert owns.code is AttributionCode.OWNS
    assert owns.identifier.normalized == "5010000066602"


def test_extraction_is_deterministic() -> None:
    line = "The accused Jaswinder Bhullar, aged 34, mobile 90000 14471, village Kherapur."
    files = {
        "fir.txt": fir_file("C-107", {12: line}),
        "notes.txt": notes_file("C-107", {3: note("Number 9000014471 is used by Jaswinder.")}),
    }

    assert extract_case("C-107", files) == extract_case("C-107", files)
