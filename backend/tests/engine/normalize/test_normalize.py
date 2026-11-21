"""Normalization rules from docs/specs/engine-matching.md section 1 and 2."""

from datetime import date

import pytest

from tracex_engine.normalize import (
    normalize_account,
    normalize_ifsc,
    normalize_name,
    normalize_org_name,
    normalize_phone,
    normalize_place,
    normalize_vehicle,
    parse_date,
    phone_from_upi,
    transliterate_devanagari,
)


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("9000014471", "9000014471"),
        ("90000 14471", "9000014471"),
        ("+91-9000014471", "9000014471"),
        ("+91 90000 14471", "9000014471"),
        ("919000014471", "9000014471"),
        ("09000014471", "9000014471"),
        ("(90000) 14471", "9000014471"),
        ("9000-014-471", "9000014471"),
        ("  9000014471 ", "9000014471"),
        ("12345", None),
        ("90000144711", None),
        ("5010000019082", None),
        ("1000014471", None),
        ("", None),
        ("phone", None),
    ],
)
def test_phone_is_ten_digits_without_country_code_or_leading_zero(
    written: str, expected: str | None
) -> None:
    assert normalize_phone(written) == expected


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("9000021203@upi", "9000021203"),
        ("9000021203@OKSBI", "9000021203"),
        ("+919000021203@upi", "9000021203"),
        ("raju.store@upi", None),
        ("9000021203", None),
        ("@upi", None),
    ],
)
def test_upi_handle_that_is_a_phone_becomes_that_phone(written: str, expected: str | None) -> None:
    assert phone_from_upi(written) == expected


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("5010000019082", "5010000019082"),
        ("0010000019082", "0010000019082"),
        ("5010 0000 19082", "5010000019082"),
        ("5010-0000-19082", "5010000019082"),
        ("123", None),
        ("12345678901234567890", None),
        ("50100000190ab", None),
        ("", None),
    ],
)
def test_account_is_digits_only_and_keeps_leading_zeros(written: str, expected: str | None) -> None:
    assert normalize_account(written) == expected


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("synb0000123", "SYNB0000123"),
        (" FAKE0000456 ", "FAKE0000456"),
        ("SYNB1000123", None),
        ("", None),
    ],
)
def test_ifsc_is_uppercase_and_validated(written: str, expected: str | None) -> None:
    assert normalize_ifsc(written) == expected


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("UP32AB1234", "UP32AB1234"),
        ("up 32 ab 1234", "UP32AB1234"),
        ("UP-32-AB-1234", "UP32AB1234"),
        ("up32ab1234", "UP32AB1234"),
        ("UP32ZZ1234", "UP32ZZ1234"),
        ("UP3AB123", None),
        ("hello", None),
        ("", None),
    ],
)
def test_vehicle_is_uppercase_without_spaces_or_hyphens(written: str, expected: str | None) -> None:
    assert normalize_vehicle(written) == expected


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("Mohd. Irfan", "mohammad irfan"),
        ("MOHD IRFAN", "mohammad irfan"),
        ("Md Irfan", "mohammad irfan"),
        ("Irfan bhai", "irfan"),
        ("Shri Ramesh Yadav", "ramesh yadav"),
        ("Smt. Sunita Devi", "sunita devi"),
        ("Irfan Sahab", "irfan"),
        ("  Jaswinder   Bhullar ", "jaswinder bhullar"),
        ("O'Brien-Smith", "o brien smith"),
        ("Bhai", ""),
        ("", ""),
        ("मोहम्मद इरफ़ान", "mohammad irfan"),
        ("इरफ़ान भाई", "irfan"),
        ("रमेश यादव", "ramesh yadav"),
        ("श्रीमती सुनीता देवी", "sunita devi"),
    ],
)
def test_name_is_romanised_lowercase_without_honorifics_and_with_mohd_expanded(
    written: str, expected: str
) -> None:
    assert normalize_name(written) == expected


def test_devanagari_and_roman_spellings_of_the_must_pass_vector_agree() -> None:
    assert normalize_name("Mohd. Irfan") == normalize_name("मोहम्मद इरफ़ान") == "mohammad irfan"


def test_normalization_is_idempotent_on_names() -> None:
    once = normalize_name("Mohd. Irfan bhai")

    assert normalize_name(once) == once


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("खान", "khan"),
        ("कुमारी", "kumari"),
        ("भुल्लर", "bhullar"),
        ("साहब", "sahab"),
        ("फ़ैज़", "faiz"),
        ("hello", "hello"),
        ("", ""),
    ],
)
def test_devanagari_is_transliterated_offline_other_text_is_unchanged(
    written: str, expected: str
) -> None:
    assert transliterate_devanagari(written) == expected


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("Shree Balaji Traders", "shree balaji"),
        ("Shri Balaji Trading Co", "shri balaji"),
        ("M/s Shree Balaji Traders", "shree balaji"),
        ("Alpha Enterprises Pvt. Ltd.", "alpha"),
        ("Traders", ""),
    ],
)
def test_org_name_drops_legal_and_generic_suffixes(written: str, expected: str) -> None:
    assert normalize_org_name(written) == expected


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("12-04-1990", date(1990, 4, 12)),
        ("12/04/1990", date(1990, 4, 12)),
        ("1990-04-12", date(1990, 4, 12)),
        ("12 April 1990", date(1990, 4, 12)),
        ("12 apr 1990", date(1990, 4, 12)),
        ("31-02-1990", None),
        ("1990", None),
        ("", None),
    ],
)
def test_date_formats_in_the_data_kit_parse_to_a_date(written: str, expected: date | None) -> None:
    assert parse_date(written) == expected


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("Hillcrest  Market", "hillcrest market"),
        ("  Ward 5 ", "ward 5"),
        ("Subhash-Nagar.", "subhash nagar"),
    ],
)
def test_place_is_compared_as_lowercase_normalized_text(written: str, expected: str) -> None:
    assert normalize_place(written) == expected


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("बालाजी ट्रेडर्स", "balaji"),
        ("श्री बालाजी ट्रेडिंग कंपनी", "shri balaji"),
        ("गुप्ता एंटरप्राइजेज प्राइवेट लिमिटेड", "gupta"),
        ("ट्रेडर्स", ""),
    ],
)
def test_org_name_drops_devanagari_legal_suffixes(written: str, expected: str) -> None:
    assert normalize_org_name(written) == expected
