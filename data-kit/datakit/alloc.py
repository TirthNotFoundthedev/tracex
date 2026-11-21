"""Identifier allocators. Planted-case noise and noise-case values come from disjoint regions."""

from __future__ import annotations

from datakit.rng import Stream

STATE_CODES = ("UP", "DL", "HR", "RJ", "MP", "UK")


class Allocators:
    """Unique synthetic phones, accounts and plates for noise. Regions never overlap."""

    def __init__(self, seed: int) -> None:
        self._seed = seed
        self._streams: dict[str, Stream] = {}
        self._used: set[str] = set()

    def _stream(self, purpose: str) -> Stream:
        if purpose not in self._streams:
            self._streams[purpose] = Stream(self._seed, f"alloc:{purpose}")
        return self._streams[purpose]

    def _unique(self, make: str, purpose: str) -> str:
        stream = self._stream(purpose)
        while True:
            value = _MAKERS[make](stream, purpose)
            if value not in self._used and not (make == "phone" and self._near_used(value)):
                self._used.add(value)
                return value

    def _near_used(self, phone: str) -> bool:
        """Is a phone one adjacent-digit swap away from one already allocated? Such a pair reads
        as a transposed number (PHONE_TRANSPOSED), so only planted cases may contain one."""
        for i in range(len(phone) - 1):
            if phone[i] != phone[i + 1]:
                swapped = phone[:i] + phone[i + 1] + phone[i] + phone[i + 2 :]
                if swapped in self._used:
                    return True
        return False

    def phone(self, region: str) -> str:
        """`region` is `planted` (inside planted cases) or `noise`."""
        return self._unique("phone", f"phone:{region}")

    def account(self, region: str) -> str:
        return self._unique("account", f"account:{region}")

    def plate(self, region: str) -> str:
        return self._unique("plate", f"plate:{region}")


def _phone(stream: Stream, purpose: str) -> str:
    low, high = (0, 99_999) if purpose.endswith("planted") else (100_000, 999_999)
    return str(9_100_000_000 + stream.between(low, high))


def _account(stream: Stream, purpose: str) -> str:
    lead = 0 if purpose.endswith("planted") else stream.between(1, 9)
    return f"5019{lead}{stream.between(0, 99_999_999):08d}"


def _plate(stream: Stream, purpose: str) -> str:
    low, high = (0, 4999) if purpose.endswith("planted") else (5000, 9999)
    code = stream.choice(STATE_CODES)
    return f"{code}{stream.between(1, 99):02d}ZZ{stream.between(low, high):04d}"


_MAKERS = {"phone": _phone, "account": _account, "plate": _plate}
