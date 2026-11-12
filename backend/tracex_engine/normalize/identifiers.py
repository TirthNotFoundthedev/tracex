"""Phone, account, IFSC and vehicle normalization (matching spec section 1)."""

import re

_MOBILE = re.compile(r"[6-9]\d{9}")
_UPI_HANDLE = re.compile(r"^(?P<local>[^@\s]+)@(?P<psp>[A-Za-z][A-Za-z0-9.]*)$")
_IFSC = re.compile(r"[A-Z]{4}0[A-Z0-9]{6}")
_VEHICLE = re.compile(r"[A-Z]{2}\d{2}[A-Z]{1,3}\d{4}")
_ACCOUNT_SEPARATORS = re.compile(r"[\s-]")
_PHONE_SEPARATORS = re.compile(r"[\s\-().]")
_VEHICLE_SEPARATORS = re.compile(r"[\s\-.]")

ACCOUNT_MIN_DIGITS = 9
ACCOUNT_MAX_DIGITS = 18


def normalize_phone(text: str) -> str | None:
    """Ten-digit Indian mobile without country code or leading zero, or None.

    Landlines (STD + number) are not normalized in this version and return None.
    """
    compact = _PHONE_SEPARATORS.sub("", text.strip())
    if compact.startswith("+"):
        compact = compact[1:]
        if not compact.startswith("91"):
            return None
    if not compact.isascii() or not compact.isdigit():
        return None
    if len(compact) == 12 and compact.startswith("91"):
        compact = compact[2:]
    elif len(compact) == 11 and compact.startswith("0"):
        compact = compact[1:]
    return compact if _MOBILE.fullmatch(compact) else None


def phone_from_upi(handle: str) -> str | None:
    """The phone a UPI handle such as `9000021203@upi` stands for, or None for any other handle."""
    match = _UPI_HANDLE.match(handle.strip())
    return normalize_phone(match.group("local")) if match else None


def normalize_account(text: str) -> str | None:
    """Account digits only, leading zeros kept; None unless 9 to 18 digits."""
    digits = _ACCOUNT_SEPARATORS.sub("", text.strip())
    if not digits.isascii() or not digits.isdigit():
        return None
    return digits if ACCOUNT_MIN_DIGITS <= len(digits) <= ACCOUNT_MAX_DIGITS else None


def normalize_ifsc(text: str) -> str | None:
    """Uppercase IFSC, or None when it is not four letters, a zero and six characters."""
    code = text.strip().upper()
    return code if _IFSC.fullmatch(code) else None


def normalize_vehicle(text: str) -> str | None:
    """Registration uppercase with no spaces, hyphens or dots (`UP32AB1234`), or None."""
    compact = _VEHICLE_SEPARATORS.sub("", text).upper()
    return compact if _VEHICLE.fullmatch(compact) else None
